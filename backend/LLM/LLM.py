import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 確保環境變數有被載入
load_dotenv()


class GeminiService:
    def __init__(self):
        # 從環境變數讀取 Key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("警告：找不到 API Key")

        # 使用新版的 Client 寫法初始化
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.5-flash-lite'

        # 將設定存起來，稍後發送請求時會用到
        self.system_instruction = (
            "你是一位專業的台灣魚種專家，專門回答台灣魚類分布、習性、釣法等問題。\n"
            "請遵守以下規則：\n"
            "1. 只能回答關於魚類、生態、習性、釣法及台灣釣點相關問題。\n"
            "2. 如果使用者詢問無關問題（如政治、數學、程式），請禮貌地回絕並導回魚類話題。\n"
            "3. 輸出請使用繁體中文，並使用台灣慣用語（例如：稱呼『吳郭魚』而非『羅非魚』）。\n"
            "4. 若提到保育類魚種，請務必提醒使用者禁止捕撈。\n"
            "5. 語氣要專業且像一位資深的釣客前輩。"
        )

    '''
    def chat(self, prompt: str):
        try:
            # 新版發送請求的寫法
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction
                )
            )
            return {"success": True, "reply": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}
    '''

    def chat(self, prompt: str, history=None):
        if history is None:
            history = []
            
        try:
            # 準備傳給 Gemini 的完整對話內容
            contents = []

            # 1. 載入之前的歷史紀錄
            for msg in history:
                # Flask Session 裡我們存 user/assistant，這裡要把它轉成 Google 需要的 user/model
                role = "user" if msg["role"] == "user" else "model"
                
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg["content"])]
                    )
                )

            # 2. 加入這次最新輸入的問題
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )
            )

            # 3. 發送帶有記憶的請求
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction
                )
            )
            return {"success": True, "reply": response.text}
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Gemini API 發生錯誤: {e}")

            #  攔截 429 頻率限制錯誤
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                return {
                    "success": False, 
                    "error": "AI 稍微喘口氣中！ 您問得太快了，請等待 1 分鐘後再繼續發問。"
                }

            return {"success": False, "error": str(e)}


# 初始化執行個體供外部直接使用
llm_service = GeminiService()
