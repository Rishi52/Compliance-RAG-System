// Remove welcome message on first interaction
let isFirstMessage = true;

// Add event listener for Enter key
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById("question");
    input.addEventListener("keypress", function(event) {
        if (event.key === "Enter") {
            event.preventDefault();
            sendQuestion();
        }
    });
});

async function sendQuestion() {
    const input = document.getElementById("question");
    const question = input.value.trim();

    if (!question) return;

    const chatBox = document.getElementById("chat-box");
    const sendBtn = document.getElementById("send-btn");

    if (isFirstMessage) {
        const welcome = document.querySelector('.welcome-message');
        if (welcome) welcome.remove();
        isFirstMessage = false;
    }

    // Add user message
    chatBox.innerHTML += `
    <div class="message user-message">
        <div class="avatar">
            <i class="fa-solid fa-user"></i>
        </div>
        <div class="message-content">
            <div class="message-bubble">
                ${question}
            </div>
        </div>
    </div>
    `;

    input.value = "";
    sendBtn.disabled = true;
    sendBtn.style.opacity = "0.5";

    // Scroll to bottom
    chatBox.scrollTop = chatBox.scrollHeight;

    // Add loading indicator
    const loadingId = 'loading-' + Date.now();
    chatBox.innerHTML += `
    <div class="message bot-message" id="${loadingId}">
        <div class="avatar">
            <i class="fa-solid fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        </div>
    </div>
    `;
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch(
            "http://127.0.0.1:8000/chat",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    question: question
                })
            }
        );

        const data = await response.json();
        
        // Remove loading indicator
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();

        let sourcesHTML = "";
        
        if (data.sources && data.sources.length > 0) {
            data.sources.forEach(source => {
                sourcesHTML += `
                <li>
                    <i class="fa-solid fa-link"></i>
                    <div>
                        <span class="source-badge">Control ${source.control_id}</span>
                        ${source.control_name} 
                        <span class="source-badge" style="margin-left: 8px;">Safeguard ${source.safeguard_id}</span>
                        ${source.safeguard_name}
                        <span style="color: var(--text-secondary); margin-left: 8px; font-size: 0.8rem;">(Page ${source.page})</span>
                    </div>
                </li>
                `;
            });
            
            sourcesHTML = `
            <div class="sources-container">
                <div class="sources-header">
                    <i class="fa-solid fa-book-open"></i> Reference Sources
                </div>
                <ul class="sources-list">
                    ${sourcesHTML}
                </ul>
            </div>
            `;
        }

        // Add bot message
        chatBox.innerHTML += `
        <div class="message bot-message">
            <div class="avatar">
                <i class="fa-solid fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="message-bubble">
                    ${data.answer.replace(/\n/g, "<br>")}
                </div>
                ${sourcesHTML}
            </div>
        </div>
        `;

    } catch (error) {
        // Remove loading indicator
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();
        
        chatBox.innerHTML += `
        <div class="message bot-message">
            <div class="avatar" style="color: var(--danger); border-color: var(--danger);">
                <i class="fa-solid fa-triangle-exclamation"></i>
            </div>
            <div class="message-content">
                <div class="message-bubble" style="border-color: var(--danger);">
                    Sorry, there was an error connecting to the server. Please ensure the backend is running.
                </div>
            </div>
        </div>
        `;
    } finally {
        sendBtn.disabled = false;
        sendBtn.style.opacity = "1";
        chatBox.scrollTop = chatBox.scrollHeight;
        input.focus();
    }
}