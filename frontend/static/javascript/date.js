const updateTime = () => {
    const timeDisplay = document.querySelector('#time-display');
    const now = new Date();
    timeDisplay.textContent = now.toLocaleTimeString();
};

// 網頁一載入，先手動執行一次，避免剛開始出現「時間載入中...」的空窗期
updateTime();

// 設定計時器：每隔 1000 毫秒 (1秒)，就自動去執行一次 updateTime 函式
setInterval(updateTime, 1000);