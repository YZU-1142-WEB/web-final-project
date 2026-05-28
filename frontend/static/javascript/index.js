// frontend/static/javascript/index.js

// ==========================================
// 1. AI 辨識任務背景輪詢檢查
// ==========================================
function checkAiTaskStatus() {
    const taskId = localStorage.getItem("fish_task_id");
    if (!taskId) return;

    console.log("偵測到背景辨識任務中，ID:", taskId);

    const interval = setInterval(async () => {
        try {
            const response = await fetch(`/api/check_task/${taskId}`);
            const data = await response.json();

            if (data.status === "completed") {
                console.log("辨識完成！準備跳轉...");
                clearInterval(interval);
                localStorage.removeItem("fish_task_id");
                window.location.href = `/result/${taskId}`;
            } else if (data.status === "not_found") {
                clearInterval(interval);
                localStorage.removeItem("fish_task_id");
            }
        } catch (error) {
            console.error("輪詢時發生錯誤:", error);
        }
    }, 3000);
}

// ==========================================
// 2. 全台縣市對應「所有測站名稱」資料庫
// ==========================================
const stationMapping = {
    // 北部
    基隆市: [
        { name: "基隆港/和平島", val: "基隆市中正區" },
        { name: "外木山", val: "基隆市中山區" }
    ],
    新北市: [
        { name: "淡水", val: "新北市淡水區" },
        { name: "富貴角 (石門)", val: "新北市石門區" },
        { name: "野柳/萬里", val: "新北市萬里區" },
        { name: "鼻頭角 (瑞芳)", val: "新北市瑞芳區" },
        { name: "龍洞/澳底 (貢寮)", val: "新北市貢寮區" }
    ],
    桃園市: [
        { name: "竹圍 (大園)", val: "桃園市大園區" },
        { name: "永安 (新屋)", val: "桃園市新屋區" }
    ],
    新竹: [
        { name: "新竹漁港", val: "新竹市北區" },
        { name: "坡頭 (新豐)", val: "新竹縣新豐鄉" }
    ],
    // 中部
    苗栗縣: [
        { name: "龍鳳 (竹南)", val: "苗栗縣竹南鎮" },
        { name: "外埔 (後龍)", val: "苗栗縣後龍鎮" },
        { name: "苑裡", val: "苗栗縣苑裡鎮" }
    ],
    臺中市: [
        { name: "臺中港/梧棲", val: "臺中市梧棲區" },
        { name: "大甲", val: "臺中市大甲區" }
    ],
    彰化縣: [
        { name: "鹿港", val: "彰化縣鹿港鎮" },
        { name: "王功 (芳苑)", val: "彰化縣芳苑鄉" }
    ],
    雲林縣: [
        { name: "麥寮", val: "雲林縣麥寮鄉" },
        { name: "箔子寮 (四湖)", val: "雲林縣四湖鄉" }
    ],
    // 南部
    嘉義縣: [
        { name: "東石", val: "嘉義縣東石鄉" },
        { name: "布袋", val: "嘉義縣布袋鎮" }
    ],
    臺南市: [
        { name: "將軍", val: "臺南市將軍區" },
        { name: "安平", val: "臺南市安平區" }
    ],
    高雄市: [
        { name: "興達 (茄萣)", val: "高雄市茄萣區" },
        { name: "彌陀", val: "高雄市彌陀區" },
        { name: "旗津", val: "高雄市旗津區" }
    ],
    屏東縣: [
        { name: "東港", val: "屏東縣東港鎮" },
        { name: "小琉球", val: "屏東縣琉球鄉" },
        { name: "後壁湖 (恆春)", val: "屏東縣恆春鎮" }
    ],
    // 東部
    宜蘭縣: [
        { name: "烏石/大溪 (頭城)", val: "宜蘭縣頭城鎮" },
        { name: "蘇澳", val: "宜蘭縣蘇澳鎮" }
    ],
    花蓮縣: [
        { name: "花蓮港", val: "花蓮縣花蓮市" },
        { name: "石梯坪 (豐濱)", val: "花蓮縣豐濱鄉" }
    ],
    臺東縣: [
        { name: "成功", val: "臺東縣成功鎮" },
        { name: "富岡 (臺東市)", val: "臺東縣臺東市" },
        { name: "綠島", val: "臺東縣綠島鄉" },
        { name: "蘭嶼", val: "臺東縣蘭嶼鄉" }
    ],
    // 外島
    澎湖縣: [
        { name: "馬公", val: "澎湖縣馬公市" },
        { name: "吉貝 (白沙)", val: "澎湖縣白沙鄉" },
        { name: "七美", val: "澎湖縣七美鄉" }
    ],
    金門縣: [
        { name: "金門 (金城)", val: "金門縣金城鎮" }
    ],
    連江縣: [
        { name: "南竿 (馬祖)", val: "連江縣南竿鄉" },
        { name: "東引", val: "連江縣東引鄉" }
    ]
};

// ==========================================
// 3. 核心功能：根據選定縣市一口氣渲染所有測站潮汐圖表
// ==========================================
async function renderAllCountyCharts() {
    const selector = document.getElementById("county-selector");
    if (!selector) return;
    
    const selectedCounty = selector.value;
    const stations = stationMapping[selectedCounty];
    const wrapper = document.getElementById("all-charts-wrapper");
    
    if (!wrapper) return;
    wrapper.innerHTML = "";

    for (let i = 0; i < stations.length; i++) {
        const stationObj = stations[i];
        const displayName = stationObj.name;
        const queryValue = stationObj.val;
        const chartId = `tidal-chart-${i}`;

        const chartDiv = document.createElement("div");
        chartDiv.id = chartId;
        chartDiv.className = "chart-card";
        wrapper.appendChild(chartDiv);

        try {
            const response = await fetch(`/api/get_tidal_data?station=${queryValue}`);
            const data = await response.json();

            if (!data.success) {
                chartDiv.innerHTML = `<p style="color:#ff6b6b; text-align:center; padding-top:150px;">❌ 無法取得 ${displayName} 的潮汐資料: ${data.message}</p>`;
                continue;
            }

            const trace = {
                x: data.times,
                y: data.heights,
                mode: "lines+markers",
                name: "預報潮高",
                line: {
                    shape: "spline",
                    color: "#00d4ff",
                    width: 3,
                },
                marker: { size: 6, color: "#007bb5" },
                fill: "tozeroy",
                fillcolor: "rgba(0, 212, 255, 0.2)",
                type: "scatter",
            };

            const layout = {
                title: {
                    text: `🌊 ${displayName} 潮汐預報曲線`,
                    font: {
                        color: "#333333",
                        size: 20,
                        family: "Arial, sans-serif",
                    },
                },
                paper_bgcolor: "#ffffff",
                plot_bgcolor: "#ffffff",
                font: { color: "#555" },
                margin: { l: 45, r: 20, t: 50, b: 60 },
                xaxis: {
                    title: "時間",
                    gridcolor: "#e5e5e5",
                    tickangle: 30,
                    zeroline: false,
                },
                yaxis: {
                    title: "潮高 (cm)",
                    gridcolor: "#e5e5e5",
                    zerolinecolor: "#999",
                },
            };

            const config = {
                responsive: true,
                displayModeBar: false,
            };
            Plotly.newPlot(chartId, [trace], layout, config);
        } catch (error) {
            console.error(`${displayName} 圖表載入失敗:`, error);
            chartDiv.innerHTML = `<p style="color:#ff6b6b; text-align:center; padding-top:150px;">${displayName} 載入失敗</p>`;
        }
    }
}

// ==========================================
// 4. 綁定「加入釣點」按鈕事件
// ==========================================
function bindAddSpotEvent() {
    const addSpotBtn = document.getElementById("add-spot-btn");
    if (!addSpotBtn) return;

    addSpotBtn.addEventListener("click", async () => {
        const spotInput = document.getElementById("spot-input");
        const spotName = spotInput ? spotInput.value.trim() : "";
        
        if (!spotName) {
            alert("請輸入釣點名稱！");
            return;
        }

        const originalText = addSpotBtn.innerText;
        addSpotBtn.disabled = true;

        try {
            // 步驟 1：模糊比對尋找相似的釣點防防呆
            addSpotBtn.innerText = "檢查釣點紀錄中...";
            const spotsResponse = await fetch("/api/my_spots");
            const spotsData = await spotsResponse.json();

            if (spotsData.status === "success") {
                const matchedSpot = spotsData.spots.find(
                    (spot) => spot.includes(spotName) || spotName.includes(spot)
                );

                if (matchedSpot) {
                    alert(`通知：系統發現您已經建立過「${matchedSpot}」，將為您整合紀錄並開啟相機。`);
                    localStorage.setItem("current_fishing_spot", matchedSpot);
                    window.location.href = cameraPageUrl; // 變數由 HTML 端傳入
                    return;
                }
            }

            // 步驟 2：如果沒建立過，呼叫 LLM 驗證
            addSpotBtn.innerText = "AI 驗證釣點中...";
            const response = await fetch("/api/llm/validate_spot", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ spot_name: spotName }),
            });

            const data = await response.json();

            if (data.valid) {
                localStorage.setItem("current_fishing_spot", spotName);
                window.location.href = cameraPageUrl;
            } else {
                alert(data.message || "請輸入正確釣點名稱");
            }
        } catch (error) {
            console.error("驗證發生錯誤:", error);
            alert("連線發生錯誤，請稍後再試！");
        } finally {
            addSpotBtn.innerText = originalText;
            addSpotBtn.disabled = false;
        }
    });
}

// ==========================================
// 5. DOM 載入完畢初始化
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    // 執行 AI 背景任務檢查
    checkAiTaskStatus();

    // 初始化渲染圖表
    const countySelect = document.getElementById("county-selector");
    renderAllCountyCharts();

    if (countySelect) {
        countySelect.addEventListener("change", renderAllCountyCharts);
    }

    // 綁定加入釣點功能
    bindAddSpotEvent();
});