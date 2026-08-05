"""Delivery Agent (Person 1): computes delivery variance and per-seller handoff variance.

Owns: delivery_analysis block. Per README section 4:
  delivery_variance_hours = order_delivered_customer_date - order_estimated_delivery_date
  handoff_variance_hours  = order_delivered_carrier_date - earliest shipping_limit_date (per seller)
Positive variance means late.
"""
import pandas as pd
from .data_loader import OlistData

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _fmt(ts):
    if ts is None or pd.isna(ts):
        return None
    return ts.strftime(TS_FORMAT)


def _hours_between(later, earlier):
    if later is None or earlier is None or pd.isna(later) or pd.isna(earlier):
        return None
    return round((later - earlier).total_seconds() / 3600, 2)


def analyze_delivery(data: OlistData, order_id: str, items_df) -> dict:
    order = data.get_order(order_id)
    if order is None:
        return {
            "delivered_at": None,
            "estimated_delivery_at": None,
            "carrier_handoff_at": None,
            "delivery_variance_hours": None,
            "seller_handoff_analysis": [],
            "late_handoff_seller_ids": [],
            "late_delivery": False,
        }

    delivered_at = order["order_delivered_customer_date"]
    estimated_at = order["order_estimated_delivery_date"]
    carrier_at = order["order_delivered_carrier_date"]

    delivery_variance_hours = _hours_between(delivered_at, estimated_at)
    late_delivery = delivery_variance_hours is not None and delivery_variance_hours > 0

    seller_handoff_analysis = []
    late_handoff_seller_ids = []

    if items_df is not None and not items_df.empty:
        for seller_id, group in items_df.groupby("seller_id", sort=False):
            shipping_limit_at = group["shipping_limit_date"].min()
            handoff_variance_hours = _hours_between(carrier_at, shipping_limit_at)
            late_handoff = handoff_variance_hours is not None and handoff_variance_hours > 0
            seller_handoff_analysis.append(
                {
                    "seller_id": seller_id,
                    "shipping_limit_at": _fmt(shipping_limit_at),
                    "handoff_variance_hours": handoff_variance_hours,
                    "late_handoff": late_handoff,
                }
            )
            if late_handoff:
                late_handoff_seller_ids.append(seller_id)

    return {
        "delivered_at": _fmt(delivered_at),
        "estimated_delivery_at": _fmt(estimated_at),
        "carrier_handoff_at": _fmt(carrier_at),
        "delivery_variance_hours": delivery_variance_hours,
        "seller_handoff_analysis": seller_handoff_analysis,
        "late_handoff_seller_ids": late_handoff_seller_ids,
        "late_delivery": late_delivery,
    }
