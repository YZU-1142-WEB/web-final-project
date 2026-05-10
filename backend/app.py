import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from LLM.LLM import llm_service
import threading
from image_identify.image_identify import Image_identify_service
from ai_task import background_ai_task

load_dotenv()

app = Flask(__name__, template_folder="../frontend/templates",
            static_folder="../frontend/static")
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key_for_dev")

CORS(app)

UPLOAD_FOLDER = 'static/uploads'
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
    status = db.Column(db.String(20), default='processing') # processing, completed, failed
    fish_type = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    flash("請先登入")
    return redirect(url_for('login'))


@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    #flash("請先登入")
    return redirect(url_for('login'))


@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({"status": "success", "message": "台灣常見魚種辨識系統 API 運作中！"})


@app.route('/api/account/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:  # 主頁
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


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if User.query.filter_by(username=username).first():
        return jsonify({"status": "error", "message": "帳號已存在"}), 400
    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"status": "success", "message": "註冊成功"})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    user = User.query.filter_by(username=data.get('username')).first()
    if user and user.password == data.get('password'):
        session['username'] = user.username
        session['user_id'] = user.id
        return jsonify({"status": "success", "message": "登入成功", "user_id": user.id})
    return jsonify({"status": "error", "message": "帳號或密碼錯誤"}), 401


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
            "status": True,
            "reply": result["reply"]
        })
    else:
        return jsonify({
            "status": False,
            "error": result["error"]
        }), 500



#更新
@app.route('/api/upload_async', methods=['POST'])
def upload_async():
    # 1. 檢查登入狀態 (因為是 API，所以回傳 JSON 錯誤，而不是 redirect)
    if 'username' not in session:
        return jsonify({"error": "請先登入"}), 401

    if 'file' not in request.files:
        return jsonify({"error": "未選取檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未選取檔案"}), 400

    if file:
        # === 步驟 1. 儲存實體檔案 ===
        filename = secure_filename(file.filename)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # === 步驟 2. 建立「號碼牌」(取代舊的 MongoDB 寫法) ===
        # 這裡的狀態設定為 'processing'，表示 AI 還沒算完
        new_record = FishRecord(
            username=session['username'],
            image_url=filename,
            status='processing'
        )
        db.session.add(new_record)
        db.session.commit()

        # === 步驟 3. 召喚背景執行緒去跑 AI！ ===
        # 把 app.app_context()、剛建好的紀錄 ID、照片路徑，丟給外面那個函數
        thread = threading.Thread(
            target=background_ai_task, 
            args=(app.app_context(), new_record.id, file_path)
        )
        thread.start() # 叫背景開始跑，主程式不等待，繼續往下走

        # === 步驟 4. 立刻回傳 JSON 給前端 ===
        # 前端的 data.record_id 就會接到這個數字，然後開始每 2 秒輪詢
        return jsonify({
            "message": "照片已接收，AI 正在背景辨識中！",
            "record_id": new_record.id
        }), 202


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ 資料庫初始化完成！")
        print("✅ 上傳資料夾準備完畢！")

    app.run(port=8000, debug=True)
