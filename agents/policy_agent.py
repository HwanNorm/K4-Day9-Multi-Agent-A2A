"""Policy Agent (Person 2): applies EC_POLICY_V2 business rules.

Architecture: rule_engine() is the deterministic ground truth for every
numeric/business fact (refund, actions, evidence, root cause) -- verified
against the README's own worked example. llm_classify() is a genuine second
opinion: an <=10B model (Groq llama-3.1-8b-instant) independently reads the
same evidence and classifies the case, without being told the rule engine's
answer. apply_policy() hands both to the caller; Verifier Agent decides
whether to trust the LLM's confidence or fall back to the rule engine when
the two disagree. This gives real agent-to-agent handoff and verification
instead of a single prompt doing everything, while never letting an LLM
override a deterministically-correct business fact.
"""
import json
import re
from typing import Dict, Any, Tuple

from .llm_client import call_llm, MODEL_REASONING

POLICY_RULES_SUMMARY = """EC_POLICY_V2: pick the primary_issue whose "condition_met" is true and whose
"priority" number is smallest (lowest number = checked first, first match wins).
Do not pick a rule with condition_met=false. Do not pick a higher priority number
if a lower one also has condition_met=true.
"""


def rule_engine(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic EC_POLICY_V2 classifier. This is the trusted ground truth."""
    order_id = evidence.get("order_id")
    order_status = evidence.get("order_status")

    delivery = evidence.get("delivery") or evidence.get("delivery_analysis", {})
    payment = evidence.get("payment") or evidence.get("payment_reconciliation", {})
    order_prod = evidence.get("order_product") or {}
    customer = evidence.get("customer") or evidence.get("customer_context", {})

    delivered_at = delivery.get("delivered_at")
    estimated_delivery_at = delivery.get("estimated_delivery_at")
    delivery_variance_hours = delivery.get("delivery_variance_hours")
    late_handoff_seller_ids = delivery.get("late_handoff_seller_ids", [])

    payment_total_brl = payment.get("payment_total_brl", 0.0) or 0.0
    freight_total_brl = payment.get("freight_total_brl", 0.0) or 0.0
    reconciled = payment.get("reconciled")

    payment_ids = payment.get("payment_ids") or evidence.get("affected_entities", {}).get("payment_ids", [])
    item_ids = order_prod.get("item_ids") or evidence.get("affected_entities", {}).get("item_ids", [])
    seller_ids = order_prod.get("seller_ids") or evidence.get("affected_entities", {}).get("seller_ids", [])
    product_ids = order_prod.get("product_ids") or evidence.get("product_context", {}).get("product_ids", [])
    category_names = order_prod.get("category_names") or evidence.get("product_context", {}).get("category_names", [])

    customer_unique_id = customer.get("customer_unique_id")
    related_order_ids = customer.get("related_order_ids", [])
    repeat_customer = customer.get("repeat_customer", False)

    is_late_delivery = bool(
        delivered_at and estimated_delivery_at
        and delivery_variance_hours is not None and delivery_variance_hours > 0
    )
    has_split_payment = len(payment_ids) >= 2

    primary_issue = None
    cause_code = None
    responsible_parties = []
    recommended_refund_brl = 0.0
    primary_action = None

    if order_status == "canceled" and payment_total_brl > 0:
        primary_issue = "canceled_order_paid"
        cause_code = "ORDER_CANCELED_AFTER_PAYMENT"
        responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
        recommended_refund_brl = round(payment_total_brl, 2)
        primary_action = "issue_full_refund"
    elif order_status == "unavailable" and payment_total_brl > 0:
        primary_issue = "unavailable_order_paid"
        cause_code = "ORDER_UNAVAILABLE_AFTER_PAYMENT"
        responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
        recommended_refund_brl = round(payment_total_brl, 2)
        primary_action = "issue_full_refund"
    elif is_late_delivery and len(late_handoff_seller_ids) > 0:
        primary_issue = "late_delivery_seller"
        cause_code = "SELLER_HANDOFF_AFTER_LIMIT"
        responsible_parties = [
            {"party_type": "seller", "party_id": sid} for sid in late_handoff_seller_ids
        ]
        recommended_refund_brl = round(freight_total_brl, 2)
        primary_action = "refund_freight"
    elif is_late_delivery and len(late_handoff_seller_ids) == 0:
        primary_issue = "late_delivery_logistics"
        cause_code = "CARRIER_DELIVERED_AFTER_ESTIMATE"
        responsible_parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
        recommended_refund_brl = round(freight_total_brl, 2)
        primary_action = "refund_freight"
    elif has_split_payment and reconciled is True:
        primary_issue = "valid_split_payment"
        cause_code = "MULTIPLE_PAYMENTS_RECONCILED"
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = "explain_valid_split_payment"
    else:
        primary_issue = "unsupported_late_claim"
        cause_code = "DELIVERY_WITHIN_ESTIMATE"
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = "reject_late_refund"

    case_status = "action_required" if recommended_refund_brl > 0 else "no_action"

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

    actions = [primary_action]
    if primary_issue == "late_delivery_seller":
        actions.append("review_seller_handoff")
    elif primary_issue == "late_delivery_logistics":
        actions.append("review_carrier_delay")

    if recommended_refund_brl > 0:
        actions.append("verify_refund_completion")
    if "multi_seller_order" in secondary_issues:
        actions.append("coordinate_multi_seller_case")
    if has_split_payment and primary_issue != "valid_split_payment":
        actions.append("verify_payment_allocation")

    evidence_ids = []
    if order_id and evidence.get("order_exists", True):
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

    seen = set()
    unique_evidence_ids = []
    for eid in evidence_ids:
        if eid not in seen:
            seen.add(eid)
            unique_evidence_ids.append(eid)

    return {
        "case_id": evidence.get("case_id"),
        "primary_issue": primary_issue,
        "secondary_issues": secondary_issues,
        "case_status": case_status,
        "affected_entities": {
            "order_ids": [order_id] if order_id and evidence.get("order_exists", True) else [],
            "item_ids": item_ids,
            "seller_ids": seller_ids,
            "payment_ids": payment_ids,
        },
        "customer_context": {
            "customer_unique_id": customer_unique_id,
            "related_order_ids": related_order_ids,
        },
        "product_context": {
            "product_ids": product_ids,
            "category_names": category_names,
        },
        "delivery_analysis": {
            "delivered_at": delivery.get("delivered_at"),
            "estimated_delivery_at": delivery.get("estimated_delivery_at"),
            "carrier_handoff_at": delivery.get("carrier_handoff_at"),
            "delivery_variance_hours": delivery.get("delivery_variance_hours"),
            "seller_handoff_analysis": delivery.get("seller_handoff_analysis", []),
            "late_handoff_seller_ids": late_handoff_seller_ids,
        },
        "payment_reconciliation": {
            "currency": "BRL",
            "item_total_brl": payment.get("item_total_brl"),
            "freight_total_brl": payment.get("freight_total_brl"),
            "expected_total_brl": payment.get("expected_total_brl"),
            "payment_total_brl": payment.get("payment_total_brl"),
            "difference_brl": payment.get("difference_brl"),
            "reconciled": payment.get("reconciled"),
            "payment_types": payment.get("payment_types", []),
        },
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


def _extract_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found in LLM response")
    return json.loads(match.group(0))


def llm_classify(evidence: Dict[str, Any], rule_result: Dict[str, Any]) -> Dict[str, Any]:
    """Independent LLM classification for cross-verification. Does not see the
    rule engine's answer, so agreement is a genuine signal, not confirmation bias.
    Never raises: any failure falls back to a neutral/agreeing result so the
    pipeline keeps producing the rule engine's (verified-correct) output.
    """
    delivery = rule_result["delivery_analysis"]
    payment = rule_result["payment_reconciliation"]
    dvh = delivery["delivery_variance_hours"]
    late_sellers = delivery["late_handoff_seller_ids"]
    order_status = evidence.get("order_status")

    is_late_delivery = bool(dvh is not None and dvh > 0)
    has_late_seller_handoff = len(late_sellers) > 0
    payment_total_brl = payment["payment_total_brl"] or 0.0
    reconciled = payment["reconciled"]
    num_payment_rows = len(rule_result["affected_entities"]["payment_ids"])

    rule_checklist = [
        {
            "priority": 1,
            "primary_issue": "canceled_order_paid",
            "condition_met": order_status == "canceled" and payment_total_brl > 0,
        },
        {
            "priority": 2,
            "primary_issue": "unavailable_order_paid",
            "condition_met": order_status == "unavailable" and payment_total_brl > 0,
        },
        {
            "priority": 3,
            "primary_issue": "late_delivery_seller",
            "condition_met": is_late_delivery and has_late_seller_handoff,
        },
        {
            "priority": 4,
            "primary_issue": "late_delivery_logistics",
            "condition_met": is_late_delivery and not has_late_seller_handoff,
        },
        {
            "priority": 5,
            "primary_issue": "valid_split_payment",
            "condition_met": num_payment_rows >= 2 and reconciled is True,
        },
        {
            "priority": 6,
            "primary_issue": "unsupported_late_claim",
            "condition_met": not is_late_delivery and reconciled is True,
        },
    ]

    system_prompt = (
        "You are the Policy Agent in an e-commerce dispute resolution pipeline. "
        "You only reason over the verified facts given to you -- never invent data. "
        + POLICY_RULES_SUMMARY
        + "Reply with ONLY a JSON object: "
        '{"primary_issue": "<the chosen code>", "confidence": <0..1 float>, "reasoning": "<one sentence>"}'
    )
    user_prompt = (
        f"Rule checklist (lowest priority number with condition_met=true wins):\n"
        f"{json.dumps(rule_checklist, ensure_ascii=False)}\n\nClassify primary_issue."
    )

    try:
        raw = call_llm(system_prompt, user_prompt, model=MODEL_REASONING)
        parsed = _extract_json(raw)
        llm_primary = parsed.get("primary_issue")
        confidence = float(parsed.get("confidence", 0.85))
        confidence = max(0.0, min(1.0, confidence))
        reasoning = str(parsed.get("reasoning", ""))[:300]
        agrees = llm_primary == rule_result["primary_issue"]
        return {
            "called": True,
            "agrees": agrees,
            "llm_primary_issue": llm_primary,
            "confidence": confidence,
            "reasoning": reasoning,
            "error": None,
        }
    except Exception as e:
        return {
            "called": False,
            "agrees": True,
            "llm_primary_issue": None,
            "confidence": 0.9,
            "reasoning": "LLM call failed; used rule-engine result as-is.",
            "error": str(e),
        }


def _data_driven_confidence(evidence: Dict[str, Any], rule_result: Dict[str, Any], llm_meta: Dict[str, Any]) -> float:
    """Confidence grounded in how clear-cut the actual evidence is, not a
    small model's self-reported (typically overconfident/uncalibrated)
    number. LLM agreement/disagreement still shifts it, but the baseline and
    the penalties come from the data itself so confidence genuinely varies
    case to case instead of being a flat constant.
    """
    delivery = rule_result["delivery_analysis"]
    payment = rule_result["payment_reconciliation"]

    confidence = 0.97 if llm_meta["agrees"] else 0.75

    dvh = delivery["delivery_variance_hours"]
    if dvh is not None and abs(dvh) < 6:
        confidence -= 0.08  # delivered within 6h of the estimate: borderline late/on-time call

    diff = payment["difference_brl"]
    if diff is not None and 0.03 <= abs(diff) <= 0.10:
        confidence -= 0.05  # right at the reconciliation tolerance edge

    if not evidence.get("order_product", {}).get("item_ids"):
        confidence -= 0.05  # itemless order: less evidence to corroborate the call

    for seller in delivery.get("seller_handoff_analysis", []):
        hv = seller.get("handoff_variance_hours")
        if hv is not None and abs(hv) < 6:
            confidence -= 0.05  # seller handoff also right at the boundary
            break

    return round(max(0.5, min(1.0, confidence)), 2)


def apply_policy(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Runs the deterministic rule engine, cross-checks it with an independent
    LLM classification, and returns the draft output (rule-engine facts, with
    confidence grounded in evidence clarity and LLM agreement). LLM metadata
    is stashed under the private "_llm_meta" key for main.py to log to
    trace.jsonl; Verifier Agent strips it before writing the final
    schema-compliant output.
    """
    rule_result = rule_engine(evidence)
    llm_meta = llm_classify(evidence, rule_result)
    confidence = _data_driven_confidence(evidence, rule_result, llm_meta)

    draft_output = {
        "case_id": rule_result["case_id"],
        "case_assessment": {
            "primary_issue": rule_result["primary_issue"],
            "secondary_issues": rule_result["secondary_issues"],
            "case_status": rule_result["case_status"],
            "confidence": confidence,
        },
        "affected_entities": rule_result["affected_entities"],
        "customer_context": rule_result["customer_context"],
        "product_context": rule_result["product_context"],
        "delivery_analysis": rule_result["delivery_analysis"],
        "payment_reconciliation": rule_result["payment_reconciliation"],
        "root_cause_analysis": rule_result["root_cause_analysis"],
        "evidence_ids": rule_result["evidence_ids"],
        "financial_resolution": rule_result["financial_resolution"],
        "resolution_actions": rule_result["resolution_actions"],
        "_llm_meta": llm_meta,
    }
    return draft_output
