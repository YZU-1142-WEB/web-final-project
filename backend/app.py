import os
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

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

    records = db.relationship('CatchRecord', backref='author', lazy=True)


@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({"status": "success", "message": "台灣常見魚種辨識系統 API 運作中！"})


@app.route('/api/register', methods=['POST'])
def register():
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
def login():
    data = request.json
    user = User.query.filter_by(username=data.get('username')).first()

    if user and user.password == data.get('password'):
        return jsonify({"status": "success", "message": "登入成功", "user_id": user.id})

    return jsonify({"status": "error", "message": "帳號或密碼錯誤"}), 401


@app.route('/api/upload', methods=['POST'])
def upload_image():
    pass


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ 資料庫初始化完成！")
        print("✅ 上傳資料夾準備完畢！")

    app.run(port=8000, debug=True)
