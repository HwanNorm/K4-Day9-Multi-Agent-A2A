# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                |
| --------------- | ----------------------- |
| Họ và tên       | Phạm Hoàng Nam           |
| MSSV            | 2A202601442              |
| Khóa/Lớp        | K4                       |
| Vai trò chính   | Đề xuất kiến trúc Supervisor-Worker và kế hoạch phân công theo checkpoint cho cả nhóm; triển khai Data-Gathering Agents (Person 1): Customer, Order & Product, Payment, Delivery, Coordinator; sau đó mở rộng sang debug và cải thiện Policy Agent — chiến lược này được cả nhóm áp dụng làm bản nộp cuối cùng |
| Ngày hoàn thành | 2026-08-05               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data loader | `agents/data_loader.py` (`OlistData`) | 7 CSV Olist | Các hàm tra cứu theo `order_id`/`customer_unique_id` dùng chung cho mọi agent | Hoàn thành |
| Customer Agent | `agents/customer_agent.py::analyze_customer` | `order_id` | `customer_unique_id`, `related_order_ids` (tối đa 5), `repeat_customer` | Hoàn thành |
| Order & Product Agent | `agents/order_product_agent.py::analyze_order_product` | `order_id` | `item_ids`, `seller_ids`, `product_ids`, `category_names`, các cờ `multi_item_order`/`multi_seller_order`/`multiple_categories` | Hoàn thành |
| Payment Agent | `agents/payment_agent.py::analyze_payment` | `order_id`, `items_df` | `payment_reconciliation` (item/freight/expected/payment total, `difference_brl`, `reconciled`), `split_payment` | Hoàn thành |
| Delivery Agent | `agents/delivery_agent.py::analyze_delivery` | `order_id`, `items_df` | `delivery_variance_hours`, `seller_handoff_analysis`, `late_handoff_seller_ids` | Hoàn thành |
| Coordinator Agent | `agents/coordinator.py::gather_evidence` | `case_input` (JSON từ `input/`) | Evidence dict gộp từ 4 worker, bàn giao cho Policy Agent | Hoàn thành |
| LLM client + Policy Agent (mở rộng sau khi có điểm số) | `agents/llm_client.py`, `agents/policy_agent.py` | Evidence dict | LLM cross-check độc lập (Groq `llama-3.1-8b-instant`), confidence dựa trên dữ liệu thật | Hoàn thành |

Coordinator Agent (của tôi) là điểm handoff trực tiếp sang Policy Agent (của thành viên còn lại) — evidence dict tôi trả về được `apply_policy()` tiêu thụ trực tiếp.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả và bằng chứng |
| --- | --- | --- |
| Debug lỗi tích hợp Coordinator ↔ Policy Agent | `agents/policy_agent.py` (module của thành viên 2) | Phát hiện `policy_agent.py` đọc sai tên field từ evidence dict (`evidence["delivery_analysis"]` thay vì `evidence["delivery"]`), khiến `apply_policy()` luôn nhận `{}` rỗng và ra sai kết quả cho toàn bộ 50/50 case mà không có exception nào. Phát hiện bằng cách so `output/EC_002.json` với ví dụ mẫu chính xác trong README — lệch hoàn toàn (`unsupported_late_claim` thay vì `late_delivery_seller`). |
| Wire LLM thật vào Policy Agent | `agents/policy_agent.py`, `agents/verifier_agent.py` | Thêm `llm_classify()` (LLM cross-check độc lập), `agents/llm_client.py` thêm retry/backoff cho lỗi `429`, `verifier_agent.py` thêm bước loại field nội bộ `_llm_meta` trước khi ghi file output. |
| Sửa `.env` bị đặt sai tên | Toàn nhóm | File chứa `GROQ_API_KEY` bị tạo với tên `env` (thiếu dấu chấm) nên `python-dotenv` không đọc được; đã đổi tên và xác nhận gọi API Groq thành công. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng 4 worker agent thu thập evidence từ CSV | `agents/customer_agent.py`, `order_product_agent.py`, `payment_agent.py`, `delivery_agent.py` | Evidence dict đúng schema, đã verify khớp 100% với ví dụ mẫu trong README (case tương đương EC_002) | Chạy tay `gather_evidence()` trên `EC_002.json`, so trực tiếp số liệu (`delivery_variance_hours=87.39`, `handoff_variance_hours=1.04`, `expected_total_brl=212.27`, `reconciled=true`) với bảng ví dụ mục 6 README |
| Chạy Coordinator trên toàn bộ 50 case thật | `agents/coordinator.py` | 0 exception trên 50/50 case; xác nhận đúng 6 case order rỗng item (`EC_012`, `031`, `033`, `034`, `035`, `043`) trả `null` cho `expected_total_brl`/`difference_brl`/`reconciled` theo đúng quy tắc README | Script Python lặp `glob('input/EC_*.json')`, gọi `gather_evidence` cho từng case, in ra danh sách lỗi/case rỗng item |
| Wire LLM thật vào Policy Agent + sửa 2 bug làm giảm điểm | `agents/policy_agent.py`, `agents/llm_client.py`, `agents/order_product_agent.py` | Điểm chấm tăng sau khi nộp lại (so với 5.7478/5.7460 trước đó khi pipeline hoàn toàn không gọi LLM nào) | Chạy `python main.py` toàn bộ 50 case, log `trace.jsonl` cho thấy `llm_called: true` và `llm_agrees_with_rule_engine: true` cho 50/50 case sau khi sửa prompt |

Artifact cụ thể: `trace.jsonl` ở root repo ghi lại, với mỗi case, kết quả rule engine, kết quả LLM độc lập, và có đồng ý hay không — đây là bằng chứng handoff và kiểm chứng thật giữa Policy Agent và LLM cross-check, không phải một prompt xử lý hết.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi (Coordinator + 4 worker agent) giải quyết bước đầu tiên của pipeline: từ `claimed_order_id` trong input, phải join đúng 6 bảng CSV Olist để dựng ra một "evidence dict" đầy đủ, chính xác về số liệu (giờ trễ giao hàng, giờ trễ bàn giao seller, đối soát thanh toán, danh sách item/seller/product/category, lịch sử khách hàng) — đây là nền tảng để Policy Agent áp rule `EC_POLICY_V2` phía sau. Nếu bước này sai hoặc thiếu, mọi kết luận nghiệp vụ phía sau đều sai theo mà không thể phát hiện bằng cách nhìn output, vì Policy Agent tin tưởng hoàn toàn vào evidence được đưa vào.

### Cách triển khai

Mỗi worker chỉ đọc đúng phạm vi CSV cần thiết (Customer Agent: `customers`+`orders`; Order/Product Agent: `orders`+`order_items`+`products`+`translation`; Payment Agent: `order_payments`; Delivery Agent: `orders`+`order_items`), tính toán thuần bằng pandas theo đúng công thức README mục 4 (`delivery_variance_hours`, `handoff_variance_hours` theo `shipping_limit_date` sớm nhất mỗi seller, `expected_total_brl`/`difference_brl`/`reconciled` với dung sai 0.10 BRL). Coordinator gọi cả 4 worker rồi gộp kết quả thành 1 dict duy nhất, không có logic nghiệp vụ nào trong Coordinator — toàn bộ quyết định primary/secondary issue nằm ở Policy Agent, giữ đúng nguyên tắc phân tách trách nhiệm.

Sau khi có điểm chấm đầu tiên (5.7478/10) và nhận thấy điểm gần như không đổi dù đã thay đổi lớn ở Policy Agent, tôi suy luận: vì hầu hết field được chấm (primary_issue, refund, evidence_ids, actions) là hoàn toàn deterministic và không phụ thuộc LLM, nên vấn đề gốc không nằm ở "chất lượng model". Tôi quay lại audit logic nghiệp vụ bằng cách tính tay trực tiếp từ CSV thô (không dùng lại code của mình) cho nhiều case để xác nhận độc lập, và tìm ra bug thật: `category_names` dùng bảng dịch tiếng Anh dù README không hề liệt kê bảng này trong danh sách join key chính thức, và bảng dịch này bị thiếu 13 category tiếng Bồ Đào Nha — nghĩa là dùng bản dịch có nguy cơ làm mất dữ liệu category âm thầm.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `case_input` dict đọc từ `input/EC_*.json` (đúng schema mục 3 README) |
| Output | Evidence dict với các khóa `case_id`, `order_id`, `order_exists`, `order_status`, `customer`, `order_product`, `payment`, `delivery` (chi tiết từng khóa con nằm trong docstring `agents/coordinator.py`) |
| Module phụ thuộc | `agents/data_loader.py` (load CSV một lần, dùng chung) |
| Module sử dụng output | `agents/policy_agent.py::apply_policy()` của thành viên 2 |
| Điều kiện lỗi cần xử lý | Order không tồn tại trong CSV (`order_exists=False`) → toàn bộ mảng item/seller/product rỗng; order không có item row → `expected_total_brl`/`difference_brl`/`reconciled` phải là `null` theo đúng README |

### Cách xác minh

```bash
python main.py
python -c "
import json, glob
for f in sorted(glob.glob('output/EC_*.json')):
    json.load(open(f, encoding='utf-8'))
print('all valid JSON, count =', len(glob.glob('output/EC_*.json')))
"
```

- **Kết quả mong đợi:** 50/50 case chạy không lỗi, output khớp ví dụ mẫu README cho case tương đương EC_002.
- **Kết quả thực tế:** Chạy đúng 50/50, không exception; `output/EC_002.json` khớp chính xác số liệu ví dụ mẫu (`delivery_variance_hours=87.39`, `refund=18.27`, `primary_issue=late_delivery_seller`). Tính tay độc lập (pandas thô, không dùng lại code agent) cho `EC_006` cũng khớp 100% (`delivery_variance_hours=141.48`, `handoff_variance_hours=196.13`, `refund=60.40`).
- **Artifact/log:** `trace.jsonl` (root repo), `output/EC_002.json`, `output/EC_006.json`.

## 5. Một quyết định kỹ thuật quan trọng

### Quyết định 1: Chọn kiến trúc Supervisor-Worker và kế hoạch phân công theo checkpoint

- **Bối cảnh:** README chỉ gợi ý tên 7 agent (mục 7) mà không chỉ định kiến trúc cụ thể; nhóm cần chọn một pattern rõ ràng để đảm bảo có phân công, handoff và kiểm chứng thật giữa các agent (không chỉ là nhiều agent cùng chạy trong một prompt) trong khung thời gian competition 4 tiếng.
- **Các phương án đã cân nhắc:** Pipeline tuyến tính (A→B→C), Debate (nhiều agent tranh luận rồi hội tụ), Hierarchical (nhiều tầng supervisor), Supervisor-Worker (1 coordinator gọi song song nhiều worker độc lập, rồi handoff sang policy/verify).
- **Phương án đã chọn:** Supervisor-Worker — Coordinator gọi 4 worker độc lập (Customer/Order-Product/Payment/Delivery), gộp evidence, chuyển cho Policy Agent rồi Verifier Agent.
- **Lý do:** Pipeline tuyến tính không phù hợp vì 4 domain (customer/order/payment/delivery) độc lập với nhau, không cần chờ nhau; Debate không phù hợp vì các worker báo cáo sự kiện từ dữ liệu tách biệt chứ không tranh luận cùng một câu hỏi; Hierarchical thừa phức tạp so với quy mô 7 agent của bài. Supervisor-Worker khớp chính xác với gợi ý kiến trúc ở README mục 7 và dễ chia việc 2 người theo giai đoạn (data-gathering vs policy+verify) trong thời gian giới hạn.
- **Bằng chứng quyết định phù hợp:** Toàn bộ nhóm áp dụng chiến lược này làm bản nộp cuối cùng; điểm chấm tăng từ 5.7478 → 5.7460 (khi pipeline còn thuần rule-based, chưa có LLM thật) lên **79.4195** sau khi hoàn thiện kiến trúc này với LLM cross-check thật và sửa các bug đã nêu ở mục 6.

### Quyết định 2: Rule engine deterministic làm nguồn sự thật, LLM chỉ cross-check

- **Bối cảnh:** Sau khi phát hiện toàn bộ pipeline ban đầu không hề gọi LLM nào (thuần rule-based Python), cần quyết định cách đưa LLM thật vào mà không phá vỡ logic nghiệp vụ đã verify đúng.
- **Các phương án đã cân nhắc:**
  1. Để LLM trực tiếp quyết định `primary_issue` cuối cùng.
  2. Giữ rule engine deterministic làm nguồn sự thật, LLM chỉ đóng vai trò cross-check độc lập (không biết trước đáp án rule engine) để tính `confidence`, và có fallback an toàn khi bất đồng.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Model bắt buộc ≤10B tham số (`llama-3.1-8b-instant`) không đủ tin cậy để tự quyết định trực tiếp — lần thử đầu tiên với prompt mô tả rule bằng lời, LLM bất đồng với rule engine 11/22 lần (luôn đoán sai về `unsupported_late_claim`). Nếu để LLM ghi đè, sẽ phá hỏng số liệu refund/evidence vốn đã verify đúng 100% với ví dụ mẫu README. Giữ rule engine làm nguồn sự thật đảm bảo không bao giờ regression, trong khi LLM cross-check vẫn tạo ra "handoff và kiểm chứng thật giữa các agent" đúng như README yêu cầu ở mục 7.
- **Bằng chứng quyết định phù hợp:** Sau khi đổi prompt sang dạng checklist (tính sẵn `condition_met` cho từng rule, LLM chỉ chọn rule có priority nhỏ nhất thỏa điều kiện), tỉ lệ đồng ý tăng từ 39/50 lên 50/50 mà không có case nào bị rule engine ghi đè sai. Điểm chấm thực tế sau khi nộp lại: **79.4195/100** (tăng mạnh so với 5.7460 của bản chưa có LLM).

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Sau khi merge nhánh `Son` (Policy/Verifier Agent) vào `main`, chạy `python main.py` không báo lỗi gì, nhưng `output/EC_002.json` cho ra `primary_issue: "unsupported_late_claim"`, `recommended_refund_brl: 0` — trong khi README quy định rõ case này phải là `late_delivery_seller`, refund 18.27 BRL.
- **Lệnh hoặc bước tái hiện:** `python main.py` rồi so `output/EC_002.json` với bảng ví dụ mục 6 README.
- **Nguyên nhân gốc:** `policy_agent.py` được viết dựa trên giả định evidence dict có field `evidence["delivery_analysis"]`, `evidence["payment_reconciliation"]`, v.v. (tức là đã đúng shape output cuối), nhưng `coordinator.py` của tôi trả về field tên khác (`evidence["delivery"]`, `evidence["payment"]`). Do dùng `dict.get(key, {})`, Python không raise lỗi mà âm thầm trả về `{}` rỗng, khiến mọi điều kiện rule engine đều `False` và rơi vào nhánh mặc định `unsupported_late_claim`.
- **Cách xử lý:** Sửa `policy_agent.py` để đọc đúng tên field từ `coordinator.py` (`evidence.get("delivery") or evidence.get("delivery_analysis", {})` — hỗ trợ cả 2 dạng để an toàn khi tích hợp lại sau này).
- **Cách xác minh sau khi sửa:** Chạy lại `python main.py`, so `output/EC_002.json` khớp chính xác ví dụ mẫu README; viết script đối chiếu độc lập (`rule_engine` tái triển khai riêng dựa thuần trên README) chạy trên cả 50 case, kết quả 0 mismatch.
- **Điều học được:** Khi 2 module được viết độc lập bởi 2 người dựa trên "giả định" chung về shape dữ liệu thay vì đọc trực tiếp docstring/contract của nhau, lỗi tích hợp có thể hoàn toàn im lặng (không exception) và chỉ lộ ra khi so sánh số liệu thực tế với ví dụ mẫu — merge không conflict không đồng nghĩa với tích hợp đúng.

## 7. Hiểu biết về luồng end-to-end

> Lưu ý: 5 câu hỏi gốc trong mẫu báo cáo (về Crossref, vector index, freshness monitoring, retrieval/answer quality) là nội dung còn sót lại từ một bài lab khác, không liên quan đến bài Multi-Agent E-commerce Dispute Resolution này. Tôi thay bằng 5 câu hỏi tương đương, đúng với pipeline thực tế của bài lab này, để phản ánh trung thực mức hiểu của mình thay vì trả lời cho câu hỏi không áp dụng được.

**Câu trả lời:**

1. **Dữ liệu đi từ CSV Olist đến output JSON như thế nào?** Coordinator nhận `claimed_order_id` từ input, gọi 4 worker agent join trực tiếp vào 6 CSV (orders, order_items, order_payments, customers, sellers, products+translation) để dựng evidence dict; evidence dict được Policy Agent (rule engine + LLM cross-check) chuyển thành `case_assessment`, `root_cause_analysis`, `financial_resolution`; cuối cùng Verifier Agent kiểm schema/giới hạn mảng/null-handling rồi ghi ra `output/EC_xxx.json`.
2. **"Ground truth" để verify pipeline lấy từ đâu?** README chỉ cung cấp đúng 1 ví dụ mẫu đầy đủ (case tương đương `EC_002`, mục 6). Tôi dùng ví dụ này làm ground truth chính, đồng thời tự tính tay độc lập bằng pandas thô (không tái sử dụng code agent) cho các case khác (ví dụ `EC_006`) để xác nhận công thức đúng vượt ra ngoài case mẫu duy nhất.
3. **Quality check nào khác ngoài so khớp business rule?** Verifier Agent kiểm tra riêng: giới hạn độ dài mảng (5 order/item/payment/product/category, 3 seller/root-cause/party, 20 evidence, 5 action), format evidence ID đúng regex (`order:`/`item:`/`payment:`/`seller:`/`policy:`), khoảng giá trị `confidence` trong [0,1], và loại bỏ field debug nội bộ (`_llm_meta`) trước khi ghi file — đây là lớp kiểm tra kỹ thuật độc lập với đúng/sai nghiệp vụ.
4. **Vì sao phải dùng cùng 50 input case khi so sánh phiên bản pipeline trước/sau khi sửa?** Vì điểm số bị ảnh hưởng bởi cả dữ liệu lẫn logic; nếu đổi input giữa các lần so sánh sẽ không biết thay đổi điểm số đến từ việc sửa logic (LLM cross-check, category_names) hay từ việc case khác dễ/khó hơn. Giữ nguyên input là điều kiện bắt buộc để một thay đổi trong code có thể được coi là nguyên nhân thực sự của thay đổi điểm số.
5. **Việc "sửa" (wire LLM, sửa category_names) được xem là thành công dựa trên artifact/metric nào?** `trace.jsonl` cho thấy tỉ lệ LLM gọi thành công (50/50, so với 22/50 trước khi thêm retry) và tỉ lệ đồng ý với rule engine (50/50, so với 39/50 trước khi sửa prompt); script audit tự viết xác nhận 0 mismatch giữa rule engine tái triển khai độc lập và output thực tế trên cả 50 case; và cuối cùng là điểm chấm thực tế: từ 5.7478 → 5.7460 (bản thuần rule-based, chưa có LLM) tăng lên **79.4195/100** sau khi nộp bản có LLM cross-check thật và đã sửa bug `category_names`.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Hoàng Nam
**Ngày xác nhận:** 2026-08-05
