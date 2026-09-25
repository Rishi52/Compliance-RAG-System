const API_BASE_URL = window.COMPLIANCE_API_URL || "http://127.0.0.1:8000";

const form = document.getElementById("question-form");
const input = document.getElementById("question");
const sendButton = document.getElementById("send-btn");
const chatBox = document.getElementById("chat-box");
const chatContainer = document.getElementById("chat-container");
const systemStatus = document.getElementById("system-status");
const statusLabel = document.getElementById("status-label");

let requestInProgress = false;
let activeController = null;

document.addEventListener("DOMContentLoaded", () => {
    checkApiHealth();
    input.focus();
});

form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (requestInProgress) {
        activeController?.abort();
        return;
    }
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
        const response = await fetch(`${API_BASE_URL}/health/ready`, {
            signal: AbortSignal.timeout(3500)
        });

        if (response.status === 503) {
            setSystemStatus("offline", "Models not ready");
            return;
        }
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
    const title = createElement("strong", "", "Connecting to the answer stream");
    const detail = createElement("span", "", "Waiting for the backend · 0s");
    const progressBar = createElement("div", "progress-bar");
    const previewLabel = createElement("span", "preview-label", "Live preview · citations not yet verified");
    const preview = createElement("div", "message-bubble draft-preview");
    preview.setAttribute("aria-live", "off");
    preview.hidden = true;
    previewLabel.hidden = true;

    copy.append(title, detail);
    row.append(spinner, copy);
    bubble.append(row, progressBar);
    content.append(bubble, previewLabel, preview);
    message.append(createAvatar("fa-solid fa-shield-halved"), content);
    chatBox.append(message);
    scrollToLatest();

    const startedAt = performance.now();
    let description = "Waiting for the backend";
    const timer = window.setInterval(() => {
        const elapsed = Math.floor((performance.now() - startedAt) / 1000);
        detail.textContent = `${description} · ${elapsed}s`;
    }, 1000);

    return {
        updateStage(stage) {
            const stages = {
                retrieving: ["Searching safeguards", "Retrieving and reranking CIS evidence"],
                selecting: ["Selecting evidence", "Keeping relevant source passages"],
                generating: ["Generating answer", "Ollama is writing a draft"],
                validating: ["Checking citations", "Verifying the finished answer"]
            };
            const [label, detailText] = stages[stage] || ["Generating answer", "Processing your question"];
            title.textContent = label;
            description = detailText;
            detail.textContent = `${description} · ${Math.floor((performance.now() - startedAt) / 1000)}s`;
        },
        appendDraft(text) {
            preview.hidden = false;
            previewLabel.hidden = false;
            preview.classList.add("cursor");
            preview.append(document.createTextNode(text));
            scrollToLatest();
        },
        retry() {
            preview.textContent = "";
            preview.hidden = true;
            previewLabel.hidden = true;
            title.textContent = "Retrying citation check";
            description = "Generating a corrected answer";
        },
        complete(data, elapsedMs, firstPreviewMs) {
            window.clearInterval(timer);
            bubble.remove();
            previewLabel.remove();
            preview.remove();

            const answer = createElement("div", "message-bubble");
            appendAnswerWithCitations(answer, data.answer || "No answer was returned.");
            content.append(answer);

            const sources = Array.isArray(data.sources) ? data.sources : [];
            if (sources.length > 0) content.append(createSources(sources));

            const meta = createElement("div", "message-meta");
            if (firstPreviewMs !== null) {
                meta.append(createElement("span", "meta-chip", `First preview ${(firstPreviewMs / 1000).toFixed(1)}s`));
            }
            meta.append(
                createElement("span", "meta-chip", `Total ${(elapsedMs / 1000).toFixed(1)}s`),
                createElement(
                    "span",
                    "meta-chip",
                    data.citation_valid ? "Citation labels checked" : "Citation check failed · abstained"
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
        },
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
        if (/^\[S\d+\]$/.test(part)) {
            container.append(createElement("span", "citation-token", part));
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
        document.createTextNode(`${sources.length} CIS source${sources.length === 1 ? "" : "s"}`),
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

async function readEventStream(response, onEvent) {
    if (!response.body) throw new Error("Your browser cannot read streamed responses.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let completed = false;

    function processLine(line) {
        if (!line.trim()) return;
        const event = JSON.parse(line);
        if (completed) throw new Error("The answer stream sent data after completion.");
        onEvent(event);
        if (event.type === "complete") completed = true;
    }

    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();
            for (const line of lines) processLine(line);
            if (buffer.length > 1024 * 1024) {
                throw new Error("The answer stream exceeded its size limit.");
            }
        }
        buffer += decoder.decode();
        if (buffer.trim()) processLine(buffer);
        if (!completed) throw new Error("The answer stream ended before completion.");
    } finally {
        reader.releaseLock();
    }
}

async function sendQuestion() {
    const question = input.value.trim();
    if (!question || requestInProgress) return;

    requestInProgress = true;
    activeController = new AbortController();
    sendButton.setAttribute("aria-label", "Stop waiting for answer");
    sendButton.firstElementChild.className = "fa-solid fa-stop";
    input.disabled = true;
    removeWelcome();
    addUserMessage(question);
    input.value = "";
    resizeComposer();

    const progress = addProgressMessage();
    const startedAt = performance.now();
    let firstPreviewMs = null;

    try {
        const response = await fetch(`${API_BASE_URL}/chat/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question }),
            signal: activeController.signal
        });
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            if (response.status === 503) setSystemStatus("offline", "Models not ready");
            throw new Error(getErrorMessage(response, data));
        }

        await readEventStream(response, (event) => {
            if (event.type === "stage") {
                progress.updateStage(event.stage);
            } else if (event.type === "draft") {
                if (firstPreviewMs === null) firstPreviewMs = performance.now() - startedAt;
                progress.appendDraft(event.text);
            } else if (event.type === "retry") {
                progress.retry();
            } else if (event.type === "complete") {
                progress.complete(event.result, performance.now() - startedAt, firstPreviewMs);
            } else if (event.type === "error") {
                throw new Error(event.message || "The server could not complete the request.");
            }
        });
        setSystemStatus("online", "API ready");
    } catch (error) {
        progress.remove();
        if (error?.name === "AbortError") {
            addErrorMessage("Stopped waiting for this answer. The server may still be processing it.");
            return;
        }
        if (error instanceof TypeError) setSystemStatus("offline", "API unavailable");
        addErrorMessage(
            error instanceof Error
                ? error.message
                : "Unable to connect to the API. Confirm that the backend is running."
        );
    } finally {
        requestInProgress = false;
        activeController = null;
        sendButton.setAttribute("aria-label", "Send question");
        sendButton.firstElementChild.className = "fa-solid fa-arrow-up";
        input.disabled = false;
        input.focus();
    }
}
