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
from flask import Flask, jsonify
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

        # 💡 核心升級：如果暫存是空的，或者距離上次下載已經超過 1 小時 (3600秒)，才重新下載
        if cwa_cache_data is None or (current_time - cwa_cache_time > 3600):
            print("向氣象署發送請求，下載最新潮汐資料中...")
            # 💡 把 timeout 延長到 30 秒，給氣象署多一點時間準備大檔案
            response = requests.get(url, verify=False, timeout=30)
            response.raise_for_status()

            # 將下載好的龐大資料存進記憶體中
            cwa_cache_data = response.json()
            cwa_cache_time = current_time
        else:
            # 開發時可以看終端機印出這行，代表成功秒抓暫存資料！
            print(f"使用暫存資料擷取：{STATION_NAME}")

        # 使用暫存的資料來進行後續處理
        data = cwa_cache_data

        records = data.get('records', {})
        tide_forecasts = records.get('TideForecasts', [])

        times = []
        heights = []
        found_station = False

        # =========================
        # 開始解析資料 (這裡跟你原本寫的一模一樣)
        # =========================
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

        # =========================
        # 資料排序 (防毛線球)
        # =========================
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

    # 嚴格要求 LLM 只回答 True 或 False
    prompt = f"請判斷「{spot_name}」是否為一個合理的台灣釣魚地點（例如真實的地名、漁港、海灣、溪流、防波堤等）？請嚴格只回答 'True' 或 'False'，不要包含任何標點符號或其他說明文字。"

    try:
        result = llm_service.chat(prompt)
        if result.get("success"):
            reply = result["reply"].strip().lower()
            # 判斷 LLM 的回覆是否包含 true
            if 'true' in reply:
                return jsonify({"valid": True})
            else:
                return jsonify({"valid": False, "message": "請輸入正確釣點名稱"})
        else:
            return jsonify({"valid": False, "message": "LLM 驗證發生錯誤"})
    except Exception as e:
        return jsonify({"valid": False, "message": str(e)})


# ==========================================
# LLM 聊天室路由 (保留同學的非同步機制)
# ==========================================

# 建立一個全域字典（看板），用來在記憶體中暫存所有 AI 任務的狀態與結果
llm_tasks = {}

# 定義路由：接收前端發送的非同步 AI 提問請求
@app.route('/api/llm/ask', methods=['POST'])
def ask_llm_async():
    # 安全檢查：若 Session 中沒有使用者名稱，代表未登入，拒絕請求
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401

    # 解析前端傳來的 JSON 資料
    data = request.get_json()
    # 從資料中取出使用者輸入的文字內容
    user_message = data.get('input_text')

    # 驗證：如果使用者沒有輸入任何文字，回傳錯誤訊息
    if not user_message:
        return jsonify({"status": "error", "message": "請提供問題"}), 400

    # 利用 UUID 隨機生成一個 8 位數的唯一任務識別碼（例如：llm_a1b2c3d4）
    task_id = f"llm_{uuid.uuid4().hex[:8]}"
    # 在全域看板中登記此任務，並將狀態初始化為 "processing"（處理中）
    llm_tasks[task_id] = {"status": "processing"}
    

    # 重複讀取 Session 紀錄
    current_history = session.get('chat_history', [])

    # 定義一個要在背景執行的工作副程式（Worker）
    def llm_worker(tid, msg, history_data):
        try:
            # 呼叫封裝好的 Gemini 服務，帶入最新問題與歷史紀錄，向 Google API 發送請求
            result = llm_service.chat(msg, history=history_data)

            # 如果 Gemini API 成功回傳結果
            if result.get("success"):
                # 使用 markdown 套件將 AI 回傳的 Markdown 語法轉換為網頁 HTML 標籤
                # extensions=['nl2br'] 會自動將文字中的換行符 '\n' 轉換為網頁的 <br> 標籤
                html_reply = markdown.markdown(
                    result["reply"], extensions=['nl2br'])
                # 將運算結果更新回全域看板中
                llm_tasks[tid] = {
                    "status": "completed",       # 標記狀態為已完成
                    "question": msg,              # 記錄當時提問的問題
                    "reply": html_reply,          # 儲存轉換後的 HTML 格式回答（網頁顯示用）
                    "raw_reply": result["reply"]  # 儲存未轉換的純文字回答（下次對話記憶用）
                }
            # 如果 Gemini API 內部判定失敗（例如觸發頻率限制）
            else:
                llm_tasks[tid] = {"status": "failed",
                                  "error_message": result.get("error", "AI 發生錯誤")}
        # 如果程式執行期間發生任何不可預期的例外錯誤（例如網路斷線）
        except Exception as e:
            llm_tasks[tid] = {"status": "failed", "error_message": str(e)}

    # 建立一個獨立的多線程（Thread）物件，指定執行背景工作，並將參數傳入
    thread = threading.Thread(target=llm_worker, args=(
        task_id, user_message, current_history))
    # 啟動背景執行緒（此時 llm_worker 開始默默執行，主程式不會卡住等待）
    thread.start()
    # 主程式立刻秒回前端，告知任務已建立，並提供任務 ID 讓前端後續進行輪詢（Polling）
    return jsonify({"status": "success", "task_id": task_id, "message": "AI 正在思考中..."})


# 定義路由：供前端 JavaScript 定時輪詢（查詢）任務的最新進度
@app.route('/api/llm/check_task/<task_id>')
def check_llm_task(task_id):
    # 從全域看板中尋找該 ID 的任務資料，若找不到則回傳 "not_found" 的狀態
    task_data = llm_tasks.get(task_id, {"status": "not_found"})

    # 檢查：如果 AI 已經運算完成，且該筆對話「尚未」儲存到使用者的 Session 紀錄中
    if task_data.get("status") == "completed" and not task_data.get("saved_to_session"):
        # 取出使用者目前的歷史對話列表
        history = session.get('chat_history', [])

        # 將這次的「使用者問題」加入歷史紀錄
        history.append({"role": "user", "content": task_data['question']})
        # 將這次的「AI 純文字回答」加入歷史紀錄（因為下一次發送給 Gemini 時需要純文字）
        history.append(
            {"role": "assistant", "content": task_data['raw_reply']}) 

        # 將更新後的歷史紀錄寫回 Session 中
        session['chat_history'] = history
        # 顯式通知 Flask 該 Session 的內部陣列已被修改，必須重新寫入 Cookie
        session.modified = True

        # 在該任務看板打個記號，防止前端因連續輪詢而導致這筆對話被重複塞入歷史紀錄
        task_data["saved_to_session"] = True

    # 回傳 JSON 格式的任務狀態與結果給前端
    return jsonify(task_data)


# 定義路由：顯示傳統的 AI 結果獨立頁面（非 AJAX 局部更新時使用）
@app.route('/api/llm/result/<task_id>')
def llm_result_page(task_id):
    # 從全域看板撈取任務資料
    result = llm_tasks.get(task_id)
    # 如果找不到任務，或者任務根本還沒執行完畢，則強制重導向回首頁
    if not result or result['status'] != 'completed':
        return redirect(url_for('home'))

    # 渲染 llm_result.html 模板，並將問題與轉好的 HTML 回覆帶入網頁中顯示
    return render_template('llm_result.html', question=result['question'], reply=result['reply'])

# ==========================================
# 圖片上傳與 AI 辨識路由 (修復：回歸 DB 架構 + 同學防呆邏輯)
# ==========================================


# 定義路由：接收前端發送的非同步圖片上傳與 AI 辨識請求
@app.route('/api/picture/upload', methods=['POST'])
def upload_async():
    # 安全檢查：若 Session 中沒有使用者名稱，代表未登入，拒絕請求
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401
    
    # 驗證：檢查前端表單欄位中是否包含名為 'file' 的檔案物件
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "未接收到檔案"}), 400

    # 從請求中取出檔案物件
    file = request.files['file']
    # 驗證：如果使用者沒選檔案就按送出，瀏覽器仍會傳送空檔名，此時予以攔截
    if file.filename == '':
        return jsonify({"status": "error", "message": "未選取檔案"}), 400

    # 當確保檔案有效存在時
    if file:
        # 將檔案的二進位原始資料（Bytes）讀取出來存入記憶體
        img_bytes = file.read()

        # 從前端表單取得釣點名稱，如果前端沒傳，則預設為 '未知釣點'
        spot_name = request.form.get('spot_name', '未知釣點')

        # ==========================================
        # 1. 呼叫 ImgBB API 上傳圖片
        # ==========================================
        try:
            # 從環境變數中讀取 ImgBB 的 API 金鑰
            IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')
            # 如果伺服器端忘記設定金鑰，拋出嚴重錯誤訊息並阻止後續執行
            if not IMGBB_API_KEY:
                print("❌ 找不到 ImgBB API 金鑰，請檢查 .env 檔案")
                return jsonify({"status": "error", "message": "伺服器設定錯誤"}), 500

            print("上傳圖片至 ImgBB 中...")

            # 將二進位圖片資料透過 Base64 編碼，再 decode 成 utf-8 字串（這是 API 要求的傳輸格式）
            b64_img = base64.b64encode(img_bytes).decode('utf-8')

            # 使用 requests 套件發送 POST 請求到 ImgBB 伺服器
            response = requests.post(
                "https://api.imgbb.com/1/upload",
                data={
                    "key": IMGBB_API_KEY,  # 帶入金鑰
                    "image": b64_img       # 帶入 Base64 圖片字串
                }
            )

            # 將 ImgBB 回傳的結果解析為 Python 字典
            response_data = response.json()

            # 如果 HTTP 狀態碼為 200，代表圖床成功收件並產生圖片網址
            if response.status_code == 200:
                # 從回傳的 JSON 結構中取出該張圖片的永久公開 URL
                img_url = response_data['data']['url']
                print(f"✅ 成功上傳到 ImgBB: {img_url}")
            # 如果圖床伺服器拒絕上傳（例如 Key 錯了或檔案太大）
            else:
                print(f"❌ ImgBB 上傳失敗: {response_data}")
                return jsonify({"status": "error", "message": "圖床伺服器拒絕請求"}), 500

        # 攔截上傳圖床期間發生的任何網路或程式例外
        except Exception as e:
            print(f"❌ 呼叫 ImgBB API 發生錯誤: {str(e)}")
            return jsonify({"status": "error", "message": f"上傳圖床失敗: {str(e)}"}), 500

        # ==========================================
        # 2. 將 ImgBB 網址寫入 Firestore 資料庫
        # ==========================================
        # 將資料新增至 Firestore 的 'fish_records' 集合（Collection）中
        # `_` 接收回傳的時間戳（此處未用到），`doc_ref` 接收該筆新文件的引用物件（指標）
        _, doc_ref = db.collection('fish_records').add({
            'username': session['username'],          # 上傳者的使用者名稱
            'image_url': img_url,                     # 剛剛拿到的 ImgBB 圖片網址
            'spot_name': spot_name,                   # 釣點名稱
            'status': 'processing',                   # 初始化狀態為處理中（等待 AI 辨識）
            'fish_type': None,                        # 預留欄位：魚種名稱（尚未辨識）
            'description': None,                      # 預留欄位：魚種詳細介紹（尚未辨識）
            'created_at': firestore.SERVER_TIMESTAMP  # 使用 Firebase 伺服器時間作為建立時間
        })

        # 從 Firestore 文件中取得系統自動生成的唯一 ID（如：2Jk9xL4mNp），作為這次辨識的任務 ID
        task_id = doc_ref.id

        # ==========================================
        # 3. 啟動背景 AI 辨識任務
        # ==========================================
        # 定義要在背景獨立執行的 AI 辨識副程式（Worker）
        def ai_worker(tid, raw_bytes):
            import traceback # 匯入追蹤錯誤軌跡的套件
            print(f"🟢 [任務 {tid}] 背景執行緒啟動！")

            try:
                # 綁定該任務在 Firestore 中對應的文件引用
                record_ref = db.collection('fish_records').document(tid)

                # 呼叫 AI 辨識核心函式（傳入圖片的二進位 Byte 資料進行圖像分析）
                predictions = analyze_catch_image(raw_bytes)
                print(f"🟢 [任務 {tid}] AI 分析完成，結果: {predictions}")

                # 防呆機制 1：如果 AI 判定照片中根本「不是魚」
                if predictions and predictions[0].get("is_fish") == False:
                    print(f"❌ [任務 {tid}] AI 判斷這張照片不是魚類")
                    # 更新資料庫狀態為 'failed'，並註記錯誤原因
                    record_ref.update({
                        'status': 'failed',
                        'error_message': '❌ AI 判斷這張照片不是魚類，請上傳清晰的魚類照片！'
                    })
                    return # 結束背景任務

                # 防呆機制 2：如果照片是魚，但判定「不是台灣本土會出現的魚種」
                if predictions and predictions[0].get("is_TW_fish") == False:
                    print(f"❌ [任務 {tid}] AI 判斷這張照片不是台灣魚類")
                    # 更新資料庫狀態為 'failed'，並註記錯誤原因
                    record_ref.update({
                        'status': 'failed',
                        'error_message': '❌ AI 判斷這張照片不是台灣常見魚類！'
                    })
                    return # 結束背景任務

                # 如果成功拿到有效的 AI 辨識結果（代表是台灣魚類）
                if predictions:
                    # 取出精確度最高的第一筆（最佳匹配）預測結果
                    best_match = predictions[0]
                    # 取出置信度分數（機率），並強制轉為浮點數
                    score = float(best_match.get('score', 0.0))
                    # 取出辨識出的魚類中文名稱（若無則預設為未知魚種）
                    fish_type = best_match.get('name', '未知魚種')
                    # 取出該魚類的介紹習性文字（若無則預設為無詳細介紹）
                    description = best_match.get('description', '無詳細介紹')

                    # 將辨識完成的豐碩成果，全面更新回 Firestore 資料庫中
                    record_ref.update({
                        'status': 'completed',                     # 標記任務成功完成
                        'fish_type': fish_type,                     # 寫入魚種名稱
                        'confidence_score': round( score*100 , 1 ), # 將小數分數轉為百分比並四捨五入到小數第一位（例如 98.5）
                        'description': description                  # 寫入習性介紹說明
                    })
                    
                # 如果 AI 回傳的資料結構是空的，查無結果
                else:
                    print(f"❌ [任務 {tid}] AI 未回傳有效預測結果，已刪除紀錄")
                    record_ref.update({
                        'status': 'failed',
                        'error_message': 'AI 辨識失敗，未回傳有效結果，請重新上傳！'
                    })

            # 捕捉背景 AI 分析時發生的任何系統崩潰或例外
            except Exception as e:
                traceback.print_exc() # 在後端終端機詳細印出是哪一行出錯
                try:
                    # 嘗試將錯誤訊息更新回資料庫，好讓前端知道為什麼卡住
                    record_ref.update({
                        'status': 'failed',
                        'error_message': f"辨識發生系統錯誤: {str(e)}"
                    })
                except Exception as inner_e:
                    # 如果連網路都斷了、導致連失敗狀態都寫不進 Firestore，則在終端機噴警告
                    print(f"❌ [任務 {tid}] 連寫入失敗狀態都失敗了: {inner_e}")

        # 建立一個獨立的背景執行緒，指定執行 ai_worker，並把任務 ID 與圖片原始 Byte 資料傳進去
        thread = threading.Thread(target=ai_worker, args=(task_id, img_bytes))
        # 啟動背景執行緒，AI 辨識在背景開始跑，主執行緒解放
        thread.start()

        # 主程式秒回 JSON 給前端，告知圖片已成功處理，並把任務 ID（Firestore 的 Doc ID）發給前端
        return jsonify({
            "status": "success",
            "task_id": task_id,
            "message": "檔案已上傳至 ImgBB 並開始辨識"
        })


# 定義路由：供前端 JavaScript 拿著 task_id 定時輪詢進度
@app.route('/api/picture/check_task/<task_id>')
def check_task(task_id):
    # 指向 Firestore 中該筆任務的文件
    doc_ref = db.collection('fish_records').document(task_id)
    # 從資料庫抓取最新資料
    doc = doc_ref.get()
    
    # 安全檢查：如果在資料庫找不到這個 ID，回傳 not_found
    if not doc.exists:
        return jsonify({"status": "not_found"})
    
    # 將文件資料轉為 Python 字典格式
    record = doc.to_dict()
    # 取出目前的辨識狀態（processing / completed / failed）
    status = record.get('status')

    # 【重要邏輯】如果 AI 判定失敗（不是魚、系統錯等）
    if status == 'failed':
        # 撈出剛剛在背景註記的親切錯誤提示
        error_msg = record.get('error_message', '辨識過程發生錯誤')
        # 為了節省空間，把這筆失敗的暫存紀錄從資料庫中徹底刪除（Delete）
        doc_ref.delete()

        # 回傳失敗狀態與原因給前端，前端收到後通常會彈出警告（Alert）視窗告知使用者
        return jsonify({
            "status": "failed",
            "error_message": error_msg
        })

    # 如果狀態是 processing（還在算）或 completed（算完了），就直接回傳狀態與魚種名稱
    return jsonify({
        "status": status,
        "fish_name": record.get('fish_type')
    })


# 定義路由：當前端發現狀態是 completed，就會跳轉到這個獨立網頁顯示辨識結果
@app.route('/api/picture/result/<task_id>')
def result_page(task_id):
    # 去資料庫撈取這筆任務的文件
    doc = db.collection('fish_records').document(task_id).get()

    # 安全檢查：若文件不存在，直接強制重導向回首頁
    if not doc.exists:
        return redirect(url_for('home'))
    
    # 轉成字典
    record = doc.to_dict()
    # 安全檢查：如果這個任務根本還沒辨識成功，不允許看結果，踢回首頁
    if record.get('status') != 'completed':
        return redirect(url_for('home'))
        
    # 通過所有檢查後，載入 HTML 模板 'result.html'，並把資料庫裡的所有辨識資料渲染到網頁上
    return render_template('result.html',
                           img_file=record.get('image_url'),          # 顯示 ImgBB 的圖片
                           fish_name=record.get('fish_type'),         # 顯示魚的名字
                           confidence=record.get('confidence_score', '無資料'), # 顯示 AI 信心度
                           description=record.get('description'))     # 顯示魚類詳細介紹說明




@app.route('/api/spots/<spot_name>/images', methods=['GET'])
def get_spot_images(spot_name):
    """取得特定釣點的所有已完成辨識的漁獲照片"""
    if 'username' not in session:
        return jsonify({"status": "error", "message": "請先登入"}), 401

    try:
        # 去 Firestore 尋找符合該釣點，且狀態是 completed 的紀錄
        records_ref = db.collection('fish_records')
        query = records_ref.where('spot_name', '==', spot_name).where(
            'status', '==', 'completed').stream()

        images = []
        for doc in query:
            data = doc.to_dict()
            images.append({
                "id": doc.id,  # 新增這行：把 Firestore 的文件 ID 傳給前端
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
        # 去 Firestore 尋找這個使用者的所有紀錄
        records_ref = db.collection('fish_records')
        query = records_ref.where(
            'username', '==', session['username']).stream()

        spots_set = set()  # 用 set 來自動過濾重複的釣點名稱
        for doc in query:
            data = doc.to_dict()
            spot = data.get('spot_name')
            # 確保有釣點名稱且不是預設的未知釣點
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

        # 為了安全，檢查這張照片是不是這個人的
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
        # 找出該使用者在這個釣點的所有紀錄
        records_ref = db.collection('fish_records')
        query = records_ref.where('username', '==', session['username']).where(
            'spot_name', '==', spot_name).stream()

        # 跑迴圈把它們全部刪掉
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
    app.run(host='0.0.0.0', port=port, debug=is_local)
