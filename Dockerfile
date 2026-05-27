# 1. 準備基礎環境：我們要一台安裝了 Python 3.12 輕量版作業系統的雲端機器
FROM python:3.12-slim

# 2. 建立工作區：在雲端機器裡面建立一個名為 /app 的資料夾，並把這裡當作我們的工作目錄
WORKDIR /app

# 3. 安裝系統底層工具（這步對你的專案最重要！）
# 因為你的專案有用到 YOLOv8 進行影像辨識，底層會呼叫 OpenCV 來處理圖片。
# 雲端主機預設是一張白紙，沒有處理影像的系統工具，所以我們必須先安裝這兩個 lib 函式庫，否則模型一讀取圖片就會報錯。
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4. 準備 Python 套件：把你的 requirements.txt 複製到雲端機器裡，然後請它下載安裝所有套件
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 複製程式碼：把你電腦裡這個專案的所有檔案 (包含 backend, frontend 等)，全部複製進雲端機器的 /app 資料夾裡
COPY . .

# 6. 打開通道：告訴雲端機器，我們要對外開放 7860 這個通訊埠 (Hugging Face 規定的通道)
EXPOSE 7860

# 7. 啟動伺服器：最後一個指令，教雲端機器如何把你的網站跑起來
CMD ["python", "backend/app.py"]