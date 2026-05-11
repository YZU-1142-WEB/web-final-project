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
import time

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
    # processing, completed, failed
    status = db.Column(db.String(20), default='processing')
    fish_type = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    flash("請先登入")
    return redirect(url_for('login'))


# 這裡先用全域變數 如果有空的話可以改為存進資料庫 (模擬存放 AI 辨識結果的資料庫 重啟後會消失)
recognition_results = {}


@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    # flash("請先登入")
    return redirect(url_for('login'))


@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({"status": "success", "message": "台灣常見魚種辨識系統 API 運作中！"})


@app.route('/camera')
def camera_page():
    if 'username' in session:
        return render_template('camera.html', username=session['username'])
    flash("請先登入")
    return redirect(url_for('login'))


@app.route('/api/account/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            session['username'] = user.username
            session['user_id'] = user.id
            return redirect(url_for('home'))
        flash("帳號或密碼錯誤")
    return render_template('login.html')


@app.route('/api/account/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        existing_user = User.query.filter_by(username=username).first()
        if existing_user is None:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash("註冊成功，請登入！")
            return redirect(url_for('login'))
        flash("該帳號已存在！")
    return render_template('register.html')


@app.route('/api/account/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    flash("您已成功登出")
    return redirect(url_for('login'))


@app.route('/api/LLM', methods=['POST'])
def chat_endpoint():
    if 'username' not in session:
        return jsonify({"success": False, "error": "請先登入"}), 401
    data = request.get_json()
    user_message = data.get('input_text')
    if not user_message:
        return jsonify({"success": False, "error": "請提供問題"}), 400
    result = llm_service.chat(user_message)

    if result["success"]:
        return jsonify({
            "success": True,
            "reply": result["reply"]
        })
    else:
        return jsonify({
            "success": False,
            "error": result["error"]
        }), 500


# 更新
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
        thread = threading.Thread(target=ai_worker, args=(task_id, filename, file_path))
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

    # 這裡渲染你原本的 result.html
    return render_template('result.html',
                           img_file=result['img_file'],
                           fish_name=result['fish_name'])


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ 資料庫初始化完成！")
        print("✅ 上傳資料夾準備完畢！")

    app.run(port=8000, debug=True)
