import os
import json
import base64
import threading            
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# ============== Flask App 初始化 ==============
load_dotenv(override=True)
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///fish_records.db')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), '../frontend/static/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

CORS(app)
db = SQLAlchemy(app)

# 確保上傳資料夾存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============== API Key 檢查 ==============
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("⚠️  警告：找不到 GEMINI_API_KEY，圖片分析功能將不可用")

# ============== LLM 初始化 ==============
if api_key:
    llm_gemini = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash", 
        google_api_key=api_key
    )
    llm_chat = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=api_key
    )
else:
    llm_gemini = None
    llm_chat = None

# ============== 資料庫模型 ==============
class User(db.Model):
    """使用者模型"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    records = db.relationship('FishRecord', backref='user', lazy=True, cascade='all, delete-orphan')

class FishRecord(db.Model):
    """魚類辨識紀錄"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_filename = db.Column(db.String(255), nullable=False)
    fish_type = db.Column(db.String(255), nullable=True)
    fish_score = db.Column(db.Float, nullable=True)
    fish_description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='processing')  # processing, completed, failed
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============== 登入檢查裝飾器 ==============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# ============== 圖片分析函數 ==============
def encode_image(image_path):
    """將圖片轉成 Base64 格式給 LangChain 讀取"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"❌ 圖片找不到: {image_path}")
        return None
    except Exception as e:
        print(f"❌ 圖片編碼錯誤: {e}")
        return None

def analyze_catch_image(image_path):
    """分析魚類圖片"""
    if not llm_gemini:
        return {
            "name": "API 未配置",
            "score": 0.0,
            "description": "請設定 GEMINI_API_KEY 環境變數"
        }
    
    try:
        # 1. 圖片轉碼
        base64_image = encode_image(image_path)
        if not base64_image:
            raise Exception("圖片編碼失敗")
        
        # 2. 組合 LangChain 支援的「多模態 (文字+圖片)」訊息格式
        message = HumanMessage(
            content=[
                {
                    "type": "text", 
                    "text": """你是一個專業的台灣魚類辨識專家。請分析圖片中的魚類，並嚴格以 JSON 格式回傳。不要有任何 Markdown 標記 (如 ```json)。
                    格式範例：{"name": "魚的中文名稱", "score": 0.98, "description": "關於這條魚的簡短介紹或建議料理方式"}"""
                },
                {
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                }
            ]
        )
        
        # 3. 發送請求
        response = llm_gemini.invoke([message])
        
        # 4. 解析 JSON - 移除 Markdown 標籤
        clean_text = response.content.replace("```json", "").replace("```", "").strip()
        result_json = json.loads(clean_text)
        
        return {
            "name": result_json.get("name", "未知魚種"),
            "score": result_json.get("score", 0.0),
            "description": result_json.get("description", "無詳細介紹")
        }

    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析錯誤: {e}")
        return {
            "name": "解析失敗",
            "score": 0.0,
            "description": "AI 回應格式不正確"
        }
    except Exception as e:
        print(f"❌ 影像辨識錯誤: {e}")
        return {
            "name": "辨識失敗",
            "score": 0.0,
            "description": str(e)
        }

def background_ai_analysis(record_id, image_path):
    """後台執行 AI 辨識"""
    with app.app_context():
        try:
            record = FishRecord.query.get(record_id)
            if not record:
                return
            
            # 執行 AI 分析
            result = analyze_catch_image(image_path)
            
            # 更新資料庫
            record.fish_type = result.get("name", "未知魚種")
            record.fish_score = result.get("score", 0.0)
            record.fish_description = result.get("description", "")
            record.status = 'completed'
            
        except Exception as e:
            record = FishRecord.query.get(record_id)
            if record:
                record.status = 'failed'
                record.error_message = str(e)
                print(f"❌ 後台任務錯誤 (ID: {record_id}): {e}")
        
        finally:
            db.session.commit()

# ============== 路由: 認證相關 ==============
@app.route('/register', methods=['GET', 'POST'])
def register_page():
    """註冊頁面"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return render_template('register.html', error='帳號和密碼不能為空'), 400
        
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='帳號已存在'), 400
        
        try:
            new_user = User(
                username=username,
                password=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login_page'))
        except Exception as e:
            db.session.rollback()
            return render_template('register.html', error=f'註冊失敗: {str(e)}'), 500
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """登入頁面"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password, password):
            return render_template('login.html', error='帳號或密碼錯誤'), 401
        
        session['user_id'] = user.id
        session['username'] = user.username
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """登出"""
    session.clear()
    return redirect(url_for('login_page'))

# ============== 路由: 頁面 ==============
@app.route('/')
@login_required
def index():
    """首頁"""
    return render_template('index.html')

@app.route('/camera')
@login_required
def camera_page():
    """相機/上傳頁面"""
    return render_template('camera.html')

@app.route('/result/<int:record_id>')
@login_required
def result_page(record_id):
    """結果頁面"""
    record = FishRecord.query.get(record_id)
    
    if not record or record.user_id != session.get('user_id'):
        return "找不到紀錄", 404
    
    return render_template('result.html', 
                          fish_name=record.fish_type,
                          fish_score=record.fish_score,
                          fish_description=record.fish_description,
                          img_file=record.image_filename)

# ============== 路由: API ==============
@app.route('/api/upload_async', methods=['POST'])
@login_required
def upload_async():
    """非同步上傳圖片並啟動 AI 辨識"""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "沒有檔案"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "檔案名稱為空"}), 400
    
    try:
        # 生成安全的檔名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 保存檔案
        file.save(filepath)
        
        # 建立資料庫紀錄
        record = FishRecord(
            user_id=session['user_id'],
            image_filename=filename,
            status='processing'
        )
        db.session.add(record)
        db.session.commit()
        
        # 啟動後台任務
        thread = threading.Thread(
            target=background_ai_analysis,
            args=(record.id, filepath)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "success",
            "task_id": record.id,
            "message": "上傳成功，AI 正在分析..."
        }), 200
        
    except Exception as e:
        print(f"❌ 上傳錯誤: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/check_task/<int:task_id>', methods=['GET'])
@login_required
def check_task_status(task_id):
    """檢查任務狀態"""
    try:
        record = FishRecord.query.get(task_id)
        
        if not record:
            return jsonify({"status": "not_found"}), 404
        
        if record.user_id != session.get('user_id'):
            return jsonify({"status": "forbidden"}), 403
        
        return jsonify({
            "status": record.status,
            "fish_name": record.fish_type,
            "fish_score": record.fish_score,
            "fish_description": record.fish_description,
            "error_message": record.error_message
        }), 200
        
    except Exception as e:
        print(f"❌ 檢查狀態錯誤: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/LLM', methods=['POST'])
@login_required
def llm_chat():
    """LLM 聊天接口"""
    if not llm_chat:
        return jsonify({
            "success": "error",
            "reply": "API 未配置，請設定 GEMINI_API_KEY"
        }), 503
    
    try:
        data = request.get_json()
        input_text = data.get('input_text', '').strip()
        
        if not input_text:
            return jsonify({
                "success": "error",
                "reply": "請輸入有效的問題"
            }), 400
        
        # 設定系統提示
        system_prompt = """你是一位專業的台灣魚種專家，專門回答台灣魚類分布、習性、釣法等問題。
請遵守以下規則：
1. 只能回答關於魚類、生態、習性、釣法及台灣釣點相關問題。
2. 如果使用者詢問無關問題，請禮貌地回絕並導回魚類話題。
3. 輸出請使用繁體中文，並使用台灣慣用語。
4. 若提到保育類魚種，請務必提醒使用者禁止捕撈。
5. 語氣要專業且像一位資深的釣客前輩。"""
        
        message = HumanMessage(content=system_prompt + "\n\n使用者問題: " + input_text)
        response = llm_chat.invoke([message])
        
        return jsonify({
            "success": "success",
            "reply": response.content
        }), 200
        
    except Exception as e:
        print(f"❌ LLM 錯誤: {e}")
        return jsonify({
            "success": "error",
            "reply": f"發生錯誤: {str(e)}"
        }), 500

# ============== 錯誤處理 ==============
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "頁面不存在"}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({"error": "伺服器內部錯誤"}), 500

# ============== 應用程式進入點 ==============
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 建立所有資料表
        print("✅ 資料庫初始化完成")
    
    print("🚀 Flask 應用啟動...")
    print(f"📍 訪問: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)