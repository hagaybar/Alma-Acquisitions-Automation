"""Thin Alma API layer. Reads may retry; writes never do.

Field notes confirmed in Alma Sandbox (Nov 2026):
- invoice payment status is nested: payment.payment_status.value
- invoice JSON lists alerts under `alert` (singular), a flat list
- a closed invoice may return invoice_workflow_status = {}
- PO-line search accepts q=mms_id~<mms>; invoice search accepts q=invoice_number~<n>
  (both are contains-matches: filter exact values afterwards)
- PO-line search with status=ALL excludes CLOSED lines; use status=ALL_WITH_CLOSED.
  Search results are brief: they lack invoice_reference, so read each line in full
- portfolio availability comes as {"value": "11", "desc": "Available"}, not "ACTIVE"
- item receipt date is item_data.arrival_date (empty = not received)
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


class WriteOutcomeUnknown(Exception):
    """The write was sent but no reply arrived. Reconcile by reading; never resend."""


class WriteRejected(Exception):
    """Alma answered the write with a 4xx: the request was refused, nothing changed."""

    def __init__(self, status: int, alma_code: str, message: str):
        super().__init__(f"HTTP {status} {alma_code}: {message}")
        self.status, self.alma_code, self.message = status, alma_code, message


class Gateway:
    def __init__(self, environment: str, write_timeout: float = 180.0):
        from almaapitk import AlmaAPIClient
        self.environment = environment
        self._reader = AlmaAPIClient(environment)
        # No automatic retries on writes: a retried POST could pay twice.
        self._writer = AlmaAPIClient(environment, max_retries=0, timeout=write_timeout)

    # ---- reads -------------------------------------------------------------
    def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        return self._reader.get(path, params=params).json()

    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        return self._get(f"almaws/v1/acq/invoices/{invoice_id}")

    def find_invoices_by_number(self, number: str) -> List[Dict[str, Any]]:
        data = self._get("almaws/v1/acq/invoices", {"q": f"invoice_number~{number}", "limit": 100})
        return [i for i in (data.get("invoice") or []) if str(i.get("number")) == str(number)]

    def get_invoice_lines(self, invoice_id: str) -> List[Dict[str, Any]]:
        lines, offset = [], 0
        while True:
            data = self._get(f"almaws/v1/acq/invoices/{invoice_id}/lines",
                             {"limit": 100, "offset": offset})
            batch = data.get("invoice_line") or []
            lines.extend(batch)
            offset += 100
            if not batch or offset >= int(data.get("total_record_count") or 0):
                return lines

    def get_pol(self, pol: str) -> Dict[str, Any]:
        return self._get(f"almaws/v1/acq/po-lines/{pol}")

    def find_pols_by_mms(self, mms_id: str) -> List[Dict[str, Any]]:
        data = self._get("almaws/v1/acq/po-lines",
                         # status=ALL silently leaves CLOSED lines out (Sandbox, 13 Nov 2026)
                         {"q": f"mms_id~{mms_id}", "status": "ALL_WITH_CLOSED", "limit": 100})
        return [p for p in (data.get("po_line") or [])
                if ((p.get("resource_metadata") or {}).get("mms_id") or {}).get("value") == str(mms_id)]

    def get_bib_portfolios(self, mms_id: str) -> List[Dict[str, Any]]:
        data = self._get(f"almaws/v1/bibs/{mms_id}/portfolios", {"limit": 100})
        return data.get("portfolio") or []

    def get_set(self, set_id: str) -> Dict[str, Any]:
        return self._get(f"almaws/v1/conf/sets/{set_id}")

    def get_set_member_ids(self, set_id: str) -> List[str]:
        ids, offset = [], 0
        while True:
            data = self._get(f"almaws/v1/conf/sets/{set_id}/members", {"limit": 100, "offset": offset})
            batch = data.get("member") or []
            ids.extend(str(m["id"]) for m in batch)
            offset += 100
            if not batch or offset >= int(data.get("total_record_count") or 0):
                return ids

    # ---- writes (single attempt) ------------------------------------------
    def invoice_service(self, invoice_id: str, op: str, body: Dict[str, Any]) -> Tuple[int, Dict[str, Any], float]:
        """POST /acq/invoices/{id}?op=<op>. Returns (http_status, body, seconds)."""
        t0 = time.monotonic()
        try:
            resp = self._writer.post(f"almaws/v1/acq/invoices/{invoice_id}", data=body, params={"op": op})
        except (requests.Timeout, requests.ConnectionError) as ex:
            raise WriteOutcomeUnknown(f"{type(ex).__name__} after {time.monotonic() - t0:.1f}s") from ex
        except Exception as ex:
            status = getattr(ex, "status_code", None)
            if status is not None and int(status) < 500:
                # Alma refused the request: nothing changed. Report its code.
                raise WriteRejected(int(status), getattr(ex, "alma_code", ""), str(ex)[:300]) from ex
            # 5xx or anything else: the write may or may not have been applied.
            raise WriteOutcomeUnknown(f"{type(ex).__name__} (HTTP {status}) after "
                                      f"{time.monotonic() - t0:.1f}s") from ex
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        return resp.status_code, payload, round(time.monotonic() - t0, 1)
