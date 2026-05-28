# 1. 選擇基礎環境
FROM python:3.12-slim

# 2. 設定容器內的工作目錄
WORKDIR /app

# 3. 安裝系統層級的依賴套件 (把 libgl1-mesa-glx 改成 libgl1)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4. 複製 requirements.txt 並安裝 Python 套件
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 把專案的所有檔案複製進容器內
COPY . .

# 6. 開放 7860 Port
EXPOSE 7860

# 7. 設定啟動指令
CMD ["python", "backend/app.py"]