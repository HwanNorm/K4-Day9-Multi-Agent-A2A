"""Main Pipeline Execution: processes input/EC_*.json and writes output/EC_*.json + trace.jsonl."""
import json
import time
from pathlib import Path
from agents.data_loader import OlistData
from agents.coordinator import gather_evidence
from agents.policy_agent import apply_policy
from agents.verifier_agent import verify

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
TRACE_FILE = BASE_DIR / "trace.jsonl"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading Olist CSV Datasets...")
    start_time = time.time()
    data = OlistData()
    print(f"Datasets loaded in {time.time() - start_time:.2f}s")

    input_files = sorted(list(INPUT_DIR.glob("EC_*.json")))
    print(f"Found {len(input_files)} cases to process.")

    traces = []

    for idx, filepath in enumerate(input_files, 1):
        case_start = time.time()
        with open(filepath, "r", encoding="utf-8") as f:
            case = json.load(f)

        case_id = case.get("case_id")
        
        # Pipeline Flow: Coordinator -> Policy Agent -> Verifier Agent
        evidence = gather_evidence(data, case)
        draft_output = apply_policy(evidence)
        final_output = verify(draft_output)

        # Write output file
        output_filepath = OUTPUT_DIR / f"{case_id}.json"
        with open(output_filepath, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)

        duration = round(time.time() - case_start, 3)

        # Record Trace
        trace_item = {
            "case_id": case_id,
            "claimed_order_id": case.get("customer_request", {}).get("claimed_order_id"),
            "primary_issue": final_output["case_assessment"]["primary_issue"],
            "case_status": final_output["case_assessment"]["case_status"],
            "recommended_refund_brl": final_output["financial_resolution"]["recommended_refund_brl"],
            "duration_seconds": duration,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        traces.append(trace_item)

        print(f"[{idx}/{len(input_files)}] Processed {case_id} -> {final_output['case_assessment']['primary_issue']} ({duration}s)")

    # Save trace.jsonl
    with open(TRACE_FILE, "w", encoding="utf-8") as f:
        for trace in traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    print(f"\nCompleted 50 cases successfully! Saved outputs to {OUTPUT_DIR} and trace to {TRACE_FILE}")


if __name__ == "__main__":
    main()
