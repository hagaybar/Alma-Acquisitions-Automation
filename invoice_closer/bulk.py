"""Bulk-loaded read view of one vendor's invoices and order lines.

Reading a large set one record at a time costs ~10 API calls per order line. Alma's
list endpoints return 100 records per call, and the invoice list with view=full carries
the invoice lines (Sandbox, 18 Nov 2026: the same fields as a single GET). So one vendor's
invoices and order lines load in a few dozen calls, and the closer's lookups are answered
from memory.

Use it for reads that happen before any write (resolving the input, eligibility,
pre-analysis, dry runs). A live run must read invoices fresh after writing; see
scripts/close_invoices.py, which resolves with this view and acts with the plain Gateway.

Brief order-line records from the list endpoint lack invoice_reference; invoices are
found through their lines instead (find_invoices_by_pol).
"""
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _v(obj, key):
    val = (obj or {}).get(key)
    return val.get("value") if isinstance(val, dict) else val


def _line_pol(line) -> Optional[str]:
    ref = line.get("po_line")
    return ref.get("value") if isinstance(ref, dict) else (ref or None)


class BulkGateway:
    def __init__(self, gw, vendor: str, log: Callable[..., None] = lambda *a, **k: None):
        if not vendor:
            raise ValueError("bulk loading needs a vendor code")
        self._gw = gw
        self.vendor = vendor
        self.log = log
        self.invoices: Dict[str, Dict] = {}
        self.lines: Dict[str, List[Dict]] = {}
        self.by_number: Dict[str, List[str]] = defaultdict(list)
        self.by_pol: Dict[str, List[str]] = defaultdict(list)
        self.pols: Dict[str, Dict] = {}
        self._cache: Dict[Any, Any] = {}
        self.calls = 0

    # ---- loading ----------------------------------------------------------
    def _pages(self, path: str, params: Dict, key: str, stage: str):
        offset, total = 0, None
        while True:
            data = self._gw._get(path, dict(params, limit=100, offset=offset))
            self.calls += 1
            batch = data.get(key) or []
            total = int(data.get("total_record_count") or 0)
            yield from batch
            offset += 100
            if offset % 1000 == 0:
                self.log("progress", stage=stage, done=min(offset, total), total=total)
            if not batch or offset >= total:
                return

    def load(self, cache: Optional[Path] = None, max_age_minutes: float = 60) -> "BulkGateway":
        """Download, or reuse `cache` if it exists and is younger than max_age_minutes.
        A fresh download is saved to `cache`. It maps input to invoices; a live run must
        still read each open invoice fresh before writing (scripts/close_invoices.py does)."""
        if cache and cache.exists():
            age = (time.time() - cache.stat().st_mtime) / 60
            if age <= max_age_minutes:
                data = json.loads(cache.read_text(encoding="utf-8"))
                if data.get("vendor") == self.vendor:
                    for inv in data["invoices"]:
                        self._add_invoice(inv, data["lines"][str(inv["id"])])
                    self.pols = data["pols"]
                    self.log("bulk_from_cache", file=str(cache), age_minutes=round(age, 1),
                             invoices=len(self.invoices), order_lines=len(self.pols))
                    return self
            self.log("bulk_cache_stale", file=str(cache), age_minutes=round(age, 1))
        self._download()
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".tmp")
            tmp.write_text(json.dumps({"vendor": self.vendor, "saved": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                       "invoices": list(self.invoices.values()), "lines": self.lines,
                                       "pols": self.pols}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(cache)
            self.log("bulk_cache_saved", file=str(cache))
        return self

    def _add_invoice(self, inv: Dict, lines: List[Dict]) -> None:
        iid = str(inv["id"])
        self.invoices[iid] = inv
        self.lines[iid] = lines
        self.by_number[str(inv.get("number"))].append(iid)
        for line in lines:
            p = _line_pol(line)
            if p:
                self.by_pol[p].append(iid)

    def _download(self) -> None:
        q = f"vendor_code~{self.vendor}"
        for inv in self._pages("almaws/v1/acq/invoices", {"q": q, "view": "full"}, "invoice",
                               "download invoices"):
            if _v(inv, "vendor") != self.vendor:      # vendor_code~ is a contains-match
                continue
            iid = str(inv["id"])
            lines = ((inv.get("invoice_lines") or {}).get("invoice_line")) or []
            expected = _v(inv, "number_of_lines")
            if expected is not None and int(expected) != len(lines):
                lines = self._gw.get_invoice_lines(iid)   # list view cut the lines short
                self.calls += 1
            self._add_invoice(inv, lines)
        for pol in self._pages("almaws/v1/acq/po-lines", {"q": q, "status": "ALL_WITH_CLOSED"},
                               "po_line", "download order lines"):
            if _v(pol, "vendor") == self.vendor:
                self.pols[str(pol.get("number"))] = pol
        self.log("bulk_loaded", vendor=self.vendor, invoices=len(self.invoices),
                 order_lines=len(self.pols), api_calls=self.calls)

    # ---- the Gateway read interface ---------------------------------------
    def get_invoice(self, invoice_id: str) -> Dict:
        inv = self.invoices.get(str(invoice_id))
        return inv if inv is not None else self._fallback("get_invoice", invoice_id)

    def find_invoices_by_number(self, number: str) -> List[Dict]:
        ids = self.by_number.get(str(number))
        if ids is None:
            return self._fallback("find_invoices_by_number", number)
        return [self.invoices[i] for i in ids]

    def get_invoice_lines(self, invoice_id: str) -> List[Dict]:
        lines = self.lines.get(str(invoice_id))
        return lines if lines is not None else self._fallback("get_invoice_lines", invoice_id)

    def find_invoices_by_pol(self, pol_no: str) -> List[Dict]:
        return [self.invoices[i] for i in dict.fromkeys(self.by_pol.get(pol_no, []))]

    def get_pol(self, pol_no: str) -> Dict:
        pol = self.pols.get(pol_no)
        return pol if pol is not None else self._fallback("get_pol", pol_no)

    def __getattr__(self, name):
        # Everything else (portfolios, items, sets, _get) goes to the real gateway, cached.
        if name == "invoice_service":
            raise AttributeError("BulkGateway is read-only")
        target = getattr(self._gw, name)
        if not callable(target):
            return target
        return lambda *args: self._fallback(name, *args)

    def _fallback(self, name, *args):
        key = (name, args)
        try:
            hash(key)
        except TypeError:
            self.calls += 1
            return getattr(self._gw, name)(*args)
        if key not in self._cache:
            self.calls += 1
            self._cache[key] = getattr(self._gw, name)(*args)
        return self._cache[key]
