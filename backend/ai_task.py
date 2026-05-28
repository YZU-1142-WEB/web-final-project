import time


def background_ai_task(app_context, record_id, file_path):

    from app import db, FishRecord

    with app_context:  # 確保背景執行緒能使用 Flask 與資料庫
        record = FishRecord.query.get(record_id)
        if not record:
            return

        try:
            # 💡 這裡目前是「模擬 AI」，故意等 3 秒
            time.sleep(3)

            # 模擬 AI 算出來的結果
            record.fish_type = "吳郭魚 (模擬AI辨識: 98%)"
            record.status = 'completed'  # 標記完成！

        except Exception as e:
            record.status = 'failed'
            record.fish_type = f"錯誤: {str(e)}"

        db.session.commit()  # 把結果存進資料庫
