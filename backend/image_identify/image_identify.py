import os
import json
import base64
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# 載入環境變數
load_dotenv(override=True)
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("❌ 找不到 API Key！")

# 這裡直接套用你剛剛測試成功的 LangChain 寫法！
# 建議用 gemini-2.5-flash 或 gemini-1.5-flash，因為它們看圖片比較聰明
llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash", 
    google_api_key=api_key
)

def encode_image(image_path):
    """將圖片轉成 Base64 格式給 LangChain 讀取"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_catch_image(image_path):
    try:
        # 1. 圖片轉碼
        base64_image = encode_image(image_path)
        
        # 2. 組合 LangChain 支援的「多模態 (文字+圖片)」訊息格式
        message = HumanMessage(
            content=[
                {
                    "type": "text", 
                    "text": """你是一個專業的台灣魚類辨識專家。請分析圖片中的魚類，並嚴格以 JSON 格式回傳。不要有任何 Markdown 標記 (如 ```json)。
                    格式範例：{"name": "魚的中文名稱", "score": 0.98, "description": "關於這條魚的簡短介紹或建議料理方式"}"""
                },
                {
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                }
            ]
        )
        
        # 3. 發送請求！(走你剛剛證明會通的那條路)
        response = llm_gemini.invoke([message])
        
        # 4. 解析 JSON
        # 把 AI 可能會雞婆加上的 Markdown 標籤清乾淨
        clean_text = response.content.replace("```json", "").replace("```", "").strip()
        result_json = json.loads(clean_text)
        
        # 5. 包裝回傳給 Flask
        predictions = [{
            "name": result_json.get("name", "未知魚種"),
            "score": result_json.get("score", 0.0),
            "description": result_json.get("description", "無詳細介紹")
        }]
        
        return predictions

    except Exception as e:
        print(f"❌ LangChain 影像辨識錯誤: {e}")
        return None