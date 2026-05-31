let imgLlmButton = new Image();
imgLlmButton.src = "/static/images/llmSendButton.jpg"; 

console.log("LLM載入中...");

imgLlmButton.onload = function() {
    console.log("✅ 圖片載入完成，開始繪製！");
    
    let btnCanvas = document.getElementById("llm-button-icon");
    if (!btnCanvas) {
        console.error("❌ 找不到 HTML 裡的 llm-button-icon！");
        return;
    }
    let btnCtx = btnCanvas.getContext("2d");

    // btnCanvas.style.border = "2px solid red"; 
    
    
    let sx = 170;     
    let sy = 189;      
    let sWidth = 273;  
    let sHeight = 269; 
    let dx = 0; 
    let dy = 0; 
    let dWidth = 273;  
    let dHeight = 269;
    btnCtx.drawImage(imgLlmButton, sx, sy, sWidth, sHeight, dx, dy, dWidth, dHeight);
    
};