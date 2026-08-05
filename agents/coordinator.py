"""Coordinator Agent (Person 1): dispatches to the 4 domain workers and gathers
their results into one evidence dict handed off to Policy Agent (Person 2).

Evidence dict shape (what Person 2's apply_policy(evidence) receives):
{
  "case_id": str,
  "order_id": str,
  "order_exists": bool,
  "order_status": str | None,
  "customer": {customer_unique_id, related_order_ids, repeat_customer},
  "order_product": {item_ids, seller_ids, all_seller_ids, product_ids,
                     category_names, multi_item_order, multi_seller_order,
                     multiple_categories},
  "payment": {payment_ids, payment_types, item_total_brl, freight_total_brl,
              expected_total_brl, payment_total_brl, difference_brl,
              reconciled, split_payment, valid_split_payment},
  "delivery": {delivered_at, estimated_delivery_at, carrier_handoff_at,
               delivery_variance_hours, seller_handoff_analysis,
               late_handoff_seller_ids, late_delivery},
}
"""
from .data_loader import OlistData
from .customer_agent import analyze_customer
from .order_product_agent import analyze_order_product
from .payment_agent import analyze_payment
from .delivery_agent import analyze_delivery


def gather_evidence(data: OlistData, case_input: dict) -> dict:
    case_id = case_input["case_id"]
    order_id = case_input["customer_request"]["claimed_order_id"]

    order_product = analyze_order_product(data, order_id)
    items_df = order_product.pop("items_df", None)

    customer = analyze_customer(data, order_id)
    payment = analyze_payment(data, order_id, items_df)
    delivery = analyze_delivery(data, order_id, items_df)

    return {
        "case_id": case_id,
        "order_id": order_id,
        "order_exists": order_product["order_exists"],
        "order_status": order_product["order_status"],
        "customer": customer,
        "order_product": order_product,
        "payment": payment,
        "delivery": delivery,
    }
