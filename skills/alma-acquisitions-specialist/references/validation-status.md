# API validation status

Official documentation checked: **2026-11-08**. This is separate from live testing.

The last-tested date identifies an observation, not an expiry date or a guarantee. A partial pass covers only its listed scope.

See [the redacted live report](validation-evidence.json) for per-operation timestamps and assertions. The supporting libraries GET is outside the Acquisitions catalog.

| Operation | Validation | Last tested (Asia/Jerusalem) | Result |
|---|---|---|---|
| `GET /almaws/v1/acq/currencies` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/fiscal-periods` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/funds` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/funds` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/funds/{fund_id}/transactions` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/funds/{fund_id}/transactions` | not_live_tested | Not tested | — |
| `DELETE /almaws/v1/acq/funds/{fund_id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/funds/{fund_id}` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/funds/{fund_id}` | not_live_tested | Not tested | — |
| `PUT /almaws/v1/acq/funds/{fund_id}` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/invoices` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/invoices/` | sandbox_tested_partial | 2026-11-08T09:46:45+02:00 | passed_in_tested_scope |
| `GET /almaws/v1/acq/invoices/{invoice_id}/attachments/{attachment_id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/invoices/{invoice_id}` | sandbox_tested_partial | 2026-11-08T09:46:46+02:00 | passed_in_tested_scope |
| `POST /almaws/v1/acq/invoices/{invoice_id}` | not_live_tested | Not tested | — |
| `PUT /almaws/v1/acq/invoices/{invoice_id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/invoices/{invoice_id}/attachments` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/invoices/{invoice_id}/attachments` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/invoices/{invoice_id}/lines` | sandbox_tested_partial | 2026-11-08T09:46:46+02:00 | passed_in_tested_scope |
| `POST /almaws/v1/acq/invoices/{invoice_id}/lines` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/invoices/{invoice_id}/lines/{invoice_line_id}` | not_live_tested | Not tested | — |
| `PUT /almaws/v1/acq/invoices/{invoice_id}/lines/{invoice_line_id}` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/licenses` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/licenses/` | not_live_tested | Not tested | — |
| `DELETE /almaws/v1/acq/licenses/{license_code}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/licenses/{license_code}` | not_live_tested | Not tested | — |
| `PUT /almaws/v1/acq/licenses/{license_code}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/licenses/{license_code}/attachments` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/licenses/{license_code}/attachments` | not_live_tested | Not tested | — |
| `DELETE /almaws/v1/acq/licenses/{license_code}/attachments/{attachment_id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/licenses/{license_code}/attachments/{attachment_id}` | not_live_tested | Not tested | — |
| `PUT /almaws/v1/acq/licenses/{license_code}/attachments/{attachment_id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/licenses/{license_code}/amendments` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/licenses/{license_code}/amendments` | not_live_tested | Not tested | — |
| `DELETE /almaws/v1/acq/licenses/{license_code}/amendments/{amendment_code}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/licenses/{license_code}/amendments/{amendment_code}` | not_live_tested | Not tested | — |
| `PUT /almaws/v1/acq/licenses/{license_code}/amendments/{amendment_code}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/po-lines` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/po-lines` | not_live_tested | Not tested | — |
| `DELETE /almaws/v1/acq/po-lines/{po_line_id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/po-lines/{po_line_id}` | sandbox_tested_partial | 2026-11-08T09:46:46+02:00 | passed_in_tested_scope |
| `PUT /almaws/v1/acq/po-lines/{po_line_id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/po-lines/{po_line_id}/items` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/po-lines/{po_line_id}/items` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/po-lines/{po_line_id}/items/{item_id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/purchase-requests/` | not_live_tested | Not tested | — |
| `DELETE /almaws/v1/acq/purchase-requests/{id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/purchase-requests/{id}` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/purchase-requests/{id}` | not_live_tested | Not tested | — |
| `PUT /almaws/v1/acq/purchase-requests/{id}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/test` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/test` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/vendors` | not_live_tested | Not tested | — |
| `POST /almaws/v1/acq/vendors` | not_live_tested | Not tested | — |
| `DELETE /almaws/v1/acq/vendors/{vendorCode}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/vendors/{vendorCode}` | sandbox_tested_partial | 2026-11-08T09:46:45+02:00 | passed_in_tested_scope |
| `PUT /almaws/v1/acq/vendors/{vendorCode}` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/vendors/{vendorCode}/invoices` | not_live_tested | Not tested | — |
| `GET /almaws/v1/acq/vendors/{vendorCode}/po-lines` | not_live_tested | Not tested | — |

## Tested scope

- `GET /almaws/v1/acq/invoices/`: Vendor-code query, owner, ACTIVE and brief filters on one bounded page; not all query combinations or pages.
- `GET /almaws/v1/acq/invoices/{invoice_id}`: One invoice detail: nested payment-status shape; no mutation or workflow transition.
- `GET /almaws/v1/acq/invoices/{invoice_id}/lines`: Invoice-line list shape for one invoice and one bounded page; no line mutations.
- `GET /almaws/v1/acq/po-lines/{po_line_id}`: One linked PO-line: type/material/owner/status fields present; no receiving or activation.
- `GET /almaws/v1/acq/vendors/{vendorCode}`: Exact lookup of one supplied vendor code.
