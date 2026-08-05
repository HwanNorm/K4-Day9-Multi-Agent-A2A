"""Verifier Agent (Person 2): validates output schema, array bounds, evidence IDs, and nulls.

Ensures strict compliance with README section 6 output schema before saving JSON.
"""
import re
from typing import Dict, Any

VALID_EVIDENCE_PREFIXES = ("order:", "item:", "payment:", "seller:", "policy:")


def verify(draft_output: Dict[str, Any]) -> Dict[str, Any]:
    """Verifies and sanitizes draft_output dict to produce final_json."""
    output = dict(draft_output)
    # Internal Policy Agent <-> LLM cross-check metadata never belongs in the
    # schema-compliant output file.
    output.pop("_llm_meta", None)

    # 1. Enforce Case Assessment limits and confidence bounds
    assessment = output.get("case_assessment", {})
    confidence = assessment.get("confidence", 0.95)
    assessment["confidence"] = max(0.0, min(1.0, float(confidence)))
    output["case_assessment"] = assessment

    # 2. Enforce Affected Entities Array Limits
    entities = output.get("affected_entities", {})
    entities["order_ids"] = entities.get("order_ids", [])[:5]
    entities["item_ids"] = entities.get("item_ids", [])[:5]
    entities["seller_ids"] = entities.get("seller_ids", [])[:3]
    entities["payment_ids"] = entities.get("payment_ids", [])[:5]
    output["affected_entities"] = entities

    # 3. Enforce Customer Context Array Limits
    cust = output.get("customer_context", {})
    cust["related_order_ids"] = cust.get("related_order_ids", [])[:5]
    output["customer_context"] = cust

    # 4. Enforce Product Context Array Limits
    prod = output.get("product_context", {})
    prod["product_ids"] = prod.get("product_ids", [])[:5]
    prod["category_names"] = prod.get("category_names", [])[:5]
    output["product_context"] = prod

    # 5. Enforce Delivery Analysis Array Limits & Float Rounding
    delivery = output.get("delivery_analysis", {})
    if delivery.get("delivery_variance_hours") is not None:
        delivery["delivery_variance_hours"] = round(float(delivery["delivery_variance_hours"]), 2)
    seller_analysis = delivery.get("seller_handoff_analysis", [])
    for s in seller_analysis:
        if s.get("handoff_variance_hours") is not None:
            s["handoff_variance_hours"] = round(float(s["handoff_variance_hours"]), 2)
    delivery["late_handoff_seller_ids"] = delivery.get("late_handoff_seller_ids", [])[:3]
    output["delivery_analysis"] = delivery

    # 6. Enforce Payment Reconciliation Null Handling & Float Rounding
    payment = output.get("payment_reconciliation", {})
    for key in ["item_total_brl", "freight_total_brl", "payment_total_brl"]:
        if payment.get(key) is not None:
            payment[key] = round(float(payment[key]), 2)
    for key in ["expected_total_brl", "difference_brl"]:
        if payment.get(key) is not None:
            payment[key] = round(float(payment[key]), 2)
        else:
            payment[key] = None
    output["payment_reconciliation"] = payment

    # 7. Enforce Root Cause Analysis Array Limits
    rca = output.get("root_cause_analysis", {})
    rca["ranked_causes"] = rca.get("ranked_causes", [])[:3]
    rca["responsible_parties"] = rca.get("responsible_parties", [])[:3]
    output["root_cause_analysis"] = rca

    # 8. Validate & Limit Evidence IDs
    raw_ev_ids = output.get("evidence_ids", [])
    valid_ev_ids = []
    for eid in raw_ev_ids:
        if isinstance(eid, str) and eid.startswith(VALID_EVIDENCE_PREFIXES):
            valid_ev_ids.append(eid)
    output["evidence_ids"] = valid_ev_ids[:20]

    # 9. Financial Resolution Float Rounding
    fin = output.get("financial_resolution", {})
    if fin.get("recommended_refund_brl") is not None:
        fin["recommended_refund_brl"] = round(float(fin["recommended_refund_brl"]), 2)
    output["financial_resolution"] = fin

    # 10. Resolution Actions Array Limits
    output["resolution_actions"] = output.get("resolution_actions", [])[:5]

    return output
