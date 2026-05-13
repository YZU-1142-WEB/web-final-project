import os
import json
import base64
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv(override=True)
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ 警告：找不到 GEMINI_API_KEY，請檢查 .env 檔案！")


llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=api_key
)


def analyze_catch_image(image_bytes):
    """
    接收圖片的二進位資料 (bytes)，呼叫 Gemini 進行辨識，並回傳格式化後的串列
    """
    try:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # 設定系統提示詞，嚴格要求 AI 吐出乾淨的 JSON
        prompt = """你是一個專業的台灣魚類辨識專家。請分析圖片中的魚類，並嚴格以 JSON 格式回傳。
        絕對不要有任何 Markdown 標記 (例如 ```json)，只要純 JSON 字串。
        格式範例：{"name": "魚的中文名稱", "score": 0.98, "description": "關於這條魚的簡短介紹"}"""

        # 組合「多模態」(文字 + 圖片) 訊息
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        )

        response = llm_gemini.invoke([message])

        # 清理字串防呆機制：把 AI 可能雞婆加上的 Markdown 符號砍掉
        clean_text = response.content.replace(
            "```json", "").replace("```", "").strip()

        result_json = json.loads(clean_text)

        predictions = [{
            "name": result_json.get("name", "未知魚種"),
            "score": result_json.get("score", 0.0),
            "description": result_json.get("description", "無詳細介紹")
        }]

        return predictions

    except Exception as e:
        print(f"❌ Gemini 影像辨識錯誤: {e}")
        return None
