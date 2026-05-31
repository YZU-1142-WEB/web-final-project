import os
import threading
import uuid
import markdown
import base64
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv
from LLM.LLM import llm_service
from image_identify.image_identify import analyze_catch_image
import requests
import urllib3
import traceback
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
cwa_cache_data = None
cwa_cache_time = 0

load_dotenv()

app = Flask(__name__, template_folder="../frontend/templates",
            static_folder="../frontend/static")
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key_for_dev")

is_local = os.environ.get("SPACE_ID") is None
if is_local:
    # HTTP
    app.config.update(
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_NAME='local_dev_session'
    )
else:
    # HTTPS
    app.config.update(
        SESSION_COOKIE_SAMESITE='None',
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_NAME='session'
    )

CORS(app)

private_key = os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n')
cred_dict = {
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key": private_key,
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "token_uri": "https://oauth2.googleapis.com/token"
}
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(
            cred, {'storageBucket': 'web-final-project-fb1af.appspot.com'})
    db = firestore.client()
    print("✅ Firebase Firestore 連線成功！")
except Exception as e:
    print(f"❌ Firebase 初始化失敗，請檢查金鑰檔案: {e}")

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

@app.route('/my_spots')
def my_spots_page():
    if 'username' in session:
        return render_template('my_spots.html', username=session['username'])
    flash("請先登入")
    return redirect(url_for('login'))


@app.route('/api/account/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).limit(1).stream()
        user_doc = None
        for doc in query:
            user_doc = doc
            break
        if user_doc:
            user_data = user_doc.to_dict()
            if user_data.get('password') == password:
                session['username'] = user_data['username']
                session['user_id'] = user_doc.id
                return redirect(url_for('home'))
        flash("帳號或密碼錯誤")
    return render_template('login.html')


@app.route('/api/account/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).limit(1).stream()
        existing_user = None
        for doc in query:
            existing_user = doc
            break
        if existing_user is None:
            users_ref.add({
                'username': username,
                'password': password,
                'created_at': firestore.SERVER_TIMESTAMP
            })
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


@app.route('/api/get_tidal_data')
def get_tidal_data():
    global cwa_cache_data, cwa_cache_time

    API_KEY = 'CWA-762AFC9F-FA10-4125-B0B6-07B4D525B827'
    DATASET_ID = 'F-A0021-001'
    STATION_NAME = request.args.get('station', '基隆市中正區')

    url = f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/{DATASET_ID}?Authorization={API_KEY}'

    try:
        current_time = time.time()

        if cwa_cache_data is None or (current_time - cwa_cache_time > 3600):
            print("向氣象署發送請求，下載最新潮汐資料中...")
            response = requests.get(url, verify=False, timeout=30)
            response.raise_for_status()

            cwa_cache_data = response.json()
            cwa_cache_time = current_time
        else:
            print(f"使用暫存資料擷取：{STATION_NAME}")

        data = cwa_cache_data

        records = data.get('records', {})
        tide_forecasts = records.get('TideForecasts', [])

        times = []
        heights = []
        found_station = False

        for forecast in tide_forecasts:
            locations = forecast.get('Location', [])
            if isinstance(locations, dict):
                locations = [locations]

            for location in locations:
                location_name = location.get('LocationName', '')

                if STATION_NAME not in location_name:
                    continue

                found_station = True
                time_periods = location.get('TimePeriods', {})
                dailies = time_periods.get('Daily', [])

                if isinstance(dailies, dict):
                    dailies = [dailies]

                for daily in dailies:
                    time_list = daily.get('Time', [])
                    if isinstance(time_list, dict):
                        time_list = [time_list]

                    for t in time_list:
                        dt = t.get('DateTime')
                        tide_heights = t.get('TideHeights', {})
                        height = tide_heights.get('AboveTWVD')

                        if dt and height is not None:
                            times.append(dt)
                            try:
                                heights.append(float(height))
                            except ValueError:
                                heights.append(0)

        if not found_station:
            return jsonify({'success': False, 'message': f'氣象署目前無提供此區資料：{STATION_NAME}'})
        if not times:
            return jsonify({'success': False, 'message': '找到測站，但沒有相對應的潮位資料'})

        tide_pairs = zip(times, heights)
        sorted_pairs = sorted(tide_pairs)
        times, heights = zip(*sorted_pairs) if sorted_pairs else ([], [])

        times = list(times)
        heights = list(heights)

        return jsonify({
            'success': True,
            'station_name': STATION_NAME,
            'times': times,
            'heights': heights
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f"連線氣象署發生錯誤，請稍後再試 ({str(e)})"
        })

# ==========================================
# LLM 判斷是否為合理釣點路由
# ==========================================

@app.route('/api/llm/validate_spot', methods=['POST'])
def validate_spot():
    if 'username' not in session:
        return jsonify({"valid": False, "message": "請先登入"}), 401

    data = request.get_json()
    spot_name = data.get('spot_name', '').strip()

    if not spot_name:
        return jsonify({"valid": False, "message": "請輸入釣點名稱"})

    prompt = f"請判斷「{spot_name}」是否為一個合理的台灣釣魚地點（例如真實的地名、漁港、海灣、溪流、防波堤等）？請嚴格只回答 'True' 或 'False'，不要包含任何標點符號或其他說明文字。"

    try:
        result = llm_service.chat(prompt)
        if result.get("success"):
            reply = result["reply"].strip().lower()
            if 'true' in reply:
                return jsonify({"valid": True})
            else:
                return jsonify({"valid": False, "message": "請輸入正確釣點名稱"})
        else:
            return jsonify({"valid": False, "message": "LLM 驗證發生錯誤"})
    except Exception as e:
        return jsonify({"valid": False, "message": str(e)})


# ==========================================
# LLM 聊天室路由
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
<<<<<<< HEAD
    chat_history = session.get('chat_history', [])

    current_history = session.get('chat_history', [])
=======
    current_history = session.get('chat_history',[])
>>>>>>> origin/feature/sort-the-code

    def llm_worker(tid, msg, history_data):
        try:
            result = llm_service.chat(msg, history=history_data)

            if result.get("success"):
                html_reply = markdown.markdown(
                    result["reply"], extensions=['nl2br'])
                llm_tasks[tid] = {
                    "status": "completed",
                    "question": msg,
                    "reply": html_reply,
                    "raw_reply": result["reply"]
                }
            else:
                llm_tasks[tid] = {"status": "failed",
                                  "error_message": result.get("error", "AI 發生錯誤")}
        except Exception as e:
            llm_tasks[tid] = {"status": "failed", "error_message": str(e)}

    thread = threading.Thread(target=llm_worker, args=(
        task_id, user_message, current_history))
    thread.start()
    return jsonify({"status": "success", "task_id": task_id, "message": "AI 正在思考中..."})

<<<<<<< HEAD
# 未改

=======
>>>>>>> origin/feature/sort-the-code

@app.route('/api/llm/check_task/<task_id>')
def check_llm_task(task_id):
    task_data = llm_tasks.get(task_id, {"status": "not_found"})

    if task_data.get("status") == "completed" and not task_data.get("saved_to_session"):
        history = session.get('chat_history', [])
        history.append({"role": "user", "content": task_data['question']})
<<<<<<< HEAD
        history.append(
            {"role": "assistant", "content": task_data['raw_reply']})  # 存入純文字

        session['chat_history'] = history
        session.modified = True

        # 做個記號，防止前端重複輪詢時，被重複存進陣列裡
=======
        history.append({"role": "assistant", "content": task_data['raw_reply']}) 
        
        session['chat_history'] = history
        session.modified = True
>>>>>>> origin/feature/sort-the-code
        task_data["saved_to_session"] = True

    return jsonify(task_data)

<<<<<<< HEAD
# 未改

=======
>>>>>>> origin/feature/sort-the-code

@app.route('/api/llm/result/<task_id>')
def llm_result_page(task_id):
    result = llm_tasks.get(task_id)
    if not result or result['status'] != 'completed':
        return redirect(url_for('home'))

<<<<<<< HEAD
    history = session.get('chat_history', [])
    history.append({"role": "user", "content": result['question']})
    history.append({"role": "assistant", "content": result['reply']})

    session['chat_history'] = [
        {"role": "user", "content": result['question']},
        {"role": "assistant", "content": result.get(
            'raw_reply', result['reply'])}
    ]
    session.modified = True

=======
>>>>>>> origin/feature/sort-the-code
    return render_template('llm_result.html', question=result['question'], reply=result['reply'])

# ==========================================
# 圖片上傳與 AI 辨識路由 
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
        spot_name = request.form.get('spot_name', '未知釣點')

        try:
            IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')
            if not IMGBB_API_KEY:
                print("❌ 找不到 ImgBB API 金鑰，請檢查 .env 檔案")
                return jsonify({"status": "error", "message": "伺服器設定錯誤"}), 500

            print("上傳圖片至 ImgBB 中...")
            b64_img = base64.b64encode(img_bytes).decode('utf-8')

            response = requests.post(
                "https://api.imgbb.com/1/upload",
                data={
                    "key": IMGBB_API_KEY,
                    "image": b64_img
                }
            )

            response_data = response.json()

            if response.status_code == 200:
                img_url = response_data['data']['url']
                print(f"✅ 成功上傳到 ImgBB: {img_url}")
            else:
                print(f"❌ ImgBB 上傳失敗: {response_data}")
                return jsonify({"status": "error", "message": "圖床伺服器拒絕請求"}), 500

        except Exception as e:
            print(f"❌ 呼叫 ImgBB API 發生錯誤: {str(e)}")
            return jsonify({"status": "error", "message": f"上傳圖床失敗: {str(e)}"}), 500

        _, doc_ref = db.collection('fish_records').add({
            'username': session['username'],
            'image_url': img_url,
            'spot_name': spot_name,
            'status': 'processing',
            'fish_type': None,
            'description': None,
            'created_at': firestore.SERVER_TIMESTAMP
        })

        task_id = doc_ref.id

        def ai_worker(tid, raw_bytes):
            import traceback
            print(f"🟢 [任務 {tid}] 背景執行緒啟動！")

            try:
                record_ref = db.collection('fish_records').document(tid)

                predictions = analyze_catch_image(raw_bytes)
                print(f"🟢 [任務 {tid}] AI 分析完成，結果: {predictions}")

                if predictions and predictions[0].get("is_fish") == False:
                    record_ref.update({'status': 'not_fish'})
                    return

                if predictions and predictions[0].get("is_TW_fish") == False:
                    record_ref.update({'status': 'not_TW_fish'})
                    return

                if predictions:
                    best_match = predictions[0]
                    score = float(best_match.get('score', 0.0))
                    fish_type = f"{best_match.get('name', '未知魚種')} (信心度: {score*100:.1f}%)"
                    description = best_match.get('description', '無詳細介紹')

                    record_ref.update({
                        'status': 'completed',
                        'fish_type': fish_type,
                        'description': description
                    })
                else:
                    record_ref.update({
                        'status': 'completed',
                        'fish_type': "圖片中未偵測到明顯魚類",
                        'description': "無法提供介紹"
                    })
            except Exception as e:
                traceback.print_exc()
                try:
                    record_ref.update({
                        'status': 'failed',
                        'fish_type': f"辨識發生系統錯誤: {str(e)}"
                    })
                except Exception as inner_e:
                    print(f"❌ [任務 {tid}] 連寫入失敗狀態都失敗了: {inner_e}")

        thread = threading.Thread(target=ai_worker, args=(task_id, img_bytes))
        thread.start()

        return jsonify({
            "status": "success",
            "task_id": task_id,
            "message": "檔案已上傳至 ImgBB 並開始辨識"
        })


@app.route('/api/picture/check_task/<task_id>')
def check_task(task_id):
    doc = db.collection('fish_records').document(task_id).get()
    if not doc.exists:
        return jsonify({"status": "not_found"})
    record = doc.to_dict()
    return jsonify({
        "status": record.get('status'),
        "fish_name": record.get('fish_type')
    })


@app.route('/api/picture/result/<task_id>')
def result_page(task_id):
    doc = db.collection('fish_records').document(task_id).get()
    if not doc.exists:
        return redirect(url_for('home'))
    record = doc.to_dict()
    if record.get('status') != 'completed':
        return redirect(url_for('home'))
    return render_template('result.html',
                           img_file=record.get('image_url'),
                           fish_name=record.get('fish_type'),
                           description=record.get('description'))


@app.route('/api/spots/<spot_name>/images', methods=['GET'])
def get_spot_images(spot_name):
    """取得特定釣點的所有已完成辨識的漁獲照片"""
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401
        
    try:
        records_ref = db.collection('fish_records')
        query = records_ref.where('spot_name', '==', spot_name).where('status', '==', 'completed').stream()
        
        images = []
        for doc in query:
            data = doc.to_dict()
            images.append({
                "id": doc.id, 
                "image_url": data.get("image_url"),
                "fish_type": data.get("fish_type"),
                "username": data.get("username")
            })
            
        return jsonify({
            "status": "success", 
            "spot_name": spot_name, 
            "images": images
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/api/my_spots', methods=['GET'])
def get_my_spots():
    """取得當前使用者所有創建過的釣點名稱列表"""
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401
        
    try:
        records_ref = db.collection('fish_records')
        query = records_ref.where('username', '==', session['username']).stream()
        
        spots_set = set()
        for doc in query:
            data = doc.to_dict()
            spot = data.get('spot_name')
            if spot and spot != '未知釣點':
                spots_set.add(spot)
                
        return jsonify({
            "status": "success", 
            "spots": list(spots_set)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/api/picture/<doc_id>', methods=['DELETE'])
def delete_picture(doc_id):
    """刪除單張照片紀錄"""
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401
        
    try:
        doc_ref = db.collection('fish_records').document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists and doc.to_dict().get('username') == session['username']:
            doc_ref.delete()
            return jsonify({"status": "success", "message": "照片已刪除"})
        else:
            return jsonify({"status": "error", "message": "找不到檔案或權限不足"}), 403
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/spots/<spot_name>', methods=['DELETE'])
def delete_spot(spot_name):
    """刪除整個釣點（也就是刪除該釣點下的所有照片紀錄）"""
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401
        
    try:
        records_ref = db.collection('fish_records')
        query = records_ref.where('username', '==', session['username']).where('spot_name', '==', spot_name).stream()
        
        deleted_count = 0
        for doc in query:
            doc.reference.delete()
            deleted_count += 1
            
        return jsonify({"status": "success", "message": f"已刪除釣點及 {deleted_count} 張照片"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    print("✅ 啟動 Flask 伺服器...")
    port = int(os.environ.get("PORT", 7860))
<<<<<<< HEAD
    app.run(host='0.0.0.0', port=port, debug=is_local)
=======
    is_local = os.environ.get("SPACE_ID") is None
    app.run(host='0.0.0.0', port=port, debug=is_local)
>>>>>>> origin/feature/sort-the-code
