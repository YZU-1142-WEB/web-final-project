import os
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from datetime import datetime #上傳照片
from werkzeug.utils import secure_filename #上傳照片
# from ai_model import predict_fish_species # 假設的ai模型函數



load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "default_secret_key_for_dev")

app.config["MONGO_URI"] = os.getenv("MONGO_URI")

mongo = PyMongo(app)
bcrypt = Bcrypt(app)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = mongo.db.users
        existing_user = users.find_one({'username': request.form['username']})

        if existing_user is None:
            hashed_password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
            users.insert_one({'username': request.form['username'], 'password': hashed_password})
            flash("註冊成功，請登入！")
            return redirect(url_for('login'))
        
        flash("該帳號已存在！")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = mongo.db.users
        login_user = users.find_one({'username': request.form['username']})

        if login_user and bcrypt.check_password_hash(login_user['password'], request.form['password']):
            session['username'] = request.form['username']
            return redirect(url_for('dashboard'))
        
        flash("帳號或密碼錯誤")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        user_records = mongo.db.fish_records.find({'username': session['username']}) #改動
        return render_template('dashboard.html', records=user_records) #改動
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

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

        # 3. 存入 MongoDB
        mongo.db.fish_records.insert_one({
            'username': session['username'],
            'image_url': filename,
            'fish_type': ai_result,
            'upload_time': datetime.now()
        })

        # 4. 直接渲染結果頁面
        return render_template('result.html', filename=filename, fish_type=ai_result)

    return redirect(url_for('dashboard'))
