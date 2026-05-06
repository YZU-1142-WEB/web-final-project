import google.generativeai as genai
import os
import json

API=os.getenv("Gemini_")

class GeminiService:
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        """
        初始化 Gemini 服務
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model_name,
            # System Instruction 寫在這裡，能讓模型更穩定地遵循專案角色
            system_instruction="你是一位專業的開發助手，負責處理資料分析。請務必以 JSON 格式回傳結果。"
        )

    def get_analysis(self, prompt: str):
        """
        獲取分析結果
        """
        # 設定輸出格式為 JSON
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.95,
            "max_output_tokens": 1024,
            "response_mime_type": "application/json", # 強制 Gemini 輸出 JSON
        }

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # 解析回傳的 JSON 字串
            return json.loads(response.text)
            
        except Exception as e:
            return {"error": str(e), "status": "error"}

# --- 專案整合範例 ---
if __name__ == "__main__":
    # 請確保已設定環境變數或直接填入 API KEY
    GOOGLE_API_KEY = "YOUR_GEMINI_API_KEY"
    
    gemini = GeminiService(api_key=GOOGLE_API_KEY)
    
    # 模擬專案輸入（例如：影像辨識後的標籤）
    user_data = {
        "task": "fish_species_identification",
        "tags": ["Betta", "Avatar Blue", "Healthy"],
        "context": "2-foot tank"
    }
    
    test_prompt = f"分析以下數據並給予建議：{json.dumps(user_data)}"
    
    result = gemini.get_analysis(test_prompt)
    print(json.dumps(result, indent=4, ensure_ascii=False))