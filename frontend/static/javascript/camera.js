// frontend/static/javascript/camera.js

async function handleUpload() {
    // 抓取畫面上的元素
    const fileInput = document.getElementById("fileInput");
    const btn = document.getElementById("submitBtn");
    const statusText = document.getElementById("statusText");

    // 檢查使用者有沒有選擇檔案
    if (!fileInput || fileInput.files.length === 0) {
        alert("請先選擇一張照片！");
        return;
    }

    // 改變按鈕與文字狀態
    const originalText = btn.innerText;
    btn.innerText = "上傳中...";
    btn.disabled = true;
    statusText.style.display = "block"; // 顯示提示文字
    statusText.innerText = "正在上傳照片... ⏳";

    // 打包檔案
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    // 🔥 新增：從 localStorage 抓取釣點名稱，並加進表單資料中一起送出
    const spotName = localStorage.getItem("current_fishing_spot");
    if (spotName) {
        formData.append("spot_name", spotName);
    }

    try {
        // 呼叫 Flask 後端 API
        const response = await fetch("/api/picture/upload", {
            method: "POST",
            body: formData,
        });

        const result = await response.json();

        // 如果後端成功接收，開始等待 AI 辨識
        if (result.status === "success") {
            btn.innerText = "AI 辨識中...";
            statusText.innerText = "照片已上傳！AI 正在分析中... 🐟";
            const taskId = result.task_id;
            localStorage.setItem("fish_task_id", taskId);

            // 啟動輪詢檢查
            checkTaskStatus(taskId, btn, originalText, statusText);
        } else {
            alert("錯誤：" + result.message);
            btn.innerText = originalText;
            btn.disabled = false;
            statusText.style.display = "none";
        }
    } catch (error) {
        console.error("上傳發生錯誤:", error);
        alert("無法連線到伺服器，請確認後端有啟動！");
        btn.innerText = originalText;
        btn.disabled = false;
        statusText.style.display = "none";
    }
}

	// 這個函數會一直去問後端：「好了沒？」
// 宣告一個非同步函數，接收四個參數：任務ID (taskId)、按鈕元素 (btn)、按鈕原始文字 (originalText)、狀態顯示文字元素 (statusText)
async function checkTaskStatus(taskId, btn, originalText, statusText) {
    try {
        // 使用 fetch 發送 API 請求到後端，查詢該 taskId 的最新狀態
        // 網址後方加上 `?t=${new Date().getTime()}` 是為了加上時間戳記，防止瀏覽器快取拿到舊資料
        const response = await fetch(
            `/api/picture/check_task/${taskId}?t=${new Date().getTime()}`,
        );
        
        // 將後端回傳的 Response 解析為 JSON 格式的資料
        const data = await response.json();

        // 判斷回傳資料中的狀態：如果任務狀態是 "completed"（已完成）
        if (data.status === "completed") {
            // 既然完成了，就清除存在瀏覽器 LocalStorage 中的任務 ID 紀錄
            localStorage.removeItem("fish_task_id");
            // 更新畫面上的狀態文字，提示使用者即將跳轉
            statusText.innerText = "🎉 辨識完成！準備跳轉...";
            // 將當前網頁重新導向到該任務的結果呈現頁面
            window.location.href = `/api/picture/result/${taskId}`;
            
        // 如果任務狀態是 "failed"（失敗）
        } else if (data.status === "failed") {
            // 一樣先清除 LocalStorage 中的任務 ID 紀錄
            localStorage.removeItem("fish_task_id");
            // 跳出警告視窗，並附上後端回傳的錯誤原因
            alert("辨識失敗：" + data.error_message);

            // 恢復按鈕的原始文字（例如從「處理中...」變回「開始辨識」）
            btn.innerText = originalText;
            // 重新啟用按鈕，讓使用者可以再次點擊
            btn.disabled = false;
            // 隱藏狀態提示文字
            statusText.style.display = "none";

            // 清空檔案上傳欄位，方便使用者重新選擇圖片
            document.getElementById("fileInput").value = "";
            
            // 以下四行負責重置圖片預覽區塊：
            const spotPreview = document.getElementById("spot-preview"); // 取得預覽圖片的元素
            const previewPlaceholder = document.getElementById("preview-placeholder"); // 取得尚未上傳圖片時的佔位符元素
            if (spotPreview) spotPreview.style.display = "none"; // 隱藏預覽圖
            if (previewPlaceholder) previewPlaceholder.style.display = "block"; // 顯示佔位符

        // 如果任務狀態是 "not_found"（找不到任務資料）
        } else if (data.status === "not_found") {
            // 清除 LocalStorage 中的任務 ID 紀錄
            localStorage.removeItem("fish_task_id");
            // 跳出警告視窗，提示使用者任務異常
            alert("❌ 找不到該筆任務，可能已被系統清除！");
            
            // 重置 UI 狀態：恢復按鈕文字、啟用按鈕、隱藏狀態文字
            btn.innerText = originalText;
            btn.disabled = false;
            statusText.style.display = "none";
            
        // 如果狀態不是 completed、failed、也不是 not_found（代表任務還在「處理中」）
        } else {
            // 在畫面的狀態文字後面加上一個點，製造「處理中...」的視覺進度感
            statusText.innerText += " .";
            // 設定計時器，等待 1000 毫秒（1秒）後，再次呼叫自己（遞迴）去問後端「好了沒？」
            setTimeout(
                () =>
                    checkTaskStatus(taskId, btn, originalText, statusText),
                1000,
            );
        }
        
    // 捕捉在 try 區塊中發生的任何預期外錯誤（例如網路斷線、後端沒回傳合法的 JSON 等）
    } catch (error) {
        // 在瀏覽器開發者工具 (F12) 的 Console 印出詳細錯誤，方便工程師除錯
        console.error("前端程式發生錯誤:", error);
        // 跳出警告視窗告知使用者發生程式執行錯誤，並顯示錯誤訊息
        alert("程式執行錯誤，請按 F12 查看 Console！\n錯誤詳情：" + error.message);
        
        // 發生錯誤後，也要將 UI 恢復到可以重新操作的狀態
        btn.innerText = originalText;
        btn.disabled = false;
        statusText.style.display = "none";
    }
}

// 頁面載入時執行，負責處理釣點顯示與圖片即時預覽
document.addEventListener("DOMContentLoaded", () => {
    // 從 localStorage 讀取剛剛加入的釣點
    const spotName = localStorage.getItem("current_fishing_spot");
    const spotContainer = document.getElementById("spot-container");
    const spotTitle = document.getElementById("spot-title");
    const fileInput = document.getElementById("fileInput");
    const spotPreview = document.getElementById("spot-preview");
    const previewPlaceholder = document.getElementById(
        "preview-placeholder",
    );

    // 如果有釣點名稱，就把底下的格子顯示出來
    if (spotName) {
        spotContainer.style.display = "block";
        spotTitle.innerText = `📍 釣點: ${spotName}`;
    }

    // 監聽使用者選擇檔案的動作，一選好檔案就馬上顯示預覽圖
    if (fileInput) {
        fileInput.addEventListener("change", function (event) {
            const file = event.target.files[0];
            if (file && spotName) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    spotPreview.src = e.target.result; // 將圖片來源設為選取的檔案
                    spotPreview.style.display = "inline-block";
                    previewPlaceholder.style.display = "none";
                };
                reader.readAsDataURL(file);
            }
        });
    }
});