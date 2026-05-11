import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. 載入 .env 檔案
load_dotenv()

# 2. 使用 os 抓取 API Key
api_key = os.getenv("GEMINI_API_KEY")

# 加上防呆機制：如果沒抓到，直接丟出例外 (Exception) 中斷程式
if not api_key:
    raise ValueError("❌ 找不到 GEMINI_API_KEY！請檢查 .env 檔案是否設定正確，或重啟終端機。")

# 3. 明確地將抓到的 api_key 傳給 Client
client = genai.Client(api_key=api_key)

def analyze_catch_image(image_path):
    """
    接收圖片路徑，呼叫 Gemini 視覺模型進行辨識，回傳標籤清單。
    """
    try:
        # 讀取本機圖片並轉為 bytes
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            
        # 決定圖片的 mime_type (簡單判斷副檔名)
        mime_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"

        # 設定給 AI 的提示詞
        prompt = """你是一個專業的台灣魚類辨識專家。請分析圖片中的魚類，並嚴格以 JSON 格式回傳。
        格式範例：{"name": "魚的中文名稱", "score": 0.98, "description": "關於這條魚的簡短介紹或建議料理方式"}"""

        # 發送請求給 Gemini (使用 gemini-1.5-flash 確保有免費額度)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", # 強制回傳 JSON
            ),
        )
        
        # 解析回傳的 JSON 字串
        result_json = json.loads(response.text)
        
        # 包裝成前端 app.py 需要的 List 格式
        predictions = [{
            "name": result_json.get("name", "未知魚種"),
            "score": result_json.get("score", 0.0),
            "description": result_json.get("description", "無詳細介紹")
        }]
        
        return predictions

    except Exception as e:
        print(f"❌ Gemini 辨識發生錯誤: {e}")
        return None