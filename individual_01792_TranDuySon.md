# Member Role Report — Day 9: Multi Agent A2A

> Báo cáo cá nhân cho Person 2 (theo [TEAM_PLAN.md](TEAM_PLAN.md)).

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                       |
| --------------- | ------------------------------ |
| Họ và tên       | Trần Duy Sơn |
| MSSV            | 01792 |
| Khóa/Lớp        | K4                             |
| Vai trò chính   | Person 2 — `policy_agent.py`, `verifier_agent.py` |
| Ngày hoàn thành | 05/08/2026              |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao   | Trạng thái                            |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| Policy rules impl. | `agents/policy_agent.py` — `apply_policy(evidence)` | `evidence` dict (từ Coordinator) | `draft_output` dict (root causes, responsible, actions) | Hoàn thành một phần |
| Verifier & schema  | `agents/verifier_agent.py` — `verify(draft_output)` | `draft_output` | `final_json` (validated, size-limited, sanitized) | Hoàn thành một phần |

Chú ý: Tôi chỉ nhận ownership cho phần áp luật và kiểm chứng kết quả trước khi ghi file.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                 | Thành viên/module được hỗ trợ | Kết quả                 |
| ------------------------- | ----------------------------- | ----------------------- |
| Tư vấn chính sách, ưu tiên | Person 1 (Coordinator + workers) | Định nghĩa rõ thứ tự rule áp dụng |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao          | Cách xác minh   |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Triển khai luật EC_POLICY_V2 | `agents/policy_agent.py` | `apply_policy(evidence) -> draft_output` | Unit test với sample evidence |
| Kiểm tra & sanitize output | `agents/verifier_agent.py` | `verify(draft_output) -> final_json` | Chạy validate schema + kiểm thử giới hạn mảng và nulls |

Output cụ thể bàn giao:

- `draft_output` (sample): danh sách root causes, responsible party tags (`customer`, `seller`, `platform`, `payment_gateway`), refund amount suggestion, actions list.
- `final_json`: giống `draft_output` nhưng đã qua kiểm tra schema, cắt mảng quá dài (max 20 items), loại bỏ null/NaN, ánh xạ evidence IDs hợp lệ.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Nhận `evidence` tổng hợp từ các worker, áp bộ quy tắc EC_POLICY_V2 theo thứ tự ưu tiên để suy luận root cause, trách nhiệm, và đề xuất hành động/refund. Sau đó verify kết quả để đảm bảo schema hợp lệ và an toàn khi ghi `output/EC_*.json`.

### Cách triển khai

- `apply_policy(evidence)`: tuần tự áp các rule trong `EC_POLICY_V2` (ưu tiên theo README §4). Mỗi rule trả optional findings; merge các findings theo precedence (rule higher priority overrides lower). Tính toán refund amounts dựa trên reconciliation logic (payment vs order totals) và delivery variance evidence.
- `verify(draft_output)`: kiểm schema (required fields, types), limit độ dài các mảng (ví dụ max 20 root-causes/actions), sanitize text (loại control chars), validate evidence IDs tồn tại (khớp với `evidence['evidence_id']`), và convert số/decimal sang chuẩn (ví dụ cents -> float 2 chữ số thập phân).

### Input, output và contract

| Thành phần              | Mô tả                                  |
| ----------------------- | -------------------------------------- |
| Input                   | `evidence` dict — gộp từ 4 worker (customer/order/payment/delivery) |
| Output                  | `final_json` — schema theo README (root_cause, responsible, refund, actions, evidence_ids) |
| Module phụ thuộc        | `agents/coordinator.py`, `agents/data_loader.py`, README (EC_POLICY_V2) |
| Module sử dụng output   | `main.py` (ghi file vào `output/`)     |
| Điều kiện lỗi cần xử lý | missing keys, inconsistent amounts, nulls, arrays quá dài, evidence_id không khớp |

### Cách xác minh

Tôi dùng một script kiểm thử nhỏ (ví dụ `tests/test_policy_verifier.py`) để supply sample `evidence` và assert các invariants. Thực thi ví dụ:

```bash
python -c "from agents.policy_agent import apply_policy; from agents.verifier_agent import verify; import json
e={'sample':'evidence'}
draft=apply_policy(e)
final=verify(draft)
print(json.dumps(final, indent=2))"
```

- **Kết quả mong đợi:** `final` tuân theo schema, không có null, mảng giới hạn, evidence_ids hợp lệ.
- **Kết quả thực tế:** (điền sau khi chạy trên môi trường local).
- **Artifact/log:** `output/EC_XXX.json` (sau khi `main.py` tích hợp).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi nhiều rule cùng phát hiện cùng một root cause, cần quyết định rule nào thắng.
- **Các phương án đã cân nhắc:** a) First-match-wins theo priority list; b) Aggregate multi-rule findings và compute weighted score.
- **Phương án đã chọn:** First-match-wins theo thứ tự priority trong `EC_POLICY_V2` (đơn giản, dễ audit cho cuộc thi).
- **Lý do:** Đảm bảo tính giải thích (explainability) và trùng khớp với yêu cầu ưu tiên trong đề bài; giảm biến thể không mong muốn khi nhiều rule chồng chéo.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `draft_output` chứa mảng `actions` với >100 items gây tràn khi ghi JSON.
- **Lệnh hoặc bước tái hiện:** supply evidence giả có nhiều suggestions từ LLM.
- **Nguyên nhân gốc:** LLM client trả quá nhiều đề xuất; không có giới hạn ở bước policy.
- **Cách xử lý:** Thêm bước truncate trong `verify()` (keep top N, N=20) và thêm logging khi cắt.
- **Cách xác minh sau khi sửa:** Unit test mô phỏng trả về 200 suggestions, assert `len(final['actions']) <= 20`.
- **Điều học được:** Luôn enforce bounds ở verifier trước khi xuất file.

## 7. Hiểu biết về luồng end-to-end

Tóm tắt ngắn gọn:

1. Worker agents lấy dữ liệu CSV qua `data_loader.py`, build evidence per order.
2. Coordinator gộp evidence 4 domain thành `evidence` dict cho một case.
3. `policy_agent.apply_policy(evidence)` áp luật `EC_POLICY_V2` theo priority, tạo `draft_output`.
4. `verifier_agent.verify(draft_output)` kiểm schema, sanitize và giới hạn arrays, trả `final_json`.
5. `main.py` (orchestrator) ghi `output/EC_*.json`.

## 8. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Duy Sơn
**Ngày xác nhận:** 5/8/2026
