# Central Library / Rialto invoice pilot

The user requested two **discovery populations**, both in Alma Sandbox:

1. Central Library invoices for Rialto electronic books.
2. Central Library invoices for Rialto physical books.

These criteria do not by themselves define eligibility to mark an invoice paid.
Keep the whole population, open-invoice candidates and the selected mutation sample
as distinct sets with separate counts.

Resolve codes through configuration/vendor APIs. A platform name can differ from
the vendor's display name. Prefer a documented exact code lookup after resolving
that identity; an empty vendor-name search is not proof that the vendor is absent.
Do not embed real institution codes or invoice IDs in generic skill instructions.

Invoice discovery uses documented owner and base/workflow filters plus the vendor
search field supported by that endpoint. Confirm returned owner/vendor. Fetch and
page invoice lines, then resolve linked PO-lines as necessary to verify book type
and electronic/physical format. Do not assume every invoice contains one format,
every charge line has a PO-line, or every electronic order is a book.

Mixed-format and unresolved invoices remain review items, not members of either
automatic-payment sample. If a report is bounded or truncated, state this beside
the counts. A zero result under an unverified filter is not an empty business set.

Before testing the current bulk processor, review payment status parsing, paid/open
handling, approval readiness, duplicate prevention and final-state verification.
Use synthetic unit fixtures for corrections and separate live Sandbox acceptance.

The user reviews a small sample's result before sending the set to the acquisitions
librarian. Wider testing/production work waits for her feedback and later direction.
Prepare a review artifact; do not send it to anyone without explicit authorization.
