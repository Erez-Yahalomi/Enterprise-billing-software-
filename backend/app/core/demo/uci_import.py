"""Optional importer for the UCI "Online Retail II" public dataset (spec section 12).

This does not ship the dataset itself (it isn't ours to redistribute). Download the CSV
from the UCI Machine Learning Repository and point UCI_CSV_PATH at it, or pass a path
explicitly, to import a reproducible subset of real transactions mapped onto the demo
tenant. Without a file present, this is a no-op — the rest of the demo (synthetic data)
works fully on its own.

Mapping (spec section 12):
    CustomerID   -> Customer
    InvoiceNo    -> Invoice
    Quantity * UnitPrice -> Charge (invoice line item, in cents)
    InvoiceDate  -> Billing date (period start/end)
    Country      -> Customer region
"""

import csv
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.billing.models import Invoice, InvoiceLineItem
from app.core.models import WorkspaceType, gen_id
from app.customers.models import Customer

TENANT_ID = "DEMO"
WORKSPACE = WorkspaceType.demo

DEFAULT_ROW_LIMIT = 100_000


def import_uci_sample(db: Session, csv_path: str | None = None, row_limit: int = DEFAULT_ROW_LIMIT) -> int:
    path = Path(csv_path or os.environ.get("UCI_CSV_PATH", "data/uci/online_retail_II.csv"))
    if not path.exists():
        # No dataset provided — skip quietly, this is explicitly optional.
        return 0

    customers_by_uci_id: dict[str, Customer] = {}
    invoices_by_no: dict[str, Invoice] = {}
    line_items_by_invoice: dict[str, list[InvoiceLineItem]] = defaultdict(list)

    with path.open(newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= row_limit:
                break
            uci_customer_id = (row.get("Customer ID") or row.get("CustomerID") or "").strip()
            invoice_no = (row.get("Invoice") or row.get("InvoiceNo") or "").strip()
            if not uci_customer_id or not invoice_no:
                continue

            customer = customers_by_uci_id.get(uci_customer_id)
            if customer is None:
                customer = Customer(
                    tenant_id=TENANT_ID, workspace_type=WORKSPACE,
                    name=f"UCI Customer {uci_customer_id}",
                    email=f"uci-{uci_customer_id}@example.invalid",
                    country=row.get("Country"),
                    status="active",
                )
                db.add(customer)
                db.flush()
                customers_by_uci_id[uci_customer_id] = customer

            invoice = invoices_by_no.get(invoice_no)
            if invoice is None:
                try:
                    invoice_date = datetime.strptime(row["InvoiceDate"], "%m/%d/%Y %H:%M").replace(tzinfo=timezone.utc)
                except (KeyError, ValueError):
                    invoice_date = datetime.now(timezone.utc)
                invoice = Invoice(
                    tenant_id=TENANT_ID, workspace_type=WORKSPACE,
                    customer_id=customer.id, subscription_id="uci-import",
                    period_start=invoice_date.date(), period_end=invoice_date.date(),
                    status="paid", subtotal_cents=0,
                )
                db.add(invoice)
                db.flush()
                invoices_by_no[invoice_no] = invoice

            try:
                quantity = float(row.get("Quantity", 0))
                unit_price = float(row.get("Price") or row.get("UnitPrice") or 0)
            except ValueError:
                continue
            amount_cents = round(quantity * unit_price * 100)
            if amount_cents == 0:
                continue

            line_item = InvoiceLineItem(
                tenant_id=TENANT_ID, workspace_type=WORKSPACE,
                invoice_id=invoice.id,
                description=(row.get("Description") or "UCI transaction line")[:255],
                kind="uci_transaction",
                amount_cents=amount_cents,
            )
            db.add(line_item)
            invoice.subtotal_cents += amount_cents

    db.commit()
    return len(invoices_by_no)
