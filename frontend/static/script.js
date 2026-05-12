document.addEventListener("DOMContentLoaded", () => {
	const inputField = document.getElementById("middle-input");
	const submitButton = document.getElementById("bottom-button");

	submitButton.addEventListener("click", async () => {
		const textValue = inputField.value.trim();

		if (!textValue) {
			alert("請先輸入內容！");
			return;
		}

		submitButton.disabled = true;
		submitButton.innerText = "處理中...";

		try {
			const response = await fetch("/api/LLM", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({ input_text: textValue }),
			});

			const result = await response.json();

			if (result.success === "success") {
				console.log("LLM 回應:", result.reply);
				alert("LLM 說: " + result.reply);
			} else {
				console.error("發生錯誤:", result.reply);
				alert("錯誤: " + result.reply);
			}
		} catch (error) {
			console.error("API 請求失敗:", error);
			alert("網路連線發生錯誤");
		} finally {
			submitButton.disabled = false;
			submitButton.innerText = "Button";
		}
	});
});

document.addEventListener("DOMContentLoaded", () => {
    const chatInput = document.getElementById('middle-input');
    const sendBtn = document.getElementById('require-LLM-button');

    async function submitLlmTask() {
        const text = chatInput.value.trim();
        if (!text) return;

        // UI 變化：讓使用者知道正在跑
        const originalText = sendBtn.innerText;
        sendBtn.innerText = "思考中...";
        sendBtn.disabled = true;
        chatInput.disabled = true;

        try {
            // 1. 發送問題，取得任務 ID
            const response = await fetch('/api/ask_llm_async', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ input_text: text })
            });
            const data = await response.json();

            if (response.ok && data.status === "success") {
                const taskId = data.task_id;
                
                // 2. 開始不斷詢問後端「AI 想好沒？」
                const interval = setInterval(async () => {
                    const checkRes = await fetch(`/api/check_llm_task/${taskId}`);
                    const checkData = await checkRes.json();

                    if (checkData.status === "completed") {
                        // 處理完成！停止詢問，跳轉到專屬結果頁
                        clearInterval(interval);
                        window.location.href = `/llm_result/${taskId}`;
                    } else if (checkData.status === "failed" || checkData.status === "not_found") {
                        // 發生錯誤
                        clearInterval(interval);
                        alert("❌ 發生錯誤：" + (checkData.error_message || "未知錯誤"));
                        resetUI();
                    }
                }, 2000); // 每 2 秒問一次
            } else {
                alert("錯誤：" + data.message);
                resetUI();
            }
        } catch (error) {
            console.error("錯誤:", error);
            alert("連線發生錯誤");
            resetUI();
        }

        // 復原 UI 的輔助函數
        function resetUI() {
            sendBtn.innerText = originalText;
            sendBtn.disabled = false;
            chatInput.disabled = false;
        }
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', submitLlmTask);
    }
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') submitLlmTask();
        });
    }
});