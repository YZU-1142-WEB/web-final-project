console.log("JS 檔案已成功載入！");
$('#random-button').click(function() {
    // 讀取 task.json (請確保檔案路徑正確)
    $.getJSON('/static/data/fish.json', function(tasks) {
        // 1. 計算隨機索引值
        console.log("讀取到的資料:", tasks);
        const randomIndex = Math.floor(Math.random() * tasks.length);
        
        // 2. 取得隨機出的魚名
        const selectedFish = tasks[randomIndex];
        
        // 3. 印出在左邊的框框 (#display-area)
        $('#display-area').text(selectedFish);
    })
    .fail(function() {
        console.error("無法載入 JSON 檔案，請檢查路徑或是否使用了伺服器環境開啟。");
    });
});