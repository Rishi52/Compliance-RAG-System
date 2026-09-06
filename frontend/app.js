const API_BASE_URL = window.COMPLIANCE_API_URL || "http://127.0.0.1:8000";

const form = document.getElementById("question-form");
const input = document.getElementById("question");
const sendButton = document.getElementById("send-btn");
const chatBox = document.getElementById("chat-box");
const chatContainer = document.getElementById("chat-container");
const systemStatus = document.getElementById("system-status");
const statusLabel = document.getElementById("status-label");

let requestInProgress = false;

document.addEventListener("DOMContentLoaded", () => {
    checkApiHealth();
    input.focus();
});

form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendQuestion();
});

input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
    }
});

input.addEventListener("input", resizeComposer);

document.querySelectorAll(".suggestion").forEach((button) => {
    button.addEventListener("click", () => {
        input.value = button.dataset.question || "";
        resizeComposer();
        form.requestSubmit();
    });
});

async function checkApiHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health/live`, {
            signal: AbortSignal.timeout(3500)
        });

        if (!response.ok) throw new Error("API health check failed");
        setSystemStatus("online", "API ready");
    } catch (_) {
        setSystemStatus("offline", "API offline");
    }
}

function setSystemStatus(state, label) {
    systemStatus.classList.remove("online", "offline");
    systemStatus.classList.add(state);
    statusLabel.textContent = label;
}

function resizeComposer() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
}

function scrollToLatest() {
    requestAnimationFrame(() => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    });
}

function removeWelcome() {
    document.getElementById("welcome-message")?.remove();
}

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function createAvatar(iconClass) {
    const avatar = createElement("div", "avatar");
    const icon = createElement("i", iconClass);
    avatar.append(icon);
    return avatar;
}

function addUserMessage(question) {
    const message = createElement("article", "message user-message");
    const content = createElement("div", "message-content");
    const bubble = createElement("div", "message-bubble", question);

    content.append(bubble);
    message.append(createAvatar("fa-solid fa-user"), content);
    chatBox.append(message);
    scrollToLatest();
}

function addProgressMessage() {
    const message = createElement("article", "message bot-message");
    const content = createElement("div", "message-content");
    const bubble = createElement("div", "message-bubble progress-card");
    const row = createElement("div", "progress-row");
    const spinner = createElement("div", "spinner");
    const copy = createElement("div", "progress-copy");
    const title = createElement("strong", "", "Searching safeguards");
    const detail = createElement("span", "", "Finding the most relevant CIS evidence · 0s");
    const progressBar = createElement("div", "progress-bar");

    copy.append(title, detail);
    row.append(spinner, copy);
    bubble.append(row, progressBar);
    content.append(bubble);
    message.append(createAvatar("fa-solid fa-shield-halved"), content);
    chatBox.append(message);
    scrollToLatest();

    const startedAt = performance.now();
    const timer = window.setInterval(() => {
        const elapsed = Math.floor((performance.now() - startedAt) / 1000);
        let stage = "Searching safeguards";
        let description = "Finding the most relevant CIS evidence";

        if (elapsed >= 3) {
            stage = "Reviewing evidence";
            description = "Reranking and selecting source passages";
        }
        if (elapsed >= 8) {
            stage = "Generating grounded answer";
            description = "Writing and checking source citations";
        }

        title.textContent = stage;
        detail.textContent = `${description} · ${elapsed}s`;
    }, 1000);

    return {
        remove() {
            window.clearInterval(timer);
            message.remove();
        }
    };
}

function appendAnswerWithCitations(container, answer) {
    const citationPattern = /(\[S\d+\])/g;
    const parts = answer.split(citationPattern);

    parts.forEach((part) => {
        if (citationPattern.test(part)) {
            container.append(createElement("span", "citation-token", part));
            citationPattern.lastIndex = 0;
        } else {
            container.append(document.createTextNode(part));
        }
    });
}

function createSources(sources) {
    const details = createElement("details", "sources");
    const summary = createElement("summary");
    summary.append(
        createElement("i", "fa-solid fa-book-open"),
        document.createTextNode(`${sources.length} verified source${sources.length === 1 ? "" : "s"}`),
        createElement("i", "fa-solid fa-chevron-down")
    );

    const list = createElement("ul", "sources-list");
    sources.forEach((source) => {
        const item = createElement("li", "source-card");
        const id = createElement("span", "source-id", source.source_id);
        const sourceText = createElement("div");
        const title = createElement(
            "strong",
            "",
            `Safeguard ${source.safeguard_id} · ${source.safeguard_name}`
        );
        const control = createElement(
            "small",
            "",
            `Control ${source.control_id} · ${source.control_name}`
        );
        const page = createElement("span", "page-badge", `Page ${source.page}`);

        sourceText.append(title, control);
        item.append(id, sourceText, page);
        list.append(item);
    });

    details.append(summary, list);
    return details;
}

async function revealAnswer(bubble, answer) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion || answer.length < 24) {
        appendAnswerWithCitations(bubble, answer);
        return;
    }

    bubble.classList.add("cursor");
    const chunks = answer.match(/\S+\s*/g) || [answer];
    const delay = Math.max(8, Math.min(22, 520 / chunks.length));

    for (let index = 0; index < chunks.length; index += 1) {
        bubble.append(document.createTextNode(chunks[index]));
        if (index % 4 === 0) scrollToLatest();
        await new Promise((resolve) => window.setTimeout(resolve, delay));
    }

    bubble.classList.remove("cursor");
    bubble.textContent = "";
    appendAnswerWithCitations(bubble, answer);
}

async function addAssistantMessage(data, elapsedMs) {
    const message = createElement("article", "message bot-message");
    const content = createElement("div", "message-content");
    const bubble = createElement("div", "message-bubble");
    const meta = createElement("div", "message-meta");
    const sourceCount = Array.isArray(data.sources) ? data.sources.length : 0;

    message.append(createAvatar("fa-solid fa-shield-halved"), content);
    content.append(bubble);
    chatBox.append(message);
    scrollToLatest();

    await revealAnswer(bubble, data.answer || "No answer was returned.");

    if (sourceCount > 0) {
        content.append(createSources(data.sources));
    }

    meta.append(
        createElement("span", "meta-chip", `${(elapsedMs / 1000).toFixed(1)}s`),
        createElement(
            "span",
            "meta-chip",
            data.citation_valid ? "Citations verified" : "Citation check incomplete"
        )
    );

    const copyButton = createElement("button", "copy-button");
    copyButton.type = "button";
    copyButton.append(
        createElement("i", "fa-regular fa-copy"),
        document.createTextNode("Copy")
    );
    copyButton.addEventListener("click", async () => {
        await navigator.clipboard.writeText(data.answer || "");
        copyButton.lastChild.textContent = "Copied";
        window.setTimeout(() => {
            copyButton.lastChild.textContent = "Copy";
        }, 1500);
    });
    meta.append(copyButton);
    content.append(meta);
    scrollToLatest();
}

function addErrorMessage(messageText) {
    const message = createElement("article", "message bot-message error-message");
    const content = createElement("div", "message-content");
    const bubble = createElement("div", "message-bubble", messageText);
    content.append(bubble);
    message.append(createAvatar("fa-solid fa-triangle-exclamation"), content);
    chatBox.append(message);
    scrollToLatest();
}

function getErrorMessage(response, data) {
    if (response.status === 422) {
        return "That question could not be processed. Rephrase it as a direct CIS Controls compliance question.";
    }
    if (response.status === 503) {
        return "The compliance models are still starting. Please wait a moment and try again.";
    }
    return data?.detail || "The server could not complete the request. Please try again.";
}

async function sendQuestion() {
    const question = input.value.trim();
    if (!question || requestInProgress) return;

    requestInProgress = true;
    sendButton.disabled = true;
    input.disabled = true;
    removeWelcome();
    addUserMessage(question);
    input.value = "";
    resizeComposer();

    const progress = addProgressMessage();
    const startedAt = performance.now();

    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question })
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(getErrorMessage(response, data));
        }

        progress.remove();
        setSystemStatus("online", "API ready");
        await addAssistantMessage(data, performance.now() - startedAt);
    } catch (error) {
        progress.remove();
        setSystemStatus("offline", "API unavailable");
        addErrorMessage(
            error instanceof Error
                ? error.message
                : "Unable to connect to the API. Confirm that the backend is running."
        );
    } finally {
        requestInProgress = false;
        sendButton.disabled = false;
        input.disabled = false;
        input.focus();
    }
}
