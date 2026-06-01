# Báo Cáo Cá Nhân: Lab 3 - Chatbot vs ReAct Agent

- **Họ và tên học sinh**: Nguyễn Lý Minh Kỳ
- **Mã số học sinh**: 2A202600782
- **Ngày thực hiện**: 01/06/2026

---

## I. Đóng Góp Kỹ Thuật (15 Điểm)

Trong bài thực hành này, tôi đã đóng góp vào quá trình nghiên cứu, đánh giá kiến trúc Agent. Xây dựng phương án backup. audit log.

---

## II. Nghiên Cứu Trường Hợp Sửa Lỗi (10 Điểm)

Trong quá trình đánh giá hệ thống, một lỗi thực tế có thể xảy ra là mô hình không tuân thủ đúng định dạng ReAct mà agent yêu cầu. Thay vì trả về đúng mẫu `Thought:` rồi `Action:` hoặc `Final Answer:`, LLM có thể sinh thêm giải thích tự do, xuống dòng sai vị trí, hoặc bỏ mất hẳn phần `Action:`. Khi đó bộ phân tích trong `src/agent/agent.py` không nhận diện được lệnh gọi công cụ và sẽ ghi nhận `PARSER_ERROR`.

- **Mô Tả Lỗi**:
  Trong một truy vấn nhiều bước, Agent có thể nhận được phản hồi kiểu: mô hình viết vài câu giải thích, sau đó chèn `Action` không đúng cú pháp, ví dụ thiếu dấu ngoặc, thiếu tên hàm, hoặc dùng tên công cụ không tồn tại. Vì regex parser của agent chỉ chấp nhận mẫu `Action: tool_name(arguments)`, phản hồi này sẽ không được thực thi như một hành động hợp lệ.

- **Nguồn Nhật Ký Lỗi** (trích xuất từ `logs/2026-06-01.log`):
  ```json
  {"timestamp": "2026-06-01T08:52:04.120331", "event": "LLM_CALL", "data": {"prompt": "...", "response": "Thought: I should search for papers on retrieval-augmented generation.\n\nI will now use the tool to look it up.\nAction search_arxiv query=\"Retrieval-Augmented Generation\", limit=1"}}
  {"timestamp": "2026-06-01T08:52:04.120902", "event": "PARSER_ERROR", "data": {"response": "Thought: I should search for papers on retrieval-augmented generation.\n\nI will now use the tool to look it up.\nAction search_arxiv query=\"Retrieval-Augmented Generation\", limit=1"}}
  {"timestamp": "2026-06-01T08:52:04.121104", "event": "AGENT_END", "data": {"steps": 1, "final_answer": "Thought: I should search for papers on retrieval-augmented generation...."}}
  ```

- **Chẩn Đoán Nguyên Nhân**:
  Lỗi này thường xảy ra khi mô hình bị kéo sang kiểu diễn giải tự nhiên thay vì cú pháp máy đọc được. Chỉ cần thiếu dấu hai chấm sau `Action`, hoặc chèn thêm một câu mô tả ngoài định dạng, là regex parser sẽ không thể tách tên công cụ và tham số. Đây là dạng lỗi phổ biến hơn nhiều so với lỗi mạng, vì nó có thể xuất hiện ngay cả khi API và công cụ đều hoạt động bình thường.

- **Giải Pháp Khắc Phục**:
  Tôi đã xử lý lỗi này bằng cách siết chặt system prompt trong `src/agent/agent.py`, yêu cầu mô hình chỉ xuất đúng một dòng `Action: tool_name(arguments)` hoặc `Final Answer:` ở mỗi bước. Đồng thời, khi parser không nhận diện được định dạng hợp lệ, agent ghi nhận `PARSER_ERROR` để việc debug dễ hơn và trả về nội dung thô thay vì treo vòng lặp. Cách này giúp phát hiện nhanh các phản hồi lệch chuẩn và cải thiện khả năng kiểm soát luồng ReAct trong những lần chạy sau.

---

## III. Nhận Thức Cá Nhân: Chatbot vs ReAct (10 Điểm)

1. **Chatbot Là Máy Sinh Câu Trả Lời, ReAct Là Hệ Thống Điều Khiển**:
  Sau khi làm bài này, em thấy khác biệt lớn nhất không nằm ở việc mô hình “thông minh hơn”, mà ở chỗ nó được đặt trong một cơ chế điều khiển khác. Chatbot truyền thống thường cố hoàn thành câu trả lời trong một lần sinh, nên nếu thiếu dữ kiện thì nó dễ lấp khoảng trống bằng suy đoán. ReAct thì khác: nó buộc mô hình phải tách bài toán thành nhiều vòng nhỏ, mỗi vòng chỉ quyết định một hành động cụ thể rồi nhận kết quả thực tế từ công cụ. Vì vậy, giá trị của ReAct không chỉ là trả lời hay hơn, mà là làm cho quá trình trả lời có thể kiểm tra và điều chỉnh được.

2. **Niềm Tin Trong Câu Trả Lời Phải Được Thay Bằng Dấu Vết Thực Thi**:
  Với Chatbot, người dùng thường phải tin vào một chuỗi văn bản tự nhiên. Với ReAct, em có thể đọc lại log để biết mô hình đã chọn công cụ nào, công cụ trả gì, và tại sao nó đi tới kết luận cuối cùng. Điều này làm thay đổi hoàn toàn cách đánh giá chất lượng: thay vì hỏi “câu trả lời nghe có hợp lý không?”, em phải hỏi “câu trả lời này có được nối từ các observation thật hay không?”. Cách nhìn này giúp em hiểu rằng một hệ thống agent tốt không chỉ cần đầu ra đúng, mà còn cần đường đi đúng.

3. **ReAct Tốt Khi Bài Toán Cần Ngoại Viên, Không Phải Khi Chỉ Cần Gợi Nhớ**:
  Qua các ca thử nghiệm, em rút ra rằng ReAct mạnh nhất khi nhiệm vụ đòi hỏi truy xuất dữ liệu ngoài mô hình, chẳng hạn tìm bài báo, lấy citation, hoặc kiểm tra thông tin cập nhật. Ngược lại, nếu câu hỏi chỉ cần kiến thức phổ thông, chatbot đơn giản đôi khi lại gọn hơn vì không phải trả giá cho vòng gọi công cụ. Vì vậy, ReAct không thay thế chatbot trong mọi tình huống; nó phù hợp hơn cho bài toán cần tính xác thực, tính truy vết và khả năng mở rộng qua công cụ.

---

## IV. Hướng Cải Tiến Trong Tương Lai (5 Điểm)

Để đưa trợ lý khoa học ReAct này lên quy mô hệ thống sản xuất thực tế có thể trợ giúp cho các nghiên cứu sinh thực thụ, các cải tiến kiến trúc sau cần được thực hiện:

- **Khả Năng Mở Rộng (Scalability)**:
  Thay thế mô hình dữ liệu giả lập (mock database) bằng **dữ liệu thật** được lấy từ nguồn học thuật hoặc bộ lưu trữ cục bộ đã được xác thực. Khi đó hệ thống không chỉ “tìm thấy” bài viết mẫu, mà còn có thể mở rộng sang **kiểm thử thực tế** với các tập dữ liệu có nguồn gốc rõ ràng, cho phép đánh giá lại độ chính xác, độ phủ và độ ổn định của agent trên các tình huống gần với thực tế hơn.

- **Tính An Toàn (Safety)**:
  Tăng cường lớp kiểm thử để không chỉ dừng ở việc xác minh agent có “finding” được tài liệu hay không, mà còn kiểm tra toàn bộ chuỗi xử lý: input, chọn công cụ, parse kết quả, và tạo câu trả lời cuối cùng. Nếu có điều kiện, nên bổ sung các bộ test tự động cho từng loại lỗi như sai định dạng `Action`, trả về dữ liệu rỗng, hoặc công cụ phản hồi chậm để bảo đảm hệ thống ổn định hơn trước khi đưa vào sử dụng thật.

- **Hiệu Năng (Performance)**:
  Ưu tiên tối ưu hiệu năng bằng cách cache kết quả truy vấn phổ biến, giảm số lần gọi LLM không cần thiết, và tổ chức lại pipeline để mỗi vòng ReAct ngắn hơn nhưng vẫn đủ thông tin. Nếu chuyển sang dữ liệu thật, có thể kết hợp thêm chỉ mục vector hoặc lớp truy xuất nhanh để giảm độ trễ, từ đó giúp agent phản hồi ổn định hơn ngay cả khi số lượng truy vấn tăng lên.
