"""Read the list of records to close from an Alma set or a file (xlsx, csv, tsv).

Each row names one record by any of: MMS ID (title), PO-line number, invoice number
or invoice ID. A file may have a header row; recognised headers are listed in
HEADER_KINDS. Without a recognised header, the first column is read and each value's
kind is detected from its shape. Optional voucher columns override the payment
values for that row's invoice.
"""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

HEADER_KINDS = {
    "mms_id": "mms", "mms": "mms", "mmsid": "mms", "title_mms_id": "mms",
    "pol": "pol", "pol_number": "pol", "po_line": "pol", "po_line_number": "pol", "poline": "pol",
    "invoice_number": "invoice_number", "invoice_no": "invoice_number", "invoice": "invoice_number",
    "invoice_id": "invoice_id",
}
VOUCHER_HEADERS = {"voucher_number", "voucher_amount", "voucher_currency", "voucher_date"}

POL_RE = re.compile(r"^POL-\d+$", re.I)
MMS_RE = re.compile(r"^99\d{8,}$")          # Alma MMS IDs start with 99
INVOICE_ID_RE = re.compile(r"^\d{15,}$")      # internal IDs are long; MMS caught first


@dataclass
class Target:
    kind: str            # mms | pol | invoice_number | invoice_id
    value: str
    source: str          # e.g. "set 123 member 4" / "file.xlsx row 7"
    voucher: Dict[str, str] = field(default_factory=dict)


def detect_kind(value: str) -> str:
    if POL_RE.match(value):
        return "pol"
    if MMS_RE.match(value):
        return "mms"
    if INVOICE_ID_RE.match(value):
        return "invoice_id"
    return "invoice_number"


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(h).strip().lower()).strip("_")


def _clean(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():   # Excel turns IDs into floats
        v = int(v)
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def _rows_from_file(path: Path) -> List[List[str]]:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        return [[_clean(c) for c in row] for row in ws.iter_rows(values_only=True)]
    if suffix in (".csv", ".tsv", ".txt"):
        delim = "\t" if suffix in (".tsv", ".txt") else ","
        with path.open(newline="", encoding="utf-8-sig") as fh:
            return [[_clean(c) for c in row] for row in csv.reader(fh, delimiter=delim)]
    raise ValueError(f"Unsupported file type {suffix!r}: use .xlsx, .csv or .tsv")


def targets_from_file(path: Path) -> List[Target]:
    rows = [r for r in _rows_from_file(path) if any(c for c in r)]
    if not rows:
        return []
    header = [_norm_header(h) for h in rows[0]]
    id_cols = [(i, HEADER_KINDS[h]) for i, h in enumerate(header) if h in HEADER_KINDS]
    voucher_cols = {h: i for i, h in enumerate(header) if h in VOUCHER_HEADERS}
    targets: List[Target] = []
    if id_cols:
        col, kind = id_cols[0]   # first recognised identifier column wins
        for n, row in enumerate(rows[1:], start=2):
            value = row[col] if col < len(row) else ""
            if not value:
                continue
            voucher = {h: row[i] for h, i in voucher_cols.items() if i < len(row) and row[i]}
            targets.append(Target(kind, value, f"{path.name} row {n}", voucher))
        return targets
    for n, row in enumerate(rows, start=1):
        value = row[0]
        if value:
            targets.append(Target(detect_kind(value), value, f"{path.name} row {n}"))
    return targets


def targets_from_set(gateway, set_id: str) -> List[Target]:
    info = gateway.get_set(set_id)
    content = ((info.get("content") or {}).get("value") or "").upper()
    ids = gateway.get_set_member_ids(set_id)
    kind = {"BIB_MMS": "mms"}.get(content)
    if kind is None:
        raise ValueError(f"Set {set_id} holds {content or 'unknown'} records; "
                         "only title (BIB_MMS) sets are supported")
    return [Target(kind, mid, f"set {set_id} member {n}") for n, mid in enumerate(ids, start=1)]


def load_targets(gateway, set_id: Optional[str], file: Optional[Path]) -> List[Target]:
    if bool(set_id) == bool(file):
        raise ValueError("Give exactly one input: an Alma set ID or a file")
    return targets_from_set(gateway, set_id) if set_id else targets_from_file(Path(file))
