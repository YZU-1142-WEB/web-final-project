import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from LLM.LLM import llm_service
import threading
from image_identify.image_identify import analyze_catch_image
from ai_task import background_ai_task
import markdown
import uuid

load_dotenv()

app = Flask(__name__, template_folder="../frontend/templates",
            static_folder="../frontend/static")
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key_for_dev")

CORS(app)

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'sqlite:///fishdb.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# === 新增這段：紀錄照片與處理狀態 ===


class FishRecord(db.Model):
    __tablename__ = 'fish_records'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='processing')
    fish_type = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    flash("請先登入")
    return redirect(url_for('login'))


recognition_results = {}
# 這裡先用全域變數 如果有空的話可以改為存進資料庫 (模擬存放 AI 辨識結果的資料庫 重啟後會消失)# ==========================================


@app.route('/api/upload_async', methods=['POST'])
def upload_async():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401

    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "未接收到檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "未選取檔案"}), 400

    if file:
        # 1. 儲存檔案到本地 (未來部署時這裡會改成存到 Google Cloud Storage)
        filename = secure_filename(file.filename)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # 👉 2. 真正寫入資料庫！建立一筆「處理中」的紀錄
        new_record = FishRecord(
            username=session['username'],
            image_url=filename,
            status='processing'
        )
        db.session.add(new_record)
        db.session.commit()

        # 取得資料庫自動產生的流水號 ID 作為 task_id
        task_id = new_record.id

        # 3. 定義背景工作
        def ai_worker(record_id, path):
            # 👉 關鍵修復：背景執行緒必須注入 app_context 才能操作資料庫！
            with app.app_context():
                # 把剛才那筆紀錄從資料庫拿出來
                record = FishRecord.query.get(record_id)
                if not record:
                    return

                try:
                    # 呼叫 AI 辨識
                    predictions = analyze_catch_image(path)

                    if predictions:
                        best_match = predictions[0]
                        record.fish_type = f"{best_match['name']} (信心度: {best_match['score']*100:.1f}%)"
                        record.description = best_match.get(
                            'description', '無詳細介紹')
                    else:
                        record.fish_type = "圖片中未偵測到明顯魚類"
                        record.description = "無法提供介紹"

                    # 標記為完成並儲存回資料庫
                    record.status = 'completed'
                    db.session.commit()

                except Exception as e:
                    print(f"❌ 背景辨識錯誤: {e}")
                    record.status = 'failed'
                    db.session.commit()

        # 4. 啟動 Thread 背景執行
        thread = threading.Thread(target=ai_worker, args=(task_id, file_path))
        thread.start()

        return jsonify({
            "status": "success",
            "task_id": task_id,
            "message": "檔案已上傳，開始辨識"
        })


@app.route('/api/check_task/<task_id>')
def check_task(task_id):
    # 👉 直接去資料庫查詢狀態
    record = FishRecord.query.get(task_id)
    if not record:
        return jsonify({"status": "not_found"})

    # 轉換成前端需要的 JSON 格式
    return jsonify({
        "status": record.status,
        "fish_name": record.fish_type
    })


@app.route('/result/<task_id>')
def result_page(task_id):
    # 👉 直接從資料庫撈取結果渲染畫面
    record = FishRecord.query.get(task_id)
    if not record or record.status != 'completed':
        return redirect(url_for('home'))

    return render_template('result.html',
                           img_file=record.image_url,
                           fish_name=record.fish_type,
                           description=record.description)
# picture


@app.route('/api/upload_async', methods=['POST'])
def upload_async():
    # 1. 檢查登入狀態
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401

    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "未接收到檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "未選取檔案"}), 400

    if file:
        filename = secure_filename(file.filename)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        task_id = filename
        recognition_results[task_id] = {"status": "processing"}

        # --- 2. 定義背景工作 (注意縮排要包在 if file: 裡面) ---
        def ai_worker(tid, fname, path):
            try:
                # 呼叫剛剛寫好的辨識函式
                predictions = analyze_catch_image(path)

                if predictions:
                    # 取得信心指數最高的結果
                    best_match = predictions[0]
                    ai_result = f"{best_match['name']} (信心度: {best_match['score']*100:.1f}%)"
                else:
                    ai_result = "圖片中未偵測到明顯魚類"

                recognition_results[tid] = {
                    "status": "completed",
                    "img_file": fname,
                    "fish_name": ai_result,
                    "all_predictions": predictions
                }
            except Exception as e:
                print(f"❌ 背景辨識錯誤: {e}")
                recognition_results[tid] = {
                    "status": "failed",
                    "error_message": str(e)
                }

        # --- 3. 剛剛不小心被刪掉的關鍵啟動區塊 ---
        # 啟動 Thread 讓辨識在背景執行，不卡死主程式
        thread = threading.Thread(
            target=ai_worker, args=(task_id, filename, file_path))
        thread.start()

        # 立刻回傳 JSON 給前端，讓前端開始轉圈圈並去 check_task
        return jsonify({
            "status": "success",
            "task_id": task_id,
            "message": "檔案已上傳，開始辨識"
        })

# --- 4. 配合用的路由：檢查進度 ---


@app.route('/api/check_task/<task_id>')
def check_task(task_id):
    result = recognition_results.get(task_id, {"status": "not_found"})
    return jsonify(result)

# --- 5. 配合用的路由：顯示最終結果頁 ---


@app.route('/result/<task_id>')
def result_page(task_id):
    result = recognition_results.get(task_id)
    if not result or result['status'] != 'completed':
        return redirect(url_for('home'))

    # 把 description 從字典裡挖出來
    description = "無詳細介紹"
    if result.get('all_predictions') and len(result['all_predictions']) > 0:
        description = result['all_predictions'][0].get('description', '無詳細介紹')

    #  把 description 一起打包上車傳給前端
    return render_template('result.html',
                           img_file=result['img_file'],
                           fish_name=result['fish_name'],
                           description=description)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ 資料庫初始化完成！")
        print("✅ 上傳資料夾準備完畢！")

    app.run(port=8000, debug=True)
