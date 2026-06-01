# 🔬 AI Scientific Research Assistant Agent (ReAct CLI)

Chào mừng bạn đến với **AI Scientific Research Assistant Agent** – một AI Agent nâng cao triển khai mô hình kiến trúc lập luận **ReAct (Reasoning and Acting)** chuyên nghiệp phục vụ nghiên cứu khoa học. 

Dự án này là giải pháp toàn diện cho **Lab 3: Chatbot vs ReAct Agent**, được thiết kế theo các tiêu chuẩn công nghệ công nghiệp thực tế với khả năng xử lý lập luận tự động, phòng chống vòng lặp vô hạn, định dạng trích dẫn chuẩn hóa quốc tế và cơ chế dự phòng cục bộ chống lỗi nghẽn mạng băng thông cực kỳ thông minh.

---

## 🌟 Tính Năng Nổi Bật

1. **Vòng lặp ReAct Đúng Nghĩa (`src/agent/agent.py`)**: Hiện thực hóa chu trình logic `Thought -> Action -> Observation` chặt chẽ, tự động bóc tách Regex và dừng sinh chuỗi (Stop Sequences) đúng lúc để nhường quyền kiểm soát cho code Python gọi API thật.
2. **Cơ chế Chống Lặp Vô Hạn (Loop Prevention)**: Giám sát toàn bộ lịch sử hành động của Agent. Nếu phát hiện hành động bị lặp lại, hệ thống tự động tiêm một cảnh báo hệ thống để ép Agent bẻ hướng suy nghĩ và đưa ra câu trả lời dựa trên thông tin sẵn có thay vì lặp vô hạn tốn phí API.
3. **Bộ Công Cụ Học Thuật Thực Tế (`src/tools/academic_tools.py`)**:
   * `search_arxiv`: Tìm kiếm bản nháp nghiên cứu trên arXiv qua API XML.
   * `search_semantic_scholar`: Truy xuất bài báo bình duyệt và **chỉ số trích dẫn (citation count)** để đánh giá độ uy tín.
   * `academic_polisher`: Công cụ chuyển đổi văn phong nháp thô sơ thành văn phong báo chí khoa học chuyên nghiệp (Premium Academic Style).
   * `format_citation`: Định dạng tài liệu tham khảo chuẩn APA, IEEE hoặc khối BibTeX.
4. **Hệ Thống Trích Xuất & Đo Lường Industry Telemetry (`logs/`)**: Tự động ghi nhận mọi sự kiện dưới dạng cấu trúc JSON chuyên nghiệp giúp dễ dàng đo lường hiệu năng (`latency_ms`) và lượng tokens tiêu thụ (`usage`).
5. **Giao Diện Dòng Lệnh CLI Tương Tác Premium**: Trình tương tác CLI được tinh chỉnh tinh giản, ẩn các log JSON rác để hiển thị một luồng lập luận ReAct cực kỳ sạch đẹp, trực quan và dễ đọc.

---

## 🛠️ Cấu Trúc Dự Án

```bash
├── src
│   ├── agent
│   │   └── agent.py              # Hiện thực hóa vòng lặp ReAct chính & Loop Prevention
│   ├── core
│   │   ├── llm_provider.py       # Bộ nạp cấu hình .env hoạt động động
│   │   └── openai_provider.py    # Cấu hình API OpenAI gpt-4o với Stop Sequences
│   ├── telemetry
│   │   └── logger.py             # Hệ thống lưu trữ telemetry JSON dòng
│   └── tools
│       └── academic_tools.py     # Bộ 4 công cụ học thuật & Local Database Fallback
├── logs/                         # Nơi lưu trữ nhật ký telemetry
├── debug_apis.py                 # Công cụ độc lập chẩn đoán lỗi kết nối API
├── run_research_agent.py         # Điểm khởi chạy CLI tương tác
├── requirements.txt              # Danh sách các thư viện phụ thuộc
└── README.md                     # Tài liệu hướng dẫn sử dụng (tệp này)
```

---

## 🚨 Chẩn Đoán Lỗi 429 & Giải Pháp Dự Phòng Local Database Fallback

### 1. Nguyên Nhân Gây Ra Lỗi 429 (Too Many Requests)
Trong quá trình phát triển trên môi trường sandbox học tập, khi nhiều Agent gửi các yêu cầu đồng thời lên máy chủ arXiv hoặc Semantic Scholar, máy chủ sẽ chặn địa chỉ IP chung (NAT IP) của hệ thống vì vượt quá hạn ngạch tần suất cho phép, trả về lỗi **HTTP 429 (Too Many Requests)**.

Để kiểm tra trạng thái API trực tiếp, bạn có thể thực hiện lệnh chẩn đoán:
```bash
python debug_apis.py
```
Script chẩn đoán sẽ gửi request thô trực tiếp và in ra chi tiết mã lỗi, headers bảo mật cùng thông báo lỗi thô từ các máy chủ để bạn phân tích kỹ thuật.

### 2. Giải Pháp Local Fallback Thông Minh
Để Agent luôn hoạt động bền bỉ, không bị crash giữa chừng và luôn hoàn thành nhiệm vụ, chúng tôi đã tích hợp **Cơ sở dữ liệu khoa học dự phòng cục bộ (Local Database Fallback)** chứa 10 bài viết khoa học hàng đầu ở nhiều lĩnh vực khác nhau (BERT, ResNet, GANs, RAG, Transformers, và đặc biệt là **Unsupervised Anomalous Sound Detection**).
* Khi API thật trả về lỗi 429 hoặc mất kết nối -> Công cụ tự động chuyển hướng tìm kiếm trong cơ sở dữ liệu local.
* Kết quả trả về có định dạng chuẩn xác (Title, Authors, Year, Abstract, URL, Citations, PDF) giúp Agent tiếp tục suy nghĩ và sinh ra định dạng trích dẫn hoặc tóm tắt hoàn hảo ở các bước sau.

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng

### 1. Cấu Hình Môi Trường
Sao chép tệp cấu hình mẫu và điền khóa OpenAI API của bạn:
```bash
cp .env.example .env
```
Mở tệp `.env` và thiết lập:
```env
OPENAI_API_KEY=your_openai_api_key_here
DEFAULT_PROVIDER=openai
```

### 2. Cài Đặt Thư Viện Phụ Thuộc
```bash
pip install -r requirements.txt
```

### 3. Chạy Thử Nghiệm Một Câu Lệnh Độc Lập qua CLI
Tìm kiếm bài báo khoa học về phân loại tế bào ung thư hoặc các công nghệ AI khác:
```bash
python run_research_agent.py "I want you to search the AI paper that refer to classifying cancer"
```

Bạn cũng có thể thử nghiệm với bài báo phát hiện âm thanh bất thường:
```bash
python run_research_agent.py "I want you to search the AI paper about unsupervised anomalous sound detection"
```

### 4. Chạy Giao Diện Tương Tác Shell (Interactive REPL)
Để thực hiện chuỗi nhiều câu lệnh liên tiếp và trò chuyện trực tiếp với Agent:
```bash
python run_research_agent.py
```
*(Gõ `exit` để thoát khỏi chương trình tương tác).*

### 5. Chạy Giao Diện Web UI Tương Tác Premium (Gradio App)
Để khởi chạy giao diện web hiện đại, đẹp mắt và trực quan để tương tác với Agent và các công cụ bổ trợ học thuật:
```bash
python app.py
```
Sau khi khởi chạy thành công, truy cập trình duyệt tại địa chỉ:
🔗 **http://localhost:7860**

Giao diện Web UI cung cấp 3 phân khu chuyên biệt:
* **🧠 ReAct Research Agent**: Trực quan hóa luồng suy nghĩ (`Thought` -> `Action` -> `Observation`) trong bảng điều khiển và câu trả lời hoàn thiện.
* **✍️ Academic Text Polisher**: Công cụ AI biên tập và nâng cấp văn phong nháp thô thành văn phong khoa học chuyên nghiệp.
* **📖 Citation Formatter**: Hỗ trợ xuất trích dẫn bài viết chuẩn APA, IEEE hoặc mã BibTeX nhanh chóng.

---

## 📊 Phân Tích Telemetry & Báo Cáo Kết Quả

Tất cả các lượt chạy thử nghiệm đều được ghi nhận tự động dưới dạng JSON tại:
📄 `logs/[YYYY-MM-DD].log` (Ví dụ: `logs/2026-06-01.log`)

Dữ liệu JSON lưu trữ đầy đủ thông tin:
* `latency_ms`: Thời gian phản hồi của LLM (giúp đánh giá tốc độ mô hình).
* `usage`: Thông số tokens tiêu thụ (`prompt_tokens`, `completion_tokens`, `total_tokens`) giúp bạn điền số liệu vào **Group Report** nhanh chóng.

---
