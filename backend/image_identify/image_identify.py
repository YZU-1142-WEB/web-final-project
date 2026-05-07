import os
import io
from dotenv import load_dotenv
from google.cloud import vision

# 1. 載入 .env 檔案中的變數
# 這會自動把 .env 裡面的設定塞進系統的環境變數 (os.environ) 中
load_dotenv() 

# 2. 安全地讀取變數 (僅供測試印出，確認 .env 有設定成功)
credential_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
print(f"目前使用的 GCP 憑證路徑是: {credential_path}")

def analyze_catch_image(image_path):
    """
    接收圖片路徑，呼叫 Google Vision API，並回傳辨識到的標籤與信心指數。
    """
    # 1. 建立 Vision API 的客戶端
    client = vision.ImageAnnotatorClient()

    # 2. 讀取實體圖片檔案
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)

    # 3. 發送請求給 Google，要求進行「標籤偵測 (Label Detection)」
    response = client.label_detection(image=image)
    labels = response.label_annotations

    # 4. 錯誤處理：如果 API 呼叫失敗
    if response.error.message:
        raise Exception(f'API 呼叫失敗: {response.error.message}')

    # 5. 整理回傳資料
    results = []
    for label in labels:
        results.append({
            "name": label.description,      # 辨識出的名稱 (例如: Fish, Ray-finned fish, Bass)
            "score": round(label.score, 4)  # 信心指數 (0.0 ~ 1.0)
        })
        
    return results

# 測試區塊 (只有在直接執行這個檔案時才會跑，被 Flask import 時不會跑這裡)
if __name__ == "__main__":
    # 請確保你的專案資料夾裡有一張叫做 test_fish.jpg 的照片來測試
    test_image = "./test_fish.jpg" 
    print("正在辨識中...")
    
    try:
        predictions = analyze_catch_image(test_image)
        print("辨識結果：")
        for p in predictions:
            print(f"標籤: {p['name']} | 信心指數: {p['score']*100:.2f}%")
    except Exception as e:
        # 如果路徑錯誤或金鑰沒設定好，這裡會清楚印出錯誤原因
        print(f"發生錯誤：{e}")