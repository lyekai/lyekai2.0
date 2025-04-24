import os
import json
import time
import pandas as pd
import sys
from dotenv import load_dotenv
import google.generativeai as genai
from fpdf import FPDF
import gradio as gr
from datetime import datetime

# 加载 .env 文件
load_dotenv()

def get_chinese_font_file() -> str:
    """
    只檢查 Windows 系統字型資料夾中是否存在候選中文字型（TTF 格式）。
    若找到則回傳完整路徑；否則回傳 None。
    """
    fonts_path = r"C:\Windows\Fonts"
    candidates = ["kaiu.ttf"]  # 這裡以楷體為例，可依需要修改
    for font in candidates:
        font_path = os.path.join(fonts_path, font)
        if os.path.exists(font_path):
            print("找到系統中文字型：", font_path)
            return os.path.abspath(font_path)
    print("未在系統中找到候選中文字型檔案。")
    return None

def create_table(pdf: FPDF, df: pd.DataFrame):
    """
    使用 FPDF 將 DataFrame 以漂亮的表格形式繪製至 PDF，
    使用交替背景色與標題區塊，並自動處理分頁。
    """
    available_width = pdf.w - 2 * pdf.l_margin
    num_columns = len(df.columns)
    col_width = available_width / num_columns
    cell_height = 10

    # 表頭：使用淺灰色背景
    pdf.set_fill_color(200, 200, 200)
    pdf.set_font("ChineseFont", "", 12)
    for col in df.columns:
        pdf.cell(col_width, cell_height, str(col), border=1, align="C", fill=True)
    pdf.ln(cell_height)

    # 資料行：交替背景色
    pdf.set_font("ChineseFont", "", 12)
    fill = False
    for index, row in df.iterrows():
        if pdf.get_y() + cell_height > pdf.h - pdf.b_margin:
            pdf.add_page()
            pdf.set_fill_color(200, 200, 200)
            pdf.set_font("ChineseFont", "", 12)
            for col in df.columns:
                pdf.cell(col_width, cell_height, str(col), border=1, align="C", fill=True)
            pdf.ln(cell_height)
            pdf.set_font("ChineseFont", "", 12)
        
        admission_method = row['單元'] if '單元' in df.columns else ''
        if admission_method == '比和比值':
            pdf.set_text_color(0, 0, 255)  # 藍色
        elif admission_method == '扇形的弧長和面積':
            pdf.set_text_color(255, 0, 0)  # 紅色
        elif admission_method == '圓周率和圓面積':
            pdf.set_text_color(255, 255, 0)  # 黃色
        elif admission_method == '數量關係':
            pdf.set_text_color(0, 255, 0)  # 綠色
        # else:
        #     pdf.set_text_color(0, 0, 0)  # 默認顏色為黑色

        # 交替背景色設定
        if fill:
            pdf.set_fill_color(230, 240, 255)
        else:
            pdf.set_fill_color(255, 255, 255)
        
        # 輸出每列的資料
        for item in row:
            pdf.cell(col_width, cell_height, str(item), border=1, align="C", fill=True)
        pdf.ln(cell_height)
        fill = not fill

    # 恢復預設顏色
    pdf.set_text_color(0, 0, 0)


def parse_markdown_table(markdown_text: str) -> pd.DataFrame:
    """
    從 Markdown 格式的表格文字提取資料，返回一個 pandas DataFrame。
    例如，輸入：
      | 班級 | 姓名| 錄取大學 | 錄取學系 |升學管道|
      |-------|-----|------|------|------|
      | 301 | 陳o孝 | 國立臺灣大學 | 地質科學系 |繁星推薦|
    會返回包含該資料的 DataFrame。
    """
    lines = markdown_text.strip().splitlines()
    # 過濾掉空行
    lines = [line.strip() for line in lines if line.strip()]
    # 找到包含 '|' 的行，假設這就是表格
    table_lines = [line for line in lines if line.startswith("")]
    if not table_lines:
        return None
    # 忽略第二行（分隔線）
    header_line = table_lines[0]
    headers = [h.strip() for h in header_line.strip("").split("")]
    data = []
    for line in table_lines[2:]:
        row = [cell.strip() for cell in line.strip("").split("")]
        if len(row) == len(headers):
            data.append(row)
    df = pd.DataFrame(data, columns=headers)
    return df

def generate_pdf(text: str = None, df: pd.DataFrame = None) -> str:
    print("開始生成 PDF")
    pdf = FPDF(format="A4")
    pdf.add_page()
    
    # 取得中文字型
    chinese_font_path = get_chinese_font_file()
    if not chinese_font_path:
        error_msg = "錯誤：無法取得中文字型檔，請先安裝合適的中文字型！"
        print(error_msg)
        return error_msg
    
    pdf.add_font("ChineseFont", "", chinese_font_path, uni=True)
    pdf.set_font("ChineseFont", "", 12)
    
    if df is not None:
        create_table(pdf, df)
    elif text is not None:
        # 這裡就是你要修改的區塊
        pdf.multi_cell(0, 10, text)
    else:
        pdf.cell(0, 10, "沒有可呈現的內容")
    
    pdf_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    print("輸出 PDF 至檔案：", pdf_filename)
    pdf.output(pdf_filename)
    print("PDF 生成完成")
    return pdf_filename

def gradio_handler(csv_file, user_prompt):
    print("進入 gradio_handler")
    if csv_file is not None:
        print("讀取 CSV 檔案")
        df = pd.read_csv(csv_file.name)
        total_rows = df.shape[0]
        block_size = 30
        cumulative_response = ""
        block_responses = []
        
        # 依區塊處理 CSV 並依每區塊呼叫 LLM 產生報表分析結果
        for i in range(0, total_rows, block_size):
            block = df.iloc[i:i+block_size]
            block_csv = block.to_csv(index=False)
            prompt = (f"以下是CSV資料第 {i+1} 到 {min(i+block_size, total_rows)} 筆：\n"
                      f"{block_csv}\n\n請根據以下規則進行分析並產出報表：\n{user_prompt}")
            print("完整 prompt for block:")
            print(prompt)
            
            # 获取 GEMINI_API_KEY 环境变量
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                raise ValueError("未能加载 GEMINI_API_KEY，请检查 .env 文件中的配置")

            # 初始化 GenerativeModel 时不需要传入 API 密钥
            model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25')

            # 使用模型生成内容
            response = model.generate_content(contents=[prompt])
            block_response = response.text.strip()
            cumulative_response += f"區塊 {i//block_size+1}:\n{block_response}\n\n"
            block_responses.append(cumulative_response)

        # 将所有区块响应合并，并生成漂亮表格 PDF
        pdf_path = generate_pdf(text=cumulative_response)
        return cumulative_response, pdf_path
    else:
        context = "未上傳 CSV 檔案。"
        full_prompt = f"{context}\n\n{user_prompt}"
        print("完整 prompt：")
        print(full_prompt)
        
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("未能加载 GEMINI_API_KEY，请检查 .env 文件中的配置")

        # 初始化 GenerativeModel 时不需要传入 API 密钥
        model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25')

        # 使用模型生成内容
        response = model.generate_content(contents=[full_prompt])
        response_text = response.text.strip()
        print("AI 回應：")
        print(response_text)

        # 若輸入的文字包含 Markdown 表格格式，將其解析成 DataFrame 並顯示
        if " " in response_text:
            table_part = "\n".join([line for line in response_text.splitlines() if line.strip().startswith("")])
            parsed_df = parse_markdown_table(table_part)
            if parsed_df is not None:
                print("Markdown 表格解析成功：")
                print(parsed_df)
                pdf_path = generate_pdf(text=f"已解析的 Markdown 表格:\n{parsed_df}")
            else:
                pdf_path = generate_pdf(text=response_text)
        else:
            pdf_path = generate_pdf(text=response_text)
        return response_text, pdf_path


# Gradio 默认提示
default_prompt = """請根據"張智翔"同學的答題狀況進行錯誤題目預測：

"其中請特別注意：\n"
        "  1. 每個欄位皆表示為一位學生在各題的答題狀況；\n"
        "  2. 其中0表示該學生在該題答錯，1表示該題答對，\n"
        "  3. 題號後方加上"."字元，不要輸出題號及答案、題型、單元及任何的"|"字元，\n"
        "  4. 題目中須結合關於'進擊的巨人'的故事，且題目之間劇情要連貫"

根據總體37道題目答題狀況，預測該學生的錯題後重新生成一份20道數學"應用題"的題目，並使用從 Markdown 格式的表格文字提取資料，返回一個題目檔案。
例如，輸入：
      1. 台北大巨蛋體育館是一個橢圓形場館，內部東西向長230公尺、南北向長170公尺、室內高度68公尺。小葉買了一個東西向長23公分、南北向長17公分的紀念模型，請問紀念模型比例尺是多少(用比和比值兩種方式表示)


      2. 卡片上的101大樓高12.7公分，是實際的1/4000倍縮小圖，台北101大樓的實際高度是多少公尺


      3. 小葉希望自己以後也能當個選手為國爭光，每天會在操場跑步。下圖是學校操場的平面圖，比例尺為1:500，請問跑一圈約多少公尺? (圖片:中間為12x10的長方形，左右各一個半徑為5的半圓)
      .
      .
      10. ...
    會返回包含該資料的 DataFrame。"""

# Gradio UI 设计
with gr.Blocks() as demo:
    gr.Markdown("# CSV 報表生成器")
    with gr.Row():
        csv_input = gr.File(label="上傳 CSV 檔案")
        user_input = gr.Textbox(label="請輸入分析指令", lines=10, value=default_prompt)
    output_text = gr.Textbox(label="回應內容", interactive=False)
    output_pdf = gr.File(label="下載 PDF 報表")
    submit_button = gr.Button("生成報表")
    submit_button.click(fn=gradio_handler, inputs=[csv_input, user_input], outputs=[output_text, output_pdf])
demo.launch()


