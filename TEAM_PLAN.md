# Team Plan — K4 Day 9 Multi-Agent A2A (2 người)

Kiến trúc: **Supervisor-Worker**. Coordinator gọi 4 worker agent độc lập để thu thập
evidence, sau đó chuyển cho Policy Agent -> Verifier Agent -> ghi `output/EC_*.json`.

## Phân công

| Ai | Module | Việc phải làm |
| --- | --- | --- |
| **Person 1** | `agents/customer_agent.py`, `agents/order_product_agent.py`, `agents/payment_agent.py`, `agents/delivery_agent.py`, `agents/coordinator.py` | Đọc CSV qua `agents/data_loader.py`, tính evidence từng domain (customer history, order/item/seller/product, payment reconciliation, delivery variance), gộp thành 1 dict evidence. |
| **Person 2** | `agents/policy_agent.py`, `agents/verifier_agent.py` | Nhận evidence dict từ Coordinator, áp bảng rule `EC_POLICY_V2` (README mục 4) đúng thứ tự ưu tiên, sinh root cause/responsible party/refund/action list. Verifier kiểm schema, giới hạn mảng, null-handling, evidence ID hợp lệ trước khi ghi file. |

**Bàn giao giữa 2 phần:** Coordinator trả về một `evidence` dict (gộp kết quả 4 worker).
Person 2 code `apply_policy(evidence) -> draft_output`, rồi `verify(draft_output) -> final_json`.
Shape của `evidence` dict xem trong docstring từng file worker đã có sẵn trong `agents/`.

## Trạng thái hiện tại (đã có trong repo)

- `agents/data_loader.py` — load 7 CSV, hàm tra cứu theo order_id / customer_unique_id
- `agents/llm_client.py` — gọi Groq API, model khai rõ trong code (`llama-3.1-8b-instant`, ≤10B theo README §9.1)
- `agents/customer_agent.py` — nháp, cần review
- `agents/order_product_agent.py` — nháp, cần review
- `agents/payment_agent.py` — nháp, cần review
- **Chưa có:** `delivery_agent.py`, `coordinator.py`, `policy_agent.py`, `verifier_agent.py`, `main.py`

## Checkpoint 2 (13h30–17h30): Competition

| Giờ | Person 1 | Person 2 |
| --- | --- | --- |
| 13h30–14h00 | Đọc README + review 3 file nháp đã có, thống nhất evidence dict schema | Đọc kỹ bảng rule EC_POLICY_V2 (README mục 4) |
| 14h00–15h30 | Code `delivery_agent.py` + `coordinator.py` | Code `policy_agent.py` |
| 15h30–16h00 | Test Coordinator trên vài case, in evidence dict | Code `verifier_agent.py` |
| 16h00–17h00 | Ghép `main.py`: chạy 50 case -> Coordinator -> Policy -> Verifier -> ghi `output/` | Debug chung |
| 17h00–17h30 | Cả 2 review output mẫu, viết `architecture.md`, `metadata.json`, `trace.jsonl` (đặt ở root) | |

## Checkpoint 3 (17h30–18h): Chốt leaderboard

Chạy lại full 50 case lần cuối, kiểm tra `output/` đúng 50 file JSON, zip `output/` để nộp,
commit toàn bộ source code lên repo trước khi nộp zip.

## Ràng buộc bắt buộc (README §9)

1. Mỗi agent chỉ dùng model ≤10B parameters.
2. Zip nộp chỉ chứa `output/`, không kèm source/`.env`.
3. Phải commit toàn bộ source lên repo trước khi nộp output zip.
4. API key/secret để trong `.env` (không commit); **tên model phải khai trong code**, không giấu trong `.env`.
