document.addEventListener('DOMContentLoaded', () => {
    const inputField = document.getElementById('middle-input');
    const submitButton = document.getElementById('bottom-button');

    submitButton.addEventListener('click', async () => {
        const textValue = inputField.value.trim();

        if (!textValue) {
            alert('請先輸入內容！');
            return;
        }

        submitButton.disabled = true;
        submitButton.innerText = "處理中...";

        try {
            const response = await fetch('/api/LLM', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ input_text: textValue })
            });

            const result = await response.json();

            if (result.status === 'success') {
                console.log('LLM 回應:', result.response);
                alert("LLM 說: " + result.response); 
            } else {
                console.error('發生錯誤:', result.message);
                alert("錯誤: " + result.message);
            }
            
        } catch (error) {
            console.error('API 請求失敗:', error);
            alert('網路連線發生錯誤');
        } finally {
            submitButton.disabled = false;
            submitButton.innerText = "Button";
        }
    });
});