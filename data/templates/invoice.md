# Invoice {{invoice_id}} — {{invoice_type}}

**{{legal_name}}**
{{street}}, {{city}}, {{region}} {{postal_code}}
{{phone_display}} · {{email}}
{{sellers_permit_line}}

| | |
|---|---|
| Bill to | {{customer_name}}{{customer_company}} |
| Job | {{job_id}} |
| Quote | {{quote_id}} |
| Issued | {{issued}} |
| Due | **{{due}}** ({{payment_terms}}) |

## Charges

| Description | Qty | Rate | Amount |
|---|---:|---:|---:|
{{line_items_rows}}

{{change_orders_section}}

| | |
|---:|---:|
| Subtotal | {{subtotal}} |
| Deposit credit | -{{deposit_credit}} |
| {{tax_line_label}} | {{tax}} |
| **Total due** | **{{total_due}}** |

{{tax_note}}

Payment methods: {{payment_methods}}
{{late_fee_line}}

Questions about this invoice: {{email}} · {{phone_display}}
