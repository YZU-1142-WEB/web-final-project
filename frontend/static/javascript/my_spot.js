// frontend/static/javascript/my_spot.js

document.addEventListener("DOMContentLoaded", () => {
    loadMySpots();
});

// 1. 載入該使用者創過的所有釣點
async function loadMySpots() {
    const menuContainer = document.getElementById("spotMenu");
    try {
        const response = await fetch("/api/my_spots");
        const data = await response.json();

        if (data.status === "success" && data.spots.length > 0) {
            menuContainer.innerHTML = "";

            data.spots.forEach((spot) => {
                const button = document.createElement("button");
                button.className = "spot-btn";
                button.innerText = `📍 ${spot}`;
                button.onclick = () => {
                    document
                        .querySelectorAll(".spot-btn")
                        .forEach((btn) => btn.classList.remove("active"));
                    button.classList.add("active");
                    loadSpotImages(spot);
                };
                menuContainer.appendChild(button);
            });
        } else {
            menuContainer.innerHTML =
                "<p class='no-data'>目前還沒有建立過任何釣點紀錄喔！</p>";
        }
    } catch (error) {
        console.error("無法載入釣點清單:", error);
        menuContainer.innerHTML =
            "<p class='no-data' style='color:red;'>伺服器連線失敗</p>";
    }
}

// 2. 根據點選的釣點，抓取對應的所有照片
async function loadSpotImages(spotName) {
    const gridContainer = document.getElementById("imageGrid");
    const titleContainer = document.getElementById("currentSpotTitle");

    titleContainer.innerText = `⚓ 正在讀取...`;
    gridContainer.innerHTML = "<div class='no-data'>載入中... 🐟</div>";

    try {
        const response = await fetch(
            `/api/spots/${encodeURIComponent(spotName)}/images`,
        );
        const data = await response.json();

        if (data.status === "success" && data.images.length > 0) {
            // 套用新樣式類別 .delete-spot-btn
            titleContainer.innerHTML = `
                🐟【${spotName}】的歷史漁獲紀錄 (${data.images.length} 張)
                <button onclick="handleDeleteSpot('${spotName}')" class="delete-spot-btn">🗑️ 刪除此釣點</button>
            `;

            gridContainer.innerHTML = "";

            data.images.forEach((img) => {
                const card = document.createElement("div");
                card.className = "fish-card";

                // 套用新樣式類別 .delete-photo-btn，並移除原本行內的 style 屬性
                card.innerHTML = `
                    <img src="${img.image_url}" alt="魚類相片" onerror="this.src='https://via.placeholder.com/220x180?text=圖片載入失敗'">
                    <div class="fish-info">
                        <p class="fish-name">${img.fish_type || "未辨識成功"}</p>
                        <p class="uploader">🎣 釣客: ${img.username}</p>
                        <button onclick="handleDeletePhoto('${img.id}', '${spotName}')" class="delete-photo-btn">🗑️ 刪除照片</button>
                    </div>
                `;
                gridContainer.appendChild(card);
            });
        } else {
            titleContainer.innerText = `📌【${spotName}】`;
            gridContainer.innerHTML =
                "<div class='no-data'>這個釣點目前空空如也，快去釣一隻吧！</div>";
        }
    } catch (error) {
        console.error("相簿載入失敗:", error);
        gridContainer.innerHTML =
            "<div class='no-data' style='color:red;'>無法取得該釣點的照片</div>";
    }
}

// 3. 刪除單張照片的邏輯
async function handleDeletePhoto(docId, spotName) {
    if (!confirm("確定要刪除這張照片嗎？這個動作無法復原喔！")) {
        return;
    }

    try {
        const response = await fetch(`/api/picture/${docId}`, {
            method: "DELETE",
        });
        const data = await response.json();

        if (data.status === "success") {
            alert("照片已成功刪除！");
            loadSpotImages(spotName); // 重新載入這個釣點的照片更新畫面
        } else {
            alert("刪除失敗：" + data.message);
        }
    } catch (error) {
        console.error("刪除照片發生錯誤:", error);
        alert("系統錯誤，無法刪除照片。");
    }
}

// 4. 刪除整個釣點的邏輯
async function handleDeleteSpot(spotName) {
    if (
        !confirm(
            `警告：確定要刪除整個【${spotName}】釣點嗎？\n這會把裡面的照片紀錄一併清空，且無法復原！`,
        )
    ) {
        return;
    }

    try {
        const response = await fetch(
            `/api/spots/${encodeURIComponent(spotName)}`,
            { method: "DELETE" },
        );
        const data = await response.json();

        if (data.status === "success") {
            alert(`已成功刪除【${spotName}】！`);

            if (localStorage.getItem("current_fishing_spot") === spotName) {
                localStorage.removeItem("current_fishing_spot");
            }

            loadMySpots();
            document.getElementById("currentSpotTitle").innerText = "請先選取釣點";
            document.getElementById("imageGrid").innerHTML =
                "<div class='no-data'>尚未選取任何釣點，或該釣點內目前沒有照片。</div>";
        } else {
            alert("刪除失敗：" + data.message);
        }
    } catch (error) {
        console.error("刪除釣點發生錯誤:", error);
        alert("系統錯誤，無法刪除釣點。");
    }
}