import pytest
from unittest.mock import patch, MagicMock
import json

# 在載入 app.py 之前，先 Mock 掉 Firebase 的初始化，避免測試時因為沒有金鑰而報錯
with patch('firebase_admin.credentials.Certificate'), \
        patch('firebase_admin.initialize_app'), \
        patch('firebase_admin.firestore.client'):
    from app import app, llm_tasks, cwa_cache_data
    import app as my_app  # 用於在測試中操作 mock 出來的 db


@pytest.fixture
def client():
    """設定 Flask 測試客戶端 (Test Client)"""
    app.config['TESTING'] = True
    app.secret_key = 'test_secret_key'
    with app.test_client() as client:
        yield client

# ==========================================
# 1. 測試基本網頁路由與登入權限
# ==========================================


def test_home_redirects_when_not_logged_in(client):
    """測試未登入時，訪問首頁會被重導向到登入頁"""
    response = client.get('/')
    assert response.status_code == 302
    assert '/api/account/login' in response.location


def test_home_access_when_logged_in(client):
    """測試登入狀態下可以正常訪問首頁"""
    with client.session_transaction() as sess:
        sess['username'] = 'testuser'
    response = client.get('/')
    assert response.status_code == 200


def test_logout(client):
    """測試登出功能是否正常清除 Session 並重導向"""
    with client.session_transaction() as sess:
        sess['username'] = 'testuser'

    response = client.get('/api/account/logout')
    assert response.status_code == 302
    assert '/api/account/login' in response.location

    # 驗證 Session 已經被清除
    with client.session_transaction() as sess:
        assert 'username' not in sess

# ==========================================
# 2. 測試 LLM 釣點驗證 API
# ==========================================


@patch('app.llm_service.chat')
def test_validate_spot_valid(mock_chat, client):
    """測試 LLM 判斷為合理釣點的情境"""
    # 模擬 LLM 回傳成功且包含 True
    mock_chat.return_value = {"success": True, "reply": "True"}

    with client.session_transaction() as sess:
        sess['username'] = 'testuser'

    response = client.post('/api/llm/validate_spot',
                           json={'spot_name': '基隆碧砂漁港'})
    data = response.get_json()

    assert response.status_code == 200
    assert data['valid'] is True
    mock_chat.assert_called_once()


@patch('app.llm_service.chat')
def test_validate_spot_invalid(mock_chat, client):
    """測試 LLM 判斷為非合理釣點的情境"""
    # 模擬 LLM 回傳包含 False
    mock_chat.return_value = {"success": True, "reply": "False"}

    with client.session_transaction() as sess:
        sess['username'] = 'testuser'

    response = client.post('/api/llm/validate_spot',
                           json={'spot_name': '麥當勞'})
    data = response.get_json()

    assert response.status_code == 200
    assert data['valid'] is False
    assert "請輸入正確釣點名稱" in data['message']


def test_validate_spot_no_auth(client):
    """測試未登入時呼叫驗證 API 會被拒絕"""
    response = client.post('/api/llm/validate_spot', json={'spot_name': '基隆'})
    assert response.status_code == 401

# ==========================================
# 3. 測試氣象署潮汐 API
# ==========================================


@patch('app.requests.get')
def test_get_tidal_data_success(mock_get, client):
    """測試串接中央氣象署 API 取得資料成功的情境"""
    # 模擬氣象署的 JSON 回應格式
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": {
            "TideForecasts": [{
                "Location": [{
                    "LocationName": "基隆市中正區",
                    "TimePeriods": {
                        "Daily": [{
                            "Time": [{
                                "DateTime": "2026-05-20T00:00:00+08:00",
                                "TideHeights": {"AboveTWVD": "1.5"}
                            }]
                        }]
                    }
                }]
            }]
        }
    }
    mock_get.return_value = mock_response

    response = client.get('/api/get_tidal_data?station=基隆市中正區')
    data = response.get_json()

    assert response.status_code == 200
    assert data['success'] is True
    assert data['station_name'] == '基隆市中正區'
    assert "2026-05-20T00:00:00+08:00" in data['times']
    assert 1.5 in data['heights']

# ==========================================
# 4. 測試 LLM 聊天室非同步任務
# ==========================================


def test_ask_llm_async_starts_task(client):
    """測試提交 LLM 問題後會正確建立任務"""
    with client.session_transaction() as sess:
        sess['username'] = 'testuser'

    response = client.post('/api/llm/ask',
                           json={'input_text': '台灣常見的魚有哪些？'})
    data = response.get_json()

    assert response.status_code == 200
    assert data['status'] == 'success'
    assert 'task_id' in data

    # 檢查任務是否被加入記憶體字典中
    task_id = data['task_id']
    from app import llm_tasks
    assert task_id in llm_tasks
    assert llm_tasks[task_id]['status'] == 'processing'

# ==========================================
# 5. 測試圖片上傳防呆 (未夾帶檔案)
# ==========================================


def test_upload_picture_no_file(client):
    """測試上傳圖片時未夾帶檔案的防呆機制"""
    with client.session_transaction() as sess:
        sess['username'] = 'testuser'

    # 不傳送 'file' 欄位
    response = client.post('/api/picture/upload', data={})
    data = response.get_json()

    assert response.status_code == 400
    assert data['status'] == 'error'
    assert data['message'] == '未接收到檔案'

# ==========================================
# 6. 測試釣點座標儲存與讀取 (新功能測試)
# ==========================================


@patch('app.db.collection')
def test_save_spot_coords_success(mock_collection, client):
    """測試成功儲存或更新釣點座標"""
    with client.session_transaction() as sess:
        sess['username'] = 'testuser'

    # 設定 Firebase 查詢的 Mock 回傳結果 (模擬沒有舊資料，進行新增)
    mock_query = MagicMock()
    mock_query.limit.return_value.stream.return_value = []
    mock_collection.return_value.where.return_value.where.return_value = mock_query

    response = client.post('/api/spots/save',
                           json={'spot_name': '秘密釣點', 'lat': 25.123, 'lng': 121.456})
    data = response.get_json()

    assert response.status_code == 200
    assert data['status'] == 'success'


@patch('app.db.collection')
def test_get_spots_with_coords_success(mock_collection, client):
    """測試讀取釣點座標列表"""
    with client.session_transaction() as sess:
        sess['username'] = 'testuser'

    # 模擬 Firebase 讀取出的文件
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {
        "spot_name": "基隆港", "lat": 25.131, "lng": 121.739}
    mock_collection.return_value.where.return_value.stream.return_value = [
        mock_doc]

    response = client.get('/api/spots/with_coords')
    data = response.get_json()

    assert response.status_code == 200
    assert data['status'] == 'success'
    assert len(data['spots']) == 1
    assert data['spots'][0]['spot_name'] == '基隆港'

# ==========================================
# 7. 測試釣點管理 (讀取與刪除)
# ==========================================


@patch('app.db.collection')
def test_get_my_spots_success(mock_collection, client):
    """測試取得個人所有釣點名稱"""
    with client.session_transaction() as sess:
        sess['username'] = 'testuser'

    # 模擬有兩筆記錄，但位於同一個釣點 (測試是否正確使用 set 去重複)
    mock_doc1 = MagicMock()
    mock_doc1.to_dict.return_value = {"spot_name": "基隆港"}
    mock_doc2 = MagicMock()
    mock_doc2.to_dict.return_value = {"spot_name": "基隆港"}
    mock_doc3 = MagicMock()
    mock_doc3.to_dict.return_value = {"spot_name": "野柳"}

    mock_collection.return_value.where.return_value.stream.return_value = [
        mock_doc1, mock_doc2, mock_doc3]

    response = client.get('/api/my_spots')
    data = response.get_json()

    assert response.status_code == 200
    assert data['status'] == 'success'
    assert len(data['spots']) == 2
    assert "基隆港" in data['spots']
    assert "野柳" in data['spots']


@patch('app.db.collection')
def test_delete_spot_success(mock_collection, client):
    """測試刪除整個釣點及其照片和座標"""
    with client.session_transaction() as sess:
        sess['username'] = 'testuser'

    # 模擬有 1 張漁獲照片，1 筆地圖座標
    mock_doc = MagicMock()
    mock_collection.return_value.where.return_value.where.return_value.stream.return_value = [
        mock_doc]

    response = client.delete('/api/spots/基隆港')
    data = response.get_json()

    assert response.status_code == 200
    assert data['status'] == 'success'
    # 確定有呼叫 delete 刪除方法
    assert mock_doc.reference.delete.called
