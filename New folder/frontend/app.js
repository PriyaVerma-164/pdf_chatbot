const pdfListElement = document.getElementById("pdfList");
const uploadInput = document.getElementById("pdfUpload");
const uploadButton = document.getElementById("uploadButton");
const refreshButton = document.getElementById("refreshButton");
const dropZone = document.getElementById("dropZone");
const selectedFileName = document.getElementById("selectedFileName");
const uploadStatus = document.getElementById("uploadStatus");
const pdfPreview = document.getElementById("pdfPreview");
const scopeTitle = document.getElementById("scopeTitle");
const scopeSubtitle = document.getElementById("scopeSubtitle");
const previewHint = document.getElementById("previewHint");
const chatWindow = document.getElementById("chatWindow");
const questionInput = document.getElementById("questionInput");
const sendButton = document.getElementById("sendButton");
const loadingIndicator = document.getElementById("loadingIndicator");

let selectedPdf = null;
let pendingUploadFile = null;
let chatHistory = [];
let statusPollTimer = null;
let pdfCache = [];

window.addEventListener("DOMContentLoaded", () => {
  bindUiEvents();
  renderSelectedDocument();
  updateChatAvailability();
  loadPdfList();
});

function bindUiEvents() {
  uploadInput.addEventListener("change", () => {
    const file = uploadInput.files[0];
    if (file) {
      setPendingUploadFile(file);
    }
  });

  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("drag-over");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("drag-over");
  });

  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("drag-over");
    const file = event.dataTransfer.files[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showUploadStatus("Please choose a PDF file.", "error");
      return;
    }
    setPendingUploadFile(file);
  });

  uploadButton.addEventListener("click", uploadPdf);
  refreshButton.addEventListener("click", loadPdfList);
  sendButton.addEventListener("click", askQuestion);

  questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      askQuestion();
    }
  });
}

function setPendingUploadFile(file) {
  pendingUploadFile = file;
  selectedFileName.textContent = file.name;
  showUploadStatus("Ready to upload.", "success");
}

async function uploadPdf() {
  const file = pendingUploadFile || uploadInput.files[0];
  if (!file) {
    showUploadStatus("Select or drop a PDF first.", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  uploadButton.disabled = true;
  uploadButton.textContent = "Uploading...";
  showUploadStatus("Uploading and scheduling ingestion...", "");

  try {
    const response = await fetch("/api/pdf/upload", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Upload failed.");
    }
    pendingUploadFile = null;
    uploadInput.value = "";
    selectedFileName.textContent = "Drop a PDF here";
    showUploadStatus("PDF uploaded and queued for processing.", "success");
    await loadPdfList();
    startStatusPolling();
  } catch (error) {
    showUploadStatus(error.message, "error");
  } finally {
    uploadButton.disabled = false;
    uploadButton.textContent = "Upload";
  }
}

async function loadPdfList() {
  try {
    const response = await fetch("/api/pdf/list");
    if (!response.ok) {
      throw new Error("Could not load document library.");
    }
    const data = await response.json();
    pdfCache = Array.isArray(data.pdfs) ? data.pdfs : [];
    renderPdfList(pdfCache);

    if (selectedPdf) {
      const refreshed = pdfCache.find((pdf) => pdf.id === selectedPdf.id);
      if (refreshed) {
        selectedPdf = refreshed;
        renderSelectedDocument();
      }
    }

    const hasActiveIngestion = pdfCache.some((pdf) => ["pending", "ingesting"].includes(pdf.status));
    if (!hasActiveIngestion && statusPollTimer) {
      clearInterval(statusPollTimer);
      statusPollTimer = null;
    }
  } catch (error) {
    pdfListElement.innerHTML = `<div class="chat-empty">${escapeHtml(error.message)}</div>`;
  }
}

function renderPdfList(pdfs) {
  pdfListElement.innerHTML = "";

  if (!pdfs.length) {
    pdfListElement.innerHTML = `<div class="chat-empty">No processed documents yet.</div>`;
    return;
  }

  pdfs.forEach((pdf) => {
    const item = document.createElement("article");
    item.className = `pdf-item${selectedPdf && selectedPdf.id === pdf.id ? " selected" : ""}`;
    const status = displayStatus(pdf.status);
    const canSelect = pdf.status === "ingested";
    item.innerHTML = `
      <div class="pdf-item-top">
        <div>
          <h3 class="pdf-item-title">${escapeHtml(pdf.pdf_name)}</h3>
          <p class="pdf-item-meta">Pages: ${pdf.total_pages || 0}</p>
        </div>
        <span class="status-pill ${status.className}">${status.label}</span>
      </div>
      <button class="select-button" type="button" ${canSelect ? "" : "disabled"}>
        ${canSelect ? "Select" : "Processing"}
      </button>
    `;
    item.querySelector("button").addEventListener("click", () => selectPdf(pdf));
    pdfListElement.appendChild(item);
  });
}

function selectPdf(pdf) {
  if (pdf.status !== "ingested") {
    showUploadStatus("Choose a completed PDF before starting chat.", "error");
    return;
  }

  selectedPdf = pdf;
  chatHistory = [];
  chatWindow.innerHTML = "";
  appendChatMessage(`Document locked: ${pdf.pdf_name}. Ask a question about this PDF.`, "assistant");
  pdfPreview.src = `/uploads/${encodeURIComponent(pdf.pdf_name)}`;
  renderSelectedDocument();
  renderPdfList(pdfCache);
  updateChatAvailability();
}

function renderSelectedDocument() {
  if (!selectedPdf) {
    scopeTitle.textContent = "Select a document";
    scopeSubtitle.textContent = "Choose a completed PDF from the library.";
    previewHint.textContent = "Metadata and page preview appear after selection.";
    pdfPreview.removeAttribute("src");
    updateChatAvailability();
    return;
  }

  scopeTitle.textContent = selectedPdf.pdf_name;
  scopeSubtitle.textContent = "Choose a question and DocuMind AI will answer only from this document.";
  previewHint.textContent = `${selectedPdf.total_pages || 0} pages available for quick preview.`;
  updateChatAvailability();
}

function updateChatAvailability() {
  const canChat = Boolean(selectedPdf && selectedPdf.status === "ingested");
  questionInput.disabled = !canChat;
  sendButton.disabled = !canChat;
}

async function askQuestion() {
  const question = questionInput.value.trim();
  if (!question) return;

  if (!selectedPdf) {
    appendChatMessage("Select an ingested PDF before asking a question.", "assistant");
    updateChatAvailability();
    return;
  }

  if (selectedPdf.status !== "ingested") {
    appendChatMessage(`This PDF is not ready yet. Current status: ${selectedPdf.status}.`, "assistant");
    await loadPdfList();
    return;
  }

  const historyForRequest = [...chatHistory];
  appendChatMessage(question, "user");
  questionInput.value = "";
  const assistantBubble = appendChatMessage("", "assistant");

  loadingIndicator.classList.remove("hidden");
  sendButton.disabled = true;
  questionInput.disabled = true;

  try {
    const response = await fetch("/api/chat/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pdf_id: selectedPdf.id,
        pdf_name: selectedPdf.pdf_name,
        question,
        chat_history: historyForRequest,
      }),
    });

    if (!response.ok) {
      throw new Error("Chat request failed.");
    }

    if (!response.body) {
      throw new Error("No response stream available.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();
      for (const part of parts) {
        if (!part.startsWith("data:")) continue;
        assistantBubble.textContent += decodeStreamPayload(part.replace(/^data:\s*/, ""));
        chatWindow.scrollTop = chatWindow.scrollHeight;
      }
    }

    if (buffer.startsWith("data:")) {
      assistantBubble.textContent += decodeStreamPayload(buffer.replace(/^data:\s*/, ""));
    }

    chatHistory = [
      ...historyForRequest,
      { role: "user", message: question },
      { role: "assistant", message: assistantBubble.textContent },
    ];
  } catch (error) {
    assistantBubble.textContent = error.message || "This information is not available in the selected PDF.";
    chatHistory = [
      ...historyForRequest,
      { role: "user", message: question },
      { role: "assistant", message: assistantBubble.textContent },
    ];
  } finally {
    loadingIndicator.classList.add("hidden");
    updateChatAvailability();
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }
}

function appendChatMessage(text, role = "assistant") {
  const emptyState = chatWindow.querySelector(".chat-empty");
  if (emptyState) emptyState.remove();

  const bubble = document.createElement("div");
  bubble.className = `chat-message ${role}`;
  bubble.textContent = text;
  chatWindow.appendChild(bubble);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return bubble;
}

function displayStatus(status) {
  if (status === "ingested") {
    return { label: "ingested", className: "" };
  }
  if (status === "failed") {
    return { label: "failed", className: "failed" };
  }
  return { label: "processing", className: "processing" };
}

function startStatusPolling() {
  if (statusPollTimer) {
    clearInterval(statusPollTimer);
  }
  statusPollTimer = setInterval(loadPdfList, 3000);
}

function decodeStreamPayload(payload) {
  try {
    return JSON.parse(payload);
  } catch (error) {
    return payload;
  }
}

function showUploadStatus(message, type) {
  uploadStatus.textContent = message;
  uploadStatus.className = `inline-status ${type || ""}`.trim();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
