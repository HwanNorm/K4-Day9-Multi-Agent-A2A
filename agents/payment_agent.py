"""Payment Agent (Person 1): sums payment rows and reconciles against item+freight.

Owns: payment_reconciliation block and the split_payment / valid_split_payment signal.
Per README section 4: for orders with no item rows, expected_total_brl,
difference_brl and reconciled must be null.
"""
from .data_loader import OlistData

MAX_PAYMENT_IDS = 5
RECONCILE_TOLERANCE_BRL = 0.10


def analyze_payment(data: OlistData, order_id: str, items_df) -> dict:
    payments = data.get_payments(order_id)

    payment_ids = [
        f"{order_id}:{seq}" for seq in payments["payment_sequential"].tolist()
    ]
    payment_types = list(dict.fromkeys(payments["payment_type"].tolist()))
    payment_total_brl = round(float(payments["payment_value"].sum()), 2)

    has_items = items_df is not None and not items_df.empty
    if has_items:
        item_total_brl = round(float(items_df["price"].sum()), 2)
        freight_total_brl = round(float(items_df["freight_value"].sum()), 2)
        expected_total_brl = round(item_total_brl + freight_total_brl, 2)
        difference_brl = round(payment_total_brl - expected_total_brl, 2)
        reconciled = abs(difference_brl) <= RECONCILE_TOLERANCE_BRL
    else:
        item_total_brl = 0.0
        freight_total_brl = 0.0
        expected_total_brl = None
        difference_brl = None
        reconciled = None

    return {
        "payment_ids": payment_ids[:MAX_PAYMENT_IDS],
        "payment_types": payment_types,
        "item_total_brl": item_total_brl,
        "freight_total_brl": freight_total_brl,
        "expected_total_brl": expected_total_brl,
        "payment_total_brl": payment_total_brl,
        "difference_brl": difference_brl,
        "reconciled": reconciled,
        "split_payment": len(payments) >= 2,
        "valid_split_payment": len(payments) >= 2 and reconciled is True,
    }
