from flask import Flask, request, jsonify
import os
import json
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv

# 讀取環境變數 (結合隊友的設定方式)
load_dotenv("API.env") 

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------
# 1. 將你的服務包裝成類別，保留未來擴充性與 JSON 處理能力
# ---------------------------------------------------------
class GeminiService:
    def __init__(self):
        # 取得金鑰
        api_key = os.getenv("gemini_API_Key")
        if not api_key:
            print("錯誤：找不到 API Key，請檢查 API.env 檔案設定")
            
        genai.configure(api_key=api_key)
        
        # 結合隊友的魚類專家 System Instruction
        self.model = genai.GenerativeModel(
            model_name='gemini-2.5-flash-lite',
            system_instruction=(
                "你是一位專業的台灣魚種專家，專門回答台灣魚類分布、習性、釣法等問題。\n"
                "請遵守以下規則：\n"
                "1. 只能回答關於魚類、生態、習性、釣法及台灣釣點相關問題。\n"
                "2. 如果使用者詢問無關問題（如政治、數學、程式），請禮貌地回絕並導回魚類話題。\n"
                "3. 輸出請使用繁體中文，並使用台灣慣用語（例如：稱呼『吳郭魚』而非『羅非魚』）。\n"
                "4. 若提到保育類魚種，請務必提醒使用者禁止捕撈。\n"
                "5. 語氣要專業且像一位資深的釣客前輩。"
            )
        )

    def chat(self, prompt: str):
        """
        處理一般對話請求
        """
        try:
            response = self.model.generate_content(prompt)
            return {"success": True, "reply": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_image_tags(self, tags_data: dict):
        """
        保留你原先的 JSON 處理邏輯，未來可專門用來處理影像辨識傳來的標籤
        """
        generation_config = {
            "temperature": 0.2,
            "response_mime_type": "application/json",
        }
        prompt = f"請分析以下影像辨識標籤並以 JSON 格式給予魚種建議：{json.dumps(tags_data)}"
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            return {"success": True, "data": json.loads(response.text)}
        except Exception as e:
            return {"success": False, "error": str(e)}

# 初始化 Gemini 服務
llm_service = GeminiService()

# ---------------------------------------------------------
# 2. 保留隊友的 Flask 路由，作為前端呼叫的 API 接口
# ---------------------------------------------------------
@app.route('/api/LLM', methods=['POST'])
def chat_endpoint():
    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({"success": False, "error": "請提供問題"}), 400

    print(f"正在詢問 Gemini: {user_message}")
    
    # 呼叫類別中的 chat 方法
    result = llm_service.chat(user_message)

    if result["success"]:
        return jsonify({
            "success": True,
            "reply": result["reply"]
        })
    else:
        print(f"Gemini 呼叫失敗: {result['error']}")
        return jsonify({
            "success": False, 
            "error": "模型思考中發生錯誤，請稍後再試。"
        }), 500

if __name__ == '__main__':
    # 啟動 Flask 伺服器
    app.run(port=3000, debug=True)