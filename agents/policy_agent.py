"""Policy Agent (Person 2): applies EC_POLICY_V2 business rules.

Receives evidence dict from Coordinator and generates draft output containing:
- case_assessment (primary_issue, secondary_issues, case_status, confidence)
- root_cause_analysis (ranked_causes, responsible_parties)
- financial_resolution (currency, recommended_refund_brl)
- resolution_actions
- evidence_ids
"""
from typing import Dict, Any


def apply_policy(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Applies EC_POLICY_V2 priority rules on collected evidence dict."""
    order_id = evidence.get("order_id")
    order_status = evidence.get("order_status")
    
    delivery = evidence.get("delivery_analysis", {})
    payment = evidence.get("payment_reconciliation", {})
    
    delivered_at = delivery.get("delivered_at")
    estimated_delivery_at = delivery.get("estimated_delivery_at")
    delivery_variance_hours = delivery.get("delivery_variance_hours")
    late_handoff_seller_ids = delivery.get("late_handoff_seller_ids", [])
    
    payment_total_brl = payment.get("payment_total_brl", 0.0) or 0.0
    freight_total_brl = payment.get("freight_total_brl", 0.0) or 0.0
    reconciled = payment.get("reconciled")
    payment_ids = evidence.get("affected_entities", {}).get("payment_ids", [])
    item_ids = evidence.get("affected_entities", {}).get("item_ids", [])
    seller_ids = evidence.get("affected_entities", {}).get("seller_ids", [])
    category_names = evidence.get("product_context", {}).get("category_names", [])
    repeat_customer = evidence.get("customer_context", {}).get("repeat_customer", False)
    
    is_late_delivery = False
    if delivered_at and estimated_delivery_at:
        if delivery_variance_hours is not None and delivery_variance_hours > 0:
            is_late_delivery = True
            
    has_split_payment = len(payment_ids) >= 2
    
    primary_issue = None
    cause_code = None
    responsible_parties = []
    recommended_refund_brl = 0.0
    primary_action = None
    
    # Priority Rule Engine (EC_POLICY_V2)
    # 1. canceled_order_paid
    if order_status == "canceled" and payment_total_brl > 0:
        primary_issue = "canceled_order_paid"
        cause_code = "ORDER_CANCELED_AFTER_PAYMENT"
        responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
        recommended_refund_brl = round(payment_total_brl, 2)
        primary_action = "issue_full_refund"

    # 2. unavailable_order_paid
    elif order_status == "unavailable" and payment_total_brl > 0:
        primary_issue = "unavailable_order_paid"
        cause_code = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
        responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
        recommended_refund_brl = round(payment_total_brl, 2)
        primary_action = "issue_full_refund"

    # 3. late_delivery_seller
    elif is_late_delivery and len(late_handoff_seller_ids) > 0:
        primary_issue = "late_delivery_seller"
        cause_code = "SELLER_HANDOFF_AFTER_LIMIT"
        responsible_parties = [
            {"party_type": "seller", "party_id": sid} for sid in late_handoff_seller_ids
        ]
        recommended_refund_brl = round(freight_total_brl, 2)
        primary_action = "refund_freight"

    # 4. late_delivery_logistics
    elif is_late_delivery and len(late_handoff_seller_ids) == 0:
        primary_issue = "late_delivery_logistics"
        cause_code = "CARRIER_DELIVERED_AFTER_ESTIMATE"
        responsible_parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
        recommended_refund_brl = round(freight_total_brl, 2)
        primary_action = "refund_freight"

    # 5. valid_split_payment
    elif has_split_payment and reconciled is True:
        primary_issue = "valid_split_payment"
        cause_code = "MULTIPLE_PAYMENTS_RECONCILED"
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = "explain_valid_split_payment"

    # 6. unsupported_late_claim (Default / Catch-all fallback)
    else:
        primary_issue = "unsupported_late_claim"
        cause_code = "DELIVERY_WITHIN_ESTIMATE"
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = "reject_late_refund"

    # Case Status
    case_status = "action_required" if recommended_refund_brl > 0 else "no_action"
    
    # Secondary Issues (Strict order)
    secondary_issues = []
    if len(item_ids) >= 2:
        secondary_issues.append("multi_item_order")
    if len(seller_ids) >= 2:
        secondary_issues.append("multi_seller_order")
    if has_split_payment:
        secondary_issues.append("split_payment")
    if repeat_customer:
        secondary_issues.append("repeat_customer")
    if len(category_names) >= 2:
        secondary_issues.append("multiple_categories")

    # Secondary Actions (Strict order)
    actions = [primary_action]
    if primary_issue == "late_delivery_seller" or len(late_handoff_seller_ids) > 0:
        actions.append("review_seller_handoff")
    elif primary_issue == "late_delivery_logistics" or is_late_delivery:
        actions.append("review_carrier_delay")

    if recommended_refund_brl > 0:
        actions.append("verify_refund_completion")

    if "multi_seller_order" in secondary_issues:
        actions.append("coordinate_multi_seller_case")

    if has_split_payment and primary_issue != "valid_split_payment":
        actions.append("verify_payment_allocation")

    # Build Evidence IDs
    evidence_ids = []
    if order_id:
        evidence_ids.append(f"order:{order_id}")
    for iid in item_ids:
        evidence_ids.append(f"item:{iid}")
    for pid in payment_ids:
        evidence_ids.append(f"payment:{pid}")
    for party in responsible_parties:
        if party.get("party_type") == "seller":
            evidence_ids.append(f"seller:{party.get('party_id')}")
    if cause_code:
        evidence_ids.append(f"policy:{cause_code}")

    # Deduplicate while preserving order
    seen = set()
    unique_evidence_ids = []
    for eid in evidence_ids:
        if eid not in seen:
            seen.add(eid)
            unique_evidence_ids.append(eid)

    draft_output = {
        "case_id": evidence.get("case_id"),
        "case_assessment": {
            "primary_issue": primary_issue,
            "secondary_issues": secondary_issues,
            "case_status": case_status,
            "confidence": 0.95,
        },
        "affected_entities": evidence.get("affected_entities", {
            "order_ids": [order_id] if order_id else [],
            "item_ids": item_ids,
            "seller_ids": seller_ids,
            "payment_ids": payment_ids,
        }),
        "customer_context": {
            "customer_unique_id": evidence.get("customer_context", {}).get("customer_unique_id"),
            "related_order_ids": evidence.get("customer_context", {}).get("related_order_ids", []),
        },
        "product_context": {
            "product_ids": evidence.get("product_context", {}).get("product_ids", []),
            "category_names": category_names,
        },
        "delivery_analysis": delivery,
        "payment_reconciliation": payment,
        "root_cause_analysis": {
            "ranked_causes": [{"cause_code": cause_code, "rank": 1}],
            "responsible_parties": responsible_parties,
        },
        "evidence_ids": unique_evidence_ids,
        "financial_resolution": {
            "currency": "BRL",
            "recommended_refund_brl": recommended_refund_brl,
        },
        "resolution_actions": actions,
    }

    return draft_output
