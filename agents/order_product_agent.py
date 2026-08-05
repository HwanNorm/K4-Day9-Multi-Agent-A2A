"""Order & Product Agent (Person 1): resolves order/item/seller/product/category facts.

Owns: affected_entities.order_ids/item_ids/seller_ids, product_context, and the
multi_item_order / multi_seller_order / multiple_categories secondary-issue signals.
"""
from .data_loader import OlistData

MAX_ITEMS = 5
MAX_SELLERS = 3
MAX_PRODUCTS = 5
MAX_CATEGORIES = 5


def analyze_order_product(data: OlistData, order_id: str) -> dict:
    order = data.get_order(order_id)
    if order is None:
        return {
            "order_exists": False,
            "order_status": None,
            "item_ids": [],
            "seller_ids": [],
            "product_ids": [],
            "category_names": [],
            "multi_item_order": False,
            "multi_seller_order": False,
            "multiple_categories": False,
        }

    items = data.get_items(order_id)

    item_ids = [f"{order_id}:{iid}" for iid in items["order_item_id"].tolist()]
    seller_ids = list(dict.fromkeys(items["seller_id"].tolist()))
    product_ids = list(dict.fromkeys(items["product_id"].tolist()))

    category_names = []
    for pid in product_ids:
        prod = data.get_product(pid)
        if prod is not None and isinstance(prod.get("product_category_name_english"), str):
            cat = prod["product_category_name_english"]
            if cat not in category_names:
                category_names.append(cat)

    return {
        "order_exists": True,
        "order_status": order["order_status"],
        "item_ids": item_ids[:MAX_ITEMS],
        "seller_ids": seller_ids[:MAX_SELLERS],
        "all_seller_ids": seller_ids,
        "product_ids": product_ids[:MAX_PRODUCTS],
        "category_names": category_names[:MAX_CATEGORIES],
        "multi_item_order": len(items) >= 2,
        "multi_seller_order": len(seller_ids) >= 2,
        "multiple_categories": len(category_names) >= 2,
        "items_df": items,
    }
