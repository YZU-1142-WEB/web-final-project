# 從 flask 套件中引入核心功能：Flask(伺服器)、request(接收資料)、jsonify(輸出 JSON)
from flask import Flask, request, jsonify
# 引入 os 模組，用於讀取作業系統的環境變數或檔案路徑
import os
# 引入 CORS，解決瀏覽器跨來源資源共用（跨網域）的安全性限制問題
from flask_cors import CORS
# 引入 Google 官方提供的 Gemini AI SDK
import google.generativeai as genai
# 引入 dotenv，用來讀取專案資料夾中的 .env 環境設定檔
from dotenv import load_dotenv 



# 指定讀取位於 backend/LLM/ 資料夾底下的 API.env 檔案
load_dotenv("API.env") 

# 實例化 Flask 應用程式物件，__name__ 代表目前執行的模組名稱
app = Flask(__name__)
# 啟動 CORS 功能，允許所有來源的網頁存取這個伺服器的 API
CORS(app)

# 透過 os.getenv 從系統環境變數中取得名為 "gemini_API_Key" 的數值（即 API 金鑰）
Gemini_API_KEY = os.getenv("gemini_API_Key")

# 檢查是否成功取得 API Key
if Gemini_API_KEY:
    # 若存在，則將金鑰設定到 Gemini 的 SDK 中進行認證
    genai.configure(api_key=Gemini_API_KEY)
else:
    # 若不存在，則在後端終端機印出錯誤訊息提醒開發者
    print("錯誤：找不到 API Key，請檢查 API.env 檔案設定")

# 初始化 Gemini 模型
model = genai.GenerativeModel(
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

# 設定一個 API 路由位址為 '/api/chat'，且限定只能使用 POST 方法存取
@app.route('/api/LLM', methods=['POST'])


def chat():
    # 讀取前端傳來的 JSON 資料格式
    data = request.get_json()
    # 從資料中取得 key 為 'message' 的內容（使用者的提問）
    user_message = data.get('message')

    # 防呆機制：如果前端沒有傳送 message 字串，則回傳錯誤
    if not user_message:
        # 回傳 JSON 格式的錯誤訊息，並給予 HTTP 狀態碼 400 (用戶請求錯誤)
        return jsonify({"success": False, "error": "請提供問題"}), 400

    try:
        # 在後端終端機印出目前的進度，方便 Debug
        print(f"正在詢問 Gemini: {user_message}")
        
        # 呼叫 Gemini SDK 的核心方法，將使用者訊息送出並等待生成結果
        response = model.generate_content(user_message)
        
        # 從 Gemini 回傳的物件中提取出生成的純文字內容
        llm_response_text = response.text

        # 回傳成功的 JSON 結果給前端，包含 success 狀態與模型回覆的文字
        return jsonify({
            "success": True,
            "reply": llm_response_text
        })

    except Exception as e:
        # 如果在呼叫 API 過程中發生任何意外（如網路斷線、API 額度爆量等）
        print(f"Gemini 呼叫失敗: {e}")
        # 回傳失敗的 JSON 訊息，並給予 HTTP 狀態碼 500 (伺服器端錯誤)
        return jsonify({
            "success": False, 
            "error": "模型思考中發生錯誤，請稍後再試。"
        }), 500

# 判斷是否為直接執行此檔案（而非作為模組被引用）
if __name__ == '__main__':
    # 啟動 Flask 伺服器，設定運行在 3000 埠 (Port 3000)
    # debug=True 代表開發模式，程式碼修改存檔後會自動重啟，方便開發
    app.run(port=3000, debug=True)