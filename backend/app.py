import os
import base64
import threading
import uuid
import markdown
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from LLM.LLM import llm_service
from image_identify.image_identify import analyze_catch_image

load_dotenv()

app = Flask(__name__, template_folder="../frontend/templates",
            static_folder="../frontend/static")
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key_for_dev")

CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'sqlite:///fishdb.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FishRecord(db.Model):
    __tablename__ = 'fish_records'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    image_url = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='processing')
    fish_type = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==========================================
# 帳號系統與基本網頁路由
# ==========================================


@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    flash("請先登入")
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    flash("請先登入")
    return redirect(url_for('login'))


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


# ==========================================
# LLM 聊天室路由 (保留同學的非同步機制)
# ==========================================

llm_tasks = {}


@app.route('/api/llm/ask', methods=['POST'])
def ask_llm_async():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401

    data = request.get_json()
    user_message = data.get('input_text')

    if not user_message:
        return jsonify({"status": "error", "message": "請提供問題"}), 400

    task_id = f"llm_{uuid.uuid4().hex[:8]}"
    llm_tasks[task_id] = {"status": "processing"}

    def llm_worker(tid, msg):
        try:
            result = llm_service.chat(msg)
            if result.get("success"):
                html_reply = markdown.markdown(
                    result["reply"], extensions=['nl2br'])
                llm_tasks[tid] = {
                    "status": "completed",
                    "question": msg,
                    "reply": html_reply
                }
            else:
                llm_tasks[tid] = {"status": "failed",
                                  "error_message": result.get("error", "AI 發生錯誤")}
        except Exception as e:
            llm_tasks[tid] = {"status": "failed", "error_message": str(e)}

    thread = threading.Thread(target=llm_worker, args=(task_id, user_message))
    thread.start()
    return jsonify({"status": "success", "task_id": task_id, "message": "AI 正在思考中..."})


@app.route('/api/llm/check_task/<task_id>')
def check_llm_task(task_id):
    return jsonify(llm_tasks.get(task_id, {"status": "not_found"}))


@app.route('/api/llm/result/<task_id>')
def llm_result_page(task_id):
    result = llm_tasks.get(task_id)
    if not result or result['status'] != 'completed':
        return redirect(url_for('home'))

    session['chat_history'] = [
        {"role": "user", "content": result['question']},
        {"role": "assistant", "content": result['reply']}
    ]
    session.modified = True

    return render_template('llm_result.html', question=result['question'], reply=result['reply'])

# ==========================================
# 圖片上傳與 AI 辨識路由 (修復：回歸 DB 架構 + 同學防呆邏輯)
# ==========================================


@app.route('/api/picture/upload', methods=['POST'])
def upload_async():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "未接收到檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "未選取檔案"}), 400

    if file:
        img_bytes = file.read()
        base64_str = base64.b64encode(img_bytes).decode('utf-8')
        mime_type = file.mimetype or 'image/jpeg'
        image_data_uri = f"data:{mime_type};base64,{base64_str}"

        new_record = FishRecord(
            username=session['username'],
            image_url=image_data_uri,
            status='processing'
        )
        db.session.add(new_record)
        db.session.commit()

        task_id = new_record.id

        def ai_worker(tid, raw_bytes):
            with app.app_context():
                record = FishRecord.query.get(tid)
                if not record:
                    return

                try:
                    predictions = analyze_catch_image(raw_bytes)

                    # 👉 整合同學的：如果判斷不是魚，直接更新資料庫為 not_fish 並中斷
                    if predictions and predictions[0].get("is_fish") == False:
                        record.status = 'not_fish'
                        db.session.commit()
                        return

                    # 👉 整合同學的：如果判斷不是台灣魚，更新資料庫為 not_TW_fish 並中斷
                    if predictions and predictions[0].get("is_TW_fish") == False:
                        record.status = 'not_TW_fish'
                        db.session.commit()
                        return

                    # 正常魚類處理邏輯
                    if predictions:
                        best_match = predictions[0]
                        record.fish_type = f"{best_match['name']} (信心度: {best_match['score']*100:.1f}%)"
                        record.description = best_match.get(
                            'description', '無詳細介紹')
                    else:
                        record.fish_type = "圖片中未偵測到明顯魚類"
                        record.description = "無法提供介紹"

                    record.status = 'completed'
                    db.session.commit()

                except Exception as e:
                    print(f"❌ 背景辨識錯誤: {e}")
                    record.status = 'failed'
                    record.fish_type = f"辨識失敗: {str(e)}"
                    db.session.commit()

        thread = threading.Thread(target=ai_worker, args=(task_id, img_bytes))
        thread.start()

        return jsonify({
            "status": "success",
            "task_id": task_id,
            "message": "檔案已上傳，開始辨識"
        })


@app.route('/api/picture/check_task/<task_id>')
def check_task(task_id):
    # 改回從資料庫查詢最新狀態
    record = FishRecord.query.get(task_id)
    if not record:
        return jsonify({"status": "not_found"})

    # 👉 讓前端的 script.js 也能正確收到 not_fish 狀態
    return jsonify({
        "status": record.status,
        "fish_name": record.fish_type
    })


@app.route('/api/picture/result/<task_id>')
def result_page(task_id):
    record = FishRecord.query.get(task_id)
    if not record or record.status != 'completed':
        return redirect(url_for('home'))

    return render_template('result.html',
                           img_file=record.image_url,
                           fish_name=record.fish_type,
                           description=record.description)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ 資料庫初始化完成！")
    app.run(port=8000, debug=True)
