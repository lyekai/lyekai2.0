import os
import re
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai
from fpdf import FPDF
import gradio as gr
from datetime import datetime
from duckduckgo_search import DDGS

load_dotenv()

def get_chinese_font_file() -> str:
    fonts_path = r"C:\\Windows\\Fonts"
    candidates = ["kaiu.ttf", "msjh.ttc", "msjhbd.ttc", "msjhl.ttc"]
    for font in candidates:
        font_path = os.path.join(fonts_path, font)
        if os.path.exists(font_path):
            return os.path.abspath(font_path)
    return None

def search_theme_info(theme: str, max_results: int = 3) -> str:
    with DDGS() as ddgs:
        results = ddgs.text(theme, max_results=max_results)
        summaries = []
        for i, res in enumerate(results):
            title = res.get("title", "")
            snippet = res.get("body", "")
            summaries.append(f"{i+1}. {title}：{snippet}")
        return "\n".join(summaries) if summaries else f"沒有找到與『{theme}』相關的資料。"

def generate_prompt(student_name: str, theme: str, num_tf: int, num_mc: int, num_app: int, theme_info: str) -> str:
    return f"""你是一名資深數學老師，請根據"{student_name}"同學的答題狀況與所有人的易錯題目進行錯誤題目預測：

以下是與主題「{theme}」相關的背景資料，請根據這些資訊融合題目故事中，讓整份試卷充滿沉浸感：

{theme_info}

📌 **整體要求：**
1. 請以「{theme}」為主題撰寫一個完整故事，角色與背景需一致。\n
2. 該故事將貫穿整份試卷，三種類型的題目須有承接性，情節逐步推進。\n
3. 每大題（是非題、選擇題、應用題）開頭請撰寫約100～150字的小故事，延續整體劇情。\n
4. 每題內容應接續前題情節，不可跳躍、無關或另開新章。\n
5. 題目務必與數學概念相關，切勿出現答案與解說。\n
6. 所有題目須用繁體中文撰寫，語句清晰。\n
7. 其中0表示該學生在該題答錯，1表示該題答對，\n
8. "題目"的欄位為該份考卷所有的題目\n

📄 題目格式規定如下（必須遵守）：
一、是非題  
"故事背景" 
1.(題目) 
2.(題目)

二、選擇題  
"故事背景" 
1.(題目)  
2.(題目)

三、應用題  
"故事背景" 
1.(題目) 
2.(題目)

請產出以下題目：
- 是非題：{num_tf} 題  
- 選擇題：{num_mc} 題  
- 應用題：{num_app} 題

📄格式與語言注意事項：
- 題號格式為：1. 2. 3. ……（中間無空格，無換行）
- 選擇題選項必須以 (1)(2)(3)(4) 呈現，且選項不得重複。
- 所有內容不得加入「請作答」「請觀察圖」或其他引導語。
- 禁止產出除題目以外的內容。
"""

def generate_pdf(text: str) -> str:
    pdf = FPDF(format="A4")
    pdf.add_page()

    font_path = get_chinese_font_file()
    if not font_path:
        return "錯誤：找不到中文字型，請安裝 kaiu.ttf 或 msjh.ttc"

    pdf.add_font("ChineseFont", "", font_path, uni=True)
    pdf.set_font("ChineseFont", size=12)

    y_offset = 15
    line_height = 8
    pdf.set_y(y_offset)

    lines = text.splitlines()
    prev_line_was_question = False
    prev_line_was_section_title = False

    for idx, line in enumerate(lines):
        stripped = line.strip()

        if stripped in ["一、是非題", "二、選擇題", "三、應用題"]:
            pdf.ln(8)
            pdf.set_font("ChineseFont", size=14)
            pdf.multi_cell(0, line_height, stripped, border=0, align='L')
            pdf.ln(6)
            prev_line_was_question = False
            prev_line_was_section_title = True

        elif re.match(r"^\d+\.", stripped):
            if prev_line_was_section_title:
                pdf.ln(10)
            pdf.set_font("ChineseFont", size=12)
            pdf.multi_cell(0, line_height, stripped, border=0, align='L')
            prev_line_was_question = True
            prev_line_was_section_title = False

            next_line = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
            if next_line in ["一、是非題", "二、選擇題", "三、應用題"] or next_line == "":
                pdf.ln(2)

        elif stripped:
            pdf.set_font("ChineseFont", size=12)
            if prev_line_was_question:
                pdf.ln(2)
            pdf.multi_cell(0, line_height, stripped, border=0, align='L')
            prev_line_was_question = False
            prev_line_was_section_title = False

        if pdf.get_y() > pdf.h - 15:
            pdf.add_page()
            pdf.set_y(15)

    pdf_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(pdf_filename)
    return pdf_filename

def generate_solution_pdf(question_text: str) -> str:
    if not question_text.strip():
        return "錯誤：沒有可產生詳解的題目內容", None

    solution_prompt = f"""你是一名有經驗的數學老師，請根據以下這份考卷內容，為每一題撰寫詳解（僅限題目部分，不要重新編寫考卷或故事背景）：

{question_text}

✅ 請遵循以下規則產出詳解：
1. 詳解內容需清楚解釋解題過程與使用的數學概念。
2. 每題詳解格式如下：
【第X題詳解】
（解說文字）

3. 僅針對數學題進行解析，請跳過非題目文字（如故事背景）。
4. 所有內容使用繁體中文，條理清晰、語句簡潔。
"""

    model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
    response = model.generate_content(solution_prompt)
    solution_text = response.text.strip()

    return generate_pdf(solution_text)

def gradio_handler(csv_file, student_name, theme, num_tf, num_mc, num_app):
    if csv_file is not None:
        df = pd.read_csv(csv_file.name)
        if student_name not in df.columns:
            return f"找不到名字：{student_name}，請確認是否正確輸入。", None

        theme_info = search_theme_info(theme)
        df_preview = df.head(30)
        csv_preview = df_preview.to_csv(index=False)

        prompt = f"""以下是學生答題資料（前30筆，包含「{student_name}」）：\n{csv_preview}\n請依照以下規則產題：\n{generate_prompt(student_name, theme, num_tf, num_mc, num_app, theme_info)}"""
        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        pdf_path = generate_pdf(response_text)
        return response_text, pdf_path
    else:
        return "請上傳包含答題資料的 CSV 檔案", None

def generate_feedback_handler(csv_file, student_name):
    if csv_file is not None:
        df = pd.read_csv(csv_file.name)
        if student_name not in df.columns:
            return f"找不到名字：{student_name}，請確認是否正確輸入。"
        if "題目" not in df.columns:
            return "CSV 中缺少「題目」欄位，無法進行錯題分析。請確認格式。"

        student_answers = df[student_name]
        wrong_questions = df[student_answers == 0][["題目"]].reset_index(drop=True)

        if wrong_questions.empty:
            return f"學生「{student_name}」在這份考卷中沒有錯題，表現非常優秀！"

        wrong_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(wrong_questions["題目"])])
        feedback_prompt = f"""你是一名有經驗的數學老師，以下是學生「{student_name}」在數學測驗中的錯題內容：\n\n{wrong_text}\n\n請根據上述錯題，進行以下三點的分析與建議，務必簡潔有力（使用繁體中文）：\n\n1. 分析這些錯題的共通點或主題\n2. 推測可能的錯誤原因\n3. 提供具體、可執行的學習建議"""

        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        response = model.generate_content(feedback_prompt)
        return response.text.strip()
    else:
        return "請上傳包含答題資料的 CSV 檔案"

# ✅ Gradio UI
with gr.Blocks() as demo:
    gr.Markdown("# 📊 錯題分析與考卷生成系統")

    with gr.Row():
        csv_input = gr.File(label="上傳 CSV 檔案")
        student_name_input = gr.Textbox(label="請輸入你的姓名", value="張智翔")
        theme_input = gr.Textbox(label="請輸入題目主題", value="海綿寶寶")

    with gr.Row():
        num_tf = gr.Slider(1, 10, value=1, step=1, label="是非題數")
        num_mc = gr.Slider(1, 10, value=1, step=1, label="選擇題數")
        num_app = gr.Slider(1, 10, value=1, step=1, label="應用題數")

    output_text = gr.Textbox(label="生成題目內容", lines=15, interactive=False)
    output_pdf = gr.File(label="下載 PDF 考卷")
    submit_button = gr.Button("✏️ 生成考卷")

    submit_button.click(
        fn=gradio_handler,
        inputs=[csv_input, student_name_input, theme_input, num_tf, num_mc, num_app],
        outputs=[output_text, output_pdf]
    )

    with gr.Row():
        solution_pdf_output = gr.File(label="下載詳解 PDF")
        generate_solution_button = gr.Button("📘 生成詳解")

    generate_solution_button.click(
        fn=generate_solution_pdf,
        inputs=[output_text],
        outputs=solution_pdf_output
    )

    gr.Markdown("---")

    feedback_button = gr.Button("📋 生成報表")
    feedback_output = gr.Textbox(label="報表建議回饋", lines=10, interactive=False)

    feedback_button.click(
        fn=generate_feedback_handler,
        inputs=[csv_input, student_name_input],
        outputs=feedback_output
    )

demo.launch()
