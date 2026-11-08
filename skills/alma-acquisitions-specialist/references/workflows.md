# Acquisitions workflow map

This is a domain orientation, not a validated universal execution sequence.
Consult coverage-and-evidence.md before acting on a specific workflow.

## Connect the records and the business process

| Area | Domain questions to answer | API/tooling route |
|---|---|---|
| Ordering and PO-lines | What is ordered, who owns it, how is it acquired, and is the order one-time or ongoing? | PO-line reads and documented update/cancellation operations; existing project order workflow |
| Vendors | Which exact supplier/account supplies or invoices the material? Is the platform name the vendor's display name? | Vendor lookup plus invoice/PO vendor/account fields |
| Funding | Which fund/fiscal period/distribution is involved, and what financial effects are intended? | Official fund/transaction contracts and linked record data; implementation and live workflow coverage are incomplete |
| Physical receiving | Which ordered items/copies are received, and what department/work-order effects are intended? | PO-line item receiving and any documented follow-on scan-in; these are writes, not lookup steps |
| Electronic resources | Which order type and resources are involved, and what activation state is required? | PO-line plus relevant Electronic/Bibliographic APIs; activation is not established by this skill's current tests |
| Invoicing | Is this a new invoice or an existing one? Which lines link to which orders? | Invoice and invoice-line reads; creation/update only for the requested business operation |
| Approval and ERP/payment | Which review rules, approval state and ERP/export/payment steps apply? | Invoice service contracts and current invoice/payment/workflow state |
| Closure | Is the desired result a closed invoice, payment recorded, a closed PO-line, or several of these? | Separate read-back assertions for each intended entity/state |

Ordering, receiving/activation and invoicing are related but are not one fixed chain
for every institution and order type. Trace the actual project scenario and settings.
Do not use a historical physical-book workflow as an electronic-resource prescription.

## Ownership and classification

Invoice owner, PO-line owner, receiving library and resource location have distinct
roles. A display label in one response is not proof that all linked records use it.
Verify each ownership fact needed by the business rule.

Electronic/physical format and book/serial/other material classification require
appropriate linked metadata. Vendor name or a title substring alone is insufficient.
An invoice can contain several order lines and formats; invoice-wide changes affect
the invoice, not just the line that caused it to appear in a discovery result.

## Search and population size

Use the endpoint's documented query fields and separate filters; validate returned
records against the intended predicate. Preserve server population totals separately
from page lengths or wrapper-generated counts. Report bounded/partial coverage.
Missing, mixed, unlinked or unclassified records need a visible review category.

The generic domain guidance does not choose the user's business eligibility rule.
Keep campaign-specific codes, samples and approval gates in the owning project.
