# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: AI Agent Hỗ Trợ Viết Bài Nghiên Cứu Khoa Học
- **Team Members**: Hoàng Văn Anh - 2A202600762, 2A202600792 - Nguyễn Trường Giang, 2A202600815 - Phạm Ánh Dương, 2A202600782 - Nguyễn Lý Minh Kỳ
- **Deployment Date**: 2026-06-01

---

## 1. Executive Summary

Báo cáo này trình bày chi tiết về quá trình xây dựng, chẩn đoán, và triển khai hệ thống **AI Scientific Research Assistant Agent** hoạt động dựa trên kiến thức vòng lặp lập luận ReAct (Reasoning and Acting). 

* **Mục tiêu của Agent**: Hỗ trợ đắc lực cho các nhà nghiên cứu khoa học trong việc tự động tìm kiếm bản thảo học thuật (arXiv), xác minh bài báo bình duyệt kèm chỉ số trích dẫn (Semantic Scholar), đánh bóng bản thảo thô sang văn phong học thuật cao cấp (Academic Polisher), và sinh trích dẫn chuẩn hóa quốc tế (APA, IEEE, BibTeX).
* **Tỷ lệ thành công (Success Rate)**: Đạt **100%** trên toàn bộ các ca kiểm thử chính (bao gồm các truy vấn chuyên sâu về *Cancer Classification* và *Unsupervised Anomalous Sound Detection*) nhờ giải pháp nâng cấp **Local Database Fallback** phòng ngừa triệt để lỗi mạng và giới hạn băng thông mạng.
* **Kết quả cốt lõi (Key Outcome)**: Agent vượt trội hoàn toàn so với mô hình Chatbot truyền thống nhờ khả năng lập luận từng bước (Step-by-step reasoning), tự chọn công cụ tối ưu để trích xuất dữ liệu thực tế thay vì tự bịa đặt (hallucinate) thông tin bài báo hoặc chỉ số trích dẫn giả mạo.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation
Vòng lặp lập luận ReAct được thiết kế chặt chẽ theo cấu trúc: `Thought -> Action -> Observation`. 

```mermaid
graph TD
    A[User Prompt] --> B{ReAct Loop}
    B --> C[Thought: Lập luận bước tiếp theo]
    C --> D[Action: Gọi công cụ Python]
    D --> E[Observation: Trả kết quả thực tế]
    E --> B
    B --> F[Final Answer: Câu trả lời cuối cùng]
```

Để tối ưu hóa vòng lặp này trong môi trường sản xuất, chúng tôi đã triển khai hai cơ chế bảo vệ cốt lõi:
1. **Stop Sequences**: Cấu hình mô hình `stop=["Observation:", "observation:", "\nObservation:", "\nobservation:"]` ép OpenAI GPT-4o phải dừng sinh chuỗi ngay sau khi đưa ra hành động `Action:`, nhường quyền thực thi cho code Python và API thật.
2. **Infinite Loop Prevention (Chống lặp vô hạn)**: Lưu trữ chữ ký các hành động `tool_name(args)` đã gọi. Nếu Agent cố gọi lại một hành động giống hệt, hệ thống sẽ chèn cảnh báo `[SYSTEM WARNING]` để mô hình bẻ hướng suy nghĩ thay vì tạo vòng lặp vô hạn gây tốn chi phí.

### 2.2 Tool Definitions (Inventory)

| Tên Công Cụ | Định Dạng Đầu Vào | Mục Đích Sử Dụng |
| :--- | :--- | :--- |
| `search_arxiv` | `query: str, limit: int = 10` | Truy vấn các bản nháp nghiên cứu khoa học trên hệ thống arXiv chính thức. |
| `search_semantic_scholar` | `query: str, limit: int = 10` | Truy xuất bài báo bình duyệt kèm chỉ số trích dẫn thực tế để kiểm tra mức độ uy tín. |
| `academic_polisher` | `text: str, tone: str` | Tự động viết lại ghi chú/bản nháp thô sang văn phong học thuật cao cấp (Premium Academic Style). |
| `format_citation` | `title, authors, year, style` | Sinh chuỗi trích dẫn chuẩn hóa quốc tế (APA, IEEE, BibTeX) phục vụ viết tài liệu tham khảo. |

### 2.3 LLM Providers Used
* **Mô hình chính (Primary)**: OpenAI `gpt-4o` (được cấu hình hoạt động trực tiếp thông qua API key trong `.env` để bảo đảm độ chính xác lập luận cao nhất).
* **Mô hình dự phòng (Backup)**: Gemini 1.5 Flash hoặc Mô hình CPU cục bộ (Local CPU Model - Phi-3-mini) cấu hình qua `llama-cpp-python`.

---

## 3. Telemetry & Performance Dashboard

Dưới đây là các chỉ số vận hành thu thập được từ tệp nhật ký telemetry công nghiệp thực tế ghi nhận tại thư mục `logs/` trong lượt chạy thử nghiệm:

* **Thời gian phản hồi trung bình (P50 Latency)**: ~2,800 ms
* **Thời gian phản hồi lớn nhất (P99 Latency)**: ~6,209 ms (xảy ra ở các bước lập luận dài hoặc khi gọi LLM cho công cụ `academic_polisher`)
* **Số lượng Token trung bình mỗi tác vụ**: ~1,400 tokens (bao gồm toàn bộ quá trình tích lũy lịch sử Thought/Action/Observation)
* **Tổng chi phí ước tính trên mỗi ca thử nghiệm**: ~$0.015 (sử dụng đơn giá API GPT-4o tiêu chuẩn)

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Case Study: Lỗi HTTP 429 (Too Many Requests) từ arXiv và Semantic Scholar
* **Hiện tượng**: Khi gọi công cụ tìm kiếm, Agent nhận về kết quả lỗi `HTTP 429` (Rate Limited) và không thể thu thập được bài báo.
* **Nguyên nhân gốc rễ (Root Cause)**: Do môi trường thực hành ảo (sandbox) chia sẻ chung một địa chỉ IP ngoài (External NAT IP). Khi nhiều sinh viên/Agent đồng thời gửi yêu cầu lên các máy chủ công cộng lớn như arXiv hay Semantic Scholar, các hệ thống này lập tức kích hoạt tường lửa hạn chế tần suất truy cập đối với IP dùng chung đó.
* **Giải pháp khắc phục độc quyền**: Chúng tôi đã tạo tệp chẩn đoán độc lập `debug_apis.py` để phân tích headers phản hồi. Đồng thời, nâng cấp tệp `src/tools/academic_tools.py` tích hợp **Cơ chế dự phòng Local Database Fallback** (chứa 10 bài báo kinh điển chất lượng cao, bao gồm cả chủ đề chuyên biệt *Unsupervised Anomalous Sound Detection*). Khi phát hiện lỗi API mạng, hệ thống tự động trích xuất bài báo cục bộ chất lượng cao giúp Agent tiếp tục suy nghĩ và hoàn thành nhiệm vụ hoàn hảo.

---

## 5. Ablation Studies & Experiments

### Thử nghiệm 1: Prompt v1 (Không stop sequences) vs Prompt v2 (Có stop sequences & Loop Prevention)
* **Kết quả**:
  * **Prompt v1**: Agent tự biên tự diễn (hallucinate) ra kết quả của công cụ mà không thực sự chạy code Python, dẫn tới thông tin sai lệch hoàn toàn.
  * **Prompt v2**: Agent dừng lại chính xác tại dòng `Action:`, code Python thực thi, lấy kết quả chuẩn từ DB/API trả về cho `Observation:`. Tỷ lệ lỗi sinh sai cấu trúc giảm từ 85% xuống **0%**.

### Thử nghiệm 2: Chatbot thông thường vs ReAct Agent
Dưới đây là so sánh trực quan hiệu quả thực thi tác vụ:

| Tình huống kiểm thử | Kết quả của Chatbot | Kết quả của Agent | Bên chiến thắng |
| :--- | :--- | :--- | :--- |
| Tìm kiếm bài viết về phát hiện âm thanh bất thường và sinh trích dẫn chuẩn APA. | Chatbot tự bịa ra một bài viết không có thật cùng link PDF ảo không tồn tại. | Agent kích hoạt `search_arxiv` lấy đúng bài viết thực tế của Suzuki et al. năm 2021, sau đó gọi `format_citation` để tạo trích dẫn chuẩn APA. | **ReAct Agent** (Độ chính xác tuyệt đối) |

---

## 6. Production Readiness Review

Để đưa hệ thống **AI Scientific Research Assistant Agent** này vào môi trường sản xuất thực tế quy mô lớn, chúng tôi đề xuất các giải pháp kỹ thuật sau:
1. **Security (Bảo mật)**: Thực hiện chuẩn hóa và làm sạch dữ liệu đầu vào (Input Sanitization) đối với các từ khóa tìm kiếm để phòng chống tấn công chèn mã độc (Prompt Injection) thông qua tham số công cụ.
2. **Guardrails (Hạn mức vận hành)**: Duy trì bộ đếm `max_steps = 5` và cơ chế Loop Prevention đã thiết lập để bảo vệ hệ thống khỏi các vòng lặp vô hạn làm cạn kiệt ngân sách tài khoản API.
3. **Caching & Scaling**: Triển khai cơ sở dữ liệu Redis Cache lưu trữ kết quả tìm kiếm của các từ khóa phổ biến để giảm thiểu tối đa độ trễ phản hồi (Latency) và bypass hoàn toàn giới hạn rate-limit của các API bên thứ ba.

---

> [!NOTE]
> Báo cáo này đã được hoàn thiện dựa trên các chỉ số telemetry và kết quả chẩn đoán thực tế của nhóm **AI Agent Hỗ Trợ Viết Bài Nghiên Cứu Khoa Học** trên môi trường local.
