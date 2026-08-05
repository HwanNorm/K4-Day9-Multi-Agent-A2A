"""Customer Agent (Person 1): resolves customer identity and order history.

Owns: affected order's customer_unique_id + related_order_ids (history only,
never merged into affected_entities per README section 3).
"""
from .data_loader import OlistData

MAX_RELATED_ORDERS = 5


def analyze_customer(data: OlistData, order_id: str) -> dict:
    order = data.get_order(order_id)
    if order is None:
        return {"customer_unique_id": None, "related_order_ids": []}

    customer = data.get_customer(order["customer_id"])
    if customer is None:
        return {"customer_unique_id": None, "related_order_ids": []}

    customer_unique_id = customer["customer_unique_id"]
    related = data.get_related_orders(customer_unique_id, exclude_order_id=order_id)
    related_ids = related.sort_values("order_purchase_timestamp")["order_id"].tolist()

    return {
        "customer_unique_id": customer_unique_id,
        "related_order_ids": related_ids[:MAX_RELATED_ORDERS],
        "repeat_customer": len(related_ids) > 0,
    }
