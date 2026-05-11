import os
from ultralytics import YOLO

# --- 自動路徑定位 ---
# 取得目前這個檔案 (image_identify.py) 的絕對路徑資料夾
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 組合出模型檔案的完整路徑：.../backend/image_identify/yolov8n.pt
MODEL_PATH = os.path.join(CURRENT_DIR, "yolov8n.pt")

# 在模組載入時就先初始化模型，避免每次辨識都要重新讀取檔案
try:
    if os.path.exists(MODEL_PATH):
        # 載入你剛下載的 YOLOv8 權重
        model = YOLO(MODEL_PATH)
        print(f"✅ [AI 服務] 成功從 {MODEL_PATH} 載入模型")
    else:
        print(f"❌ [AI 服務] 找不到模型檔：{MODEL_PATH}")
        model = None
except Exception as e:
    print(f"⚠️ [AI 服務] 模型載入發生錯誤: {e}")
    model = None

def analyze_catch_image(image_path):
    """
    接收圖片路徑，使用 YOLO 進行辨識，回傳標籤清單。
    """
    if model is None:
        raise Exception("AI 模型未就緒，請檢查 yolov8n.pt 是否存在。")

    # 執行推論
    results = model(image_path)
    result = results[0]  # 取得第一張圖片的結果
    
    predictions = []
    
    # 如果有偵測到物體 (boxes)
    if len(result.boxes) > 0:
        for box in result.boxes:
            class_id = int(box.cls)      # 類別 ID
            name = result.names[class_id] # 類別名稱 (如 'fish')
            score = float(box.conf)      # 信心指數
            
            predictions.append({
                "name": name,
                "score": round(score, 4)
            })
            
    return predictions