# Architecture Specification — Multi-Agent E-commerce Dispute Resolution

 Kiến trúc hệ thống tuân theo mô hình **Supervisor-Worker Agent Architecture** nhằm xử lý 50 case khiếu nại thương mại điện tử từ dữ liệu Olist.

## 1. Sơ đồ Kiến trúc Hệ thống (Agent Workflow)

```mermaid
flowchart TD
    Input[Input Case: EC_xxx.json] --> Supervisor[Coordinator Agent]
    
    subgraph Data Layer & Workers
        Supervisor -->|order_id| W1[Customer Agent]
        Supervisor -->|order_id| W2[Order & Product Agent]
        Supervisor -->|order_id| W3[Payment Agent]
        Supervisor -->|order_id, items| W4[Delivery Agent]
        
        CSV[(Olist CSV Datasets)] --> W1
        CSV --> W2
        CSV --> W3
        CSV --> W4
    end

    W1 -->|customer_context| Evidence[Aggregated Evidence Dict]
    W2 -->|affected_entities, product_context| Evidence
    W3 -->|payment_reconciliation| Evidence
    W4 -->|delivery_analysis| Evidence

    Evidence --> Policy[Policy Agent]
    Policy -->|draft_output| Verifier[Verifier Agent]
    Verifier -->|final_json| Output[Output File: output/EC_xxx.json]
```

---

## 2. Vai trò & Quyền truy cập từng Agent

| Agent Name | Vai trò | Dữ liệu truy cập (CSVs) | Trách nhiệm chính |
| :--- | :--- | :--- | :--- |
| **Coordinator Agent** | Supervisor / Orchestrator | Input JSONs | Khởi tạo pipeline, điều phối 4 worker agent, gộp kết quả thành `evidence` dict. |
| **Customer Agent** | Worker (Person 1) | `olist_customers_dataset.csv`, `olist_orders_dataset.csv` | Tra cứu `customer_unique_id`, các đơn hàng lịch sử (`related_order_ids`), xác định `repeat_customer`. |
| **Order & Product Agent** | Worker (Person 1) | `olist_orders_dataset.csv`, `olist_order_items_dataset.csv`, `olist_products_dataset.csv`, `product_category_name_translation.csv` | Thu thập `item_ids`, `seller_ids`, `product_ids`, `category_names`, phát hiện multi-item, multi-seller, multi-category. |
| **Payment Agent** | Worker (Person 1) | `olist_order_payments_dataset.csv` | Tính toán tổng thanh toán `payment_total_brl`, đối soát với tổng item + freight (`reconciled`), kiểm tra `split_payment`. |
| **Delivery Agent** | Worker (Person 1) | `olist_orders_dataset.csv`, `olist_order_items_dataset.csv` | Tính sai số giao hàng `delivery_variance_hours`, sai số bàn giao của seller `handoff_variance_hours`, phát hiện seller bàn giao trễ. |
| **Policy Agent** | Policy Rule Engine (Person 2) | Evidence Dict | Áp dụng bảng quy tắc `EC_POLICY_V2`, xác định `primary_issue`, `secondary_issues`, `root_cause_analysis`, `financial_resolution`, `resolution_actions`, `evidence_ids`. |
| **Verifier Agent** | Quality Control (Person 2) | Draft Output Dict | Phân tích JSON schema, kiểm tra giới hạn mảng (Array bounds), xử lý giá trị null, làm tròn số tiền, kiểm định Evidence IDs trước khi xuất file. |

---

## 3. Luồng Handoff Dữ liệu (Handoff Flow)

1. **Step 1 (Input Handling)**: Coordinator tiếp nhận `case_id` và `claimed_order_id` từ `input/EC_*.json`.
2. **Step 2 (Parallel Evidence Gathering)**: Coordinator kích hoạt 4 Worker Agents truy xuất dữ liệu Olist.
3. **Step 3 (Evidence Aggregation)**: Kết quả từ 4 Worker được gộp thành 1 đối tượng `evidence` duy nhất.
4. **Step 4 (Policy Evaluation)**: Policy Agent thực thi đánh giá dựa trên `EC_POLICY_V2` để sinh ra `draft_output`.
5. **Step 5 (Verification & Output)**: Verifier Agent kiểm tra các ràng buộc kỹ thuật (schema, null, rounding, array bounds) và ghi ra file `output/EC_*.json`.
