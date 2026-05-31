// A. 建立一個新的圖片物件實體
let imgLlmButton = new Image();
// B. 設定圖片的來源路徑（這會觸發瀏覽器開始載入）
// 請確保你的圖片檔案確實放在這個路徑下
imgLlmButton.src = "/static/images/llmSendButton.jpg"; 

console.log("LLM");
// C. (重要！) 因為圖片載入需要時間，
// 我們通常會用 onload 事件，確保圖載好了才開始畫
imgLlmButton.onload = function() {
    console.log("圖片載入完成，可以開始裁切與繪製！");
    let sx = 433;     // 從大圖的 X=100 開始切
    let sy = 200;      // 從大圖的 Y=50 開始切
    let sWidth = 288;  // 切下寬 64px
    let sHeight = 275; // 切下高 64px

    let dx = 300; 
    let dy = 300; 
 
    let dWidth = 288;  
    let dHeight = 275;

    ctx.drawImage(imgLlmButton, sx, sy, sWidth, sHeight, dx, dy, dWidth, dHeight);
};