import os
import gradio as gr
import io
import contextlib
from src.core.openai_provider import OpenAIProvider
from src.agent.agent import ReActAgent
from src.tools.academic_tools import search_arxiv, search_semantic_scholar, academic_polisher, format_citation
from run_research_agent import get_research_tools

# Function to run the main ReAct agent
def run_research_agent(prompt):
    if not prompt or not prompt.strip():
        return "Vui lòng nhập yêu cầu nghiên cứu."
    
    try:
        # Initialize core provider and agent
        api_key = os.getenv("OPENAI_API_KEY")
        provider = OpenAIProvider(model_name="gpt-4o", api_key=api_key)
        tools = get_research_tools()
        agent = ReActAgent(llm=provider, tools=tools, max_steps=7)
        
        # Run the reasoning loop
        final_answer = agent.run(prompt)
    except Exception as e:
        final_answer = f"Lỗi hệ thống: {e}"
        
    return final_answer

# Wrapper for direct Academic Polisher tool execution
def run_polisher(text, tone):
    if not text or not text.strip():
        return "Vui lòng nhập văn bản nháp."
    try:
        return academic_polisher(text, tone)
    except Exception as e:
        return f"Lỗi biên tập: {e}"

# Wrapper for direct Citation Formatter tool execution
def run_citation(title, authors, year, style):
    if not title or not title.strip():
        return "Vui lòng nhập tiêu đề bài báo."
    try:
        # standardizing year as integer or default string
        try:
            year_int = int(year)
        except ValueError:
            year_int = 2023
        return format_citation(title, authors, year_int, style)
    except Exception as e:
        return f"Lỗi tạo trích dẫn: {e}"

# Premium CSS for modern styling
custom_css = """
body {
    background-color: #f7f9fc;
}
.title-header {
    text-align: center;
    margin-bottom: 20px;
}
.title-header h1 {
    font-size: 2.5rem;
    font-weight: 800;
    color: #1e3a8a;
    background: linear-gradient(90deg, #1e3a8a, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 5px;
}
.title-header p {
    font-size: 1.1rem;
    color: #4b5563;
}
.card-panel {
    background: white;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05);
}
"""

# Build the Gradio UI using Blocks
with gr.Blocks() as demo:
    
    # Header Section
    gr.HTML(
        """
        <div class="title-header">
            <h1>🔬 AI Scientific Research Assistant Agent</h1>
            <p>Giải pháp AI hỗ trợ viết bài nghiên cứu khoa học chuyên nghiệp dựa trên kiến trúc ReAct & Telemetry công nghiệp.</p>
        </div>
        """
    )
    
    # Tabs System
    with gr.Tabs():
        
        # Tab 1: ReAct Agent Playground
        with gr.TabItem("🧠 ReAct Research Agent"):
            gr.Markdown(
                """
                ### Luồng Lập luận ReAct Tự động (Reasoning & Acting)
                Nhập yêu cầu tìm kiếm bài báo, tóm tắt và sinh trích dẫn. Agent sẽ tự động lập luận từng bước (`Thought`), gọi công cụ học thuật (`Action`) và quan sát kết quả (`Observation`) để trả lời.
                """
            )
            with gr.Row():
                with gr.Column(scale=1):
                    research_prompt = gr.Textbox(
                        label="Yêu cầu Nghiên cứu (Research Prompt)",
                        placeholder="Ví dụ: I want you to search the AI paper that refer to classifying cancer",
                        lines=4,
                        value="I want you to search the AI paper that refer to classifying cancer"
                    )
                    submit_btn = gr.Button("🚀 Kích Hoạt Agent", variant="primary")
                    
                    gr.Markdown("#### 💡 Truy vấn Mẫu gợi ý:")
                    gr.Examples(
                        examples=[
                            ["I want you to search the AI paper that refer to classifying cancer"],
                            ["I want you to search the AI paper about unsupervised anomalous sound detection and format its citation in APA style"],
                            ["Search attention is all you need paper and format in IEEE"]
                        ],
                        inputs=research_prompt
                    )
                    
                with gr.Column(scale=2):
                    gr.Markdown("#### 📊 Kết quả Phản hồi")
                    
                    # Final Output
                    final_output = gr.Markdown(
                        label="Câu trả lời cuối cùng (Final Answer)",
                        value="*Kết quả phản hồi khoa học từ Agent sẽ xuất hiện ở đây...*"
                    )
                        
            submit_btn.click(
                fn=run_research_agent,
                inputs=research_prompt,
                outputs=final_output
            )
            
        # Tab 2: Cognitive Tool - Academic Polisher
        with gr.TabItem("✍️ Academic Text Polisher"):
            gr.Markdown(
                """
                ### Công cụ Biên tập Khoa học (Cognitive Polisher Tool)
                Nhập đoạn nháp, ý tưởng thô sơ hoặc ghi chú thí nghiệm của bạn. Công cụ sẽ gọi mô hình ngôn ngữ cao cấp để viết lại thành văn phong học thuật chuẩn mực, mạch lạc và trang trọng.
                """
            )
            with gr.Row():
                with gr.Column():
                    raw_text = gr.Textbox(
                        label="Văn bản Nháp Thô (Draft Text)",
                        placeholder="Ví dụ: we ran tests on deep learning and got 95% accuracy which is cool",
                        lines=6
                    )
                    tone_dropdown = gr.Dropdown(
                        label="Văn phong Đích (Target Tone)",
                        choices=[
                            "formal academic style",
                            "concise conference abstract",
                            "highly technical paper description",
                            "grant proposal writing style"
                        ],
                        value="formal academic style"
                    )
                    polish_btn = gr.Button("✨ Đánh Bóng Văn Bản", variant="primary")
                with gr.Column():
                    polished_text = gr.Textbox(
                        label="Kết quả Đã Biên Tập (Polished Academic Prose)",
                        lines=10,
                        interactive=False
                    )
            polish_btn.click(
                fn=run_polisher,
                inputs=[raw_text, tone_dropdown],
                outputs=polished_text
            )
            
        # Tab 3: Utility Tool - Citation Formatter
        with gr.TabItem("📖 Citation Formatter"):
            gr.Markdown(
                """
                ### Bộ Định dạng Trích dẫn Quốc tế (Citation Formatter Tool)
                Điền thông tin thư mục của bài viết để tự động sinh ra chuỗi tài liệu tham khảo chuẩn chỉnh theo APA, IEEE hoặc khối mã nguồn BibTeX.
                """
            )
            with gr.Row():
                with gr.Column():
                    paper_title = gr.Textbox(
                        label="Tiêu đề Bài báo (Paper Title)",
                        placeholder="Ví dụ: Attention Is All You Need",
                        value="Attention Is All You Need"
                    )
                    paper_authors = gr.Textbox(
                        label="Danh sách Tác giả (Authors - cách nhau bằng dấu phẩy)",
                        placeholder="Ví dụ: Ashish Vaswani, Noam Shazeer, Niki Parmar",
                        value="Ashish Vaswani, Noam Shazeer, Niki Parmar"
                    )
                    paper_year = gr.Textbox(
                        label="Năm Xuất Bản (Year)",
                        placeholder="Ví dụ: 2017",
                        value="2017"
                    )
                    citation_style = gr.Dropdown(
                        label="Định dạng Tài liệu Tham khảo (Style)",
                        choices=["APA", "IEEE", "BIBTEX"],
                        value="APA"
                    )
                    citation_btn = gr.Button("📑 Sinh Trích Dẫn", variant="primary")
                with gr.Column():
                    citation_output = gr.Textbox(
                        label="Trích dẫn Chuẩn Hóa (Formatted Citation)",
                        lines=6,
                        interactive=False
                    )
            citation_btn.click(
                fn=run_citation,
                inputs=[paper_title, paper_authors, paper_year, citation_style],
                outputs=citation_output
            )

    # Footer
    gr.HTML(
        """
        <div style="text-align: center; margin-top: 30px; font-size: 0.9rem; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 15px;">
            Hệ thống phát triển bởi Nhóm <strong>AI Agent Hỗ Trợ Viết Bài Nghiên Cứu Khoa Học</strong> • Lab 3 - Production-Grade Agentic System
        </div>
        """
    )

# Run the app locally
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"), css=custom_css)
