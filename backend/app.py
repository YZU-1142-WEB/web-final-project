import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

#引入LLM 垃圾LLM 垃圾Gemini
from LLM.LLM import llm_service

#讀入垃圾AI的Key
load_dotenv(".env")

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


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    flash("請先登入")
    return redirect(url_for('login'))

#主頁
@app.route('/home')
def home():
    # 檢查有沒有登入，有登入才給看 index.html
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    
    # 沒登入的話，趕回登入頁面
    flash("請先登入")
    return redirect(url_for('login'))


@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({"status": "success", "message": "台灣常見魚種辨識系統 API 運作中！"})


@app.route('/api/account/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:#主頁
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
    # 檢查權限 (可選，如果你希望登入後才能用)
    # if 'username' not in session:
    #     return jsonify({"success": False, "error": "請先登入"}), 401

    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({"success": False, "error": "請提供問題"}), 400

    # 呼叫剛才 import 進來的工具
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


@app.route('/api/upload', methods=['POST'])
def upload():
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash("未選取檔案")
        return redirect(url_for('dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash("未選取檔案")
        return redirect(url_for('dashboard'))

    if file:
        # 1. 儲存檔案
        filename = secure_filename(file.filename)
        # 建議加上時間戳記避免重複
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # 2. 丟給 AI (這裡先用模擬數據)
        # ai_result = predict_fish_species(file_path)
        ai_result = "吳郭魚 (AI 測試結果)"

        # 3. 存入資料庫(需要改成 SQLAlchemy)
#        mongo.db.fish_records.insert_one({
#            'username': session['username'],
#            'image_url': filename,
#            'fish_type': ai_result,
#            'upload_time': datetime.now()
#       })

        # 4. 直接渲染結果頁面
        return render_template('result.html', filename=filename, fish_type=ai_result)

    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ 資料庫初始化完成！")
        print("✅ 上傳資料夾準備完畢！")

    app.run(port=8000, debug=True)
