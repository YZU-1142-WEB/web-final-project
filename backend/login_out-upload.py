import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from datetime import datetime #上傳照片
from werkzeug.utils import secure_filename #上傳照片
# from ai_model import predict_fish_species # 假設的ai模型函數

load_dotenv()

app = Flask(__name__, template_folder="../frontend/templates",
            static_folder="../frontend/static")

app.secret_key = os.getenv("SECRET_KEY", "default_secret_key_for_dev")

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


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html')
    return redirect(url_for('login'))


@app.route('/api/account/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user is None:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash("註冊成功，請登入！")
            return redirect(url_for('login'))
        flash("該帳號已存在！")
    return render_template('register.html')


@app.route('/api/account/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            session['username'] = username
            return redirect(url_for('dashboard'))

        flash("帳號或密碼錯誤")
    return render_template('login.html')


@app.route('/api/account/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ 資料庫初始化完成！")
        print("✅ 上傳資料夾準備完畢！")
    app.run(port=8000, debug=True)


#設定上傳路徑，並確保資料夾存在
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
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
