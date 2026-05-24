const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const chooseFileBtn = document.getElementById('choose-file-btn');
const selectedFile = document.getElementById('selected-file');
const emailInput = document.getElementById('email-input');
const statusEl = document.getElementById('status');
const previewIframe = document.getElementById('preview-iframe');
const previewJson = document.getElementById('preview-json');
const htmlResult = document.getElementById('html-result');
const emptyState = document.getElementById('empty-state');
const downloadBtn = document.getElementById('download-btn');
const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendChatBtn = document.getElementById('send-chat-btn');
const chatbotPanel = document.getElementById('chatbot-panel');
const resultPanel = document.getElementById('result-panel');
const hideChatbotBtn = document.getElementById('hide-chatbot-btn');
const hideResultBtn = document.getElementById('hide-result-btn');
const panelButtons = document.querySelectorAll('[data-panel]');

let currentFile = null;
let chatMessages = [];
let documentMetadata = {};

// --- panel state ---
function updatePanelControls() {
  const chatbotCollapsed = chatbotPanel.classList.contains('collapsed');
  const resultCollapsed = resultPanel.classList.contains('collapsed');

  hideChatbotBtn.disabled = resultCollapsed;
  hideResultBtn.disabled = chatbotCollapsed;
}

function togglePanel(panelName) {
  const panel = panelName === 'chatbot' ? chatbotPanel : resultPanel;
  const otherPanel = panelName === 'chatbot' ? resultPanel : chatbotPanel;

  if (!panel.classList.contains('collapsed') && otherPanel.classList.contains('collapsed')) {
    return;
  }

  panel.classList.toggle('collapsed');
  updatePanelControls();
}

panelButtons.forEach(button => {
  button.addEventListener('click', () => {
    const panelName = button.dataset.panel;
    const panel = panelName === 'chatbot' ? chatbotPanel : resultPanel;

    if (button.classList.contains('collapsed-bar') && !panel.classList.contains('collapsed')) {
      return;
    }

    togglePanel(panelName);
  });
});

updatePanelControls();

// --- download ---
downloadBtn.addEventListener('click', async () => {
  if (!currentFile) return;
  const base = currentFile.name.replace(/\.[^.]+$/, '');
  const downloadName = base + '.html';
  try {
    const res = await fetch(`/download-file?filename=${encodeURIComponent(currentFile.name)}`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setStatus(`Download error: ${body.error || res.statusText}`, 'error');
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = downloadName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    setStatus(`Download error: ${err.message}`, 'error');
  }
});

// --- file selection ---
function updateChatAvailability() {
  const enabled = Boolean(currentFile);
  chatInput.disabled = !enabled;
  sendChatBtn.disabled = !enabled;
}

function setFile(file) {
  currentFile = file;
  selectedFile.textContent = file ? `Selected: ${file.name}` : '';
  uploadBtn.disabled = !file;
  updateChatAvailability();
}

fileInput.addEventListener('change', () => setFile(fileInput.files[0] || null));

// --- drag and drop ---
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});
dropZone.addEventListener('click', e => {
  if (e.target === chooseFileBtn) return;
  fileInput.click();
});
dropZone.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') fileInput.click();
});

// --- status helpers ---
function setStatus(msg, type) {
  statusEl.textContent = msg;
  statusEl.className = `status ${type || ''}`.trim();
}

// --- preview helpers ---
function looksLikeHtml(str) {
  return /<[a-z][\s\S]*>/i.test(str);
}

function showHtml(html) {
  htmlResult.classList.remove('hidden');
  previewJson.classList.add('hidden');
  emptyState.classList.add('hidden');
  previewIframe.srcdoc = html;
  downloadBtn.classList.remove('hidden');
}

function showJsonOnly(data) {
  htmlResult.classList.add('hidden');
  previewJson.classList.remove('hidden');
  emptyState.classList.add('hidden');
  previewJson.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  downloadBtn.classList.remove('hidden');
}

function setPreview(body) {
  const result = body.result;

  if (typeof result === 'string') {
    if (looksLikeHtml(result)) {
      showHtml(result);
    } else {
      showJsonOnly(result);
    }
    return;
  }

  if (result !== null && typeof result === 'object') {
    const textField = result.text;
    if (typeof textField === 'string' && looksLikeHtml(textField)) {
      showHtml(textField);
      return;
    }
    showJsonOnly(result);
    return;
  }

  showJsonOnly(result ?? body);
}

// --- chat helpers ---
function normalizeChatResponse(body) {
  let result = body?.result;
  if (typeof result === 'string') {
    try { result = JSON.parse(result); } catch { return result; }
  }
  if (result && typeof result === 'object') {
    if (typeof result.output === 'string') return result.output;
    if (typeof result.answer === 'string') return result.answer;
    if (typeof result.text === 'string') return result.text;
    if (typeof result.response === 'string') return result.response;
    return JSON.stringify(result, null, 2);
  }
  return JSON.stringify(body, null, 2);
}

function renderChatMessages() {
  if (!chatMessages.length) {
    chatHistory.innerHTML = '<div class="chat-empty-state">Upload and analyze a document to start chatting about it.</div>';
    return;
  }

  chatHistory.innerHTML = '';
  chatMessages.forEach(message => {
    const messageEl = document.createElement('div');
    messageEl.className = `chat-message ${message.role}`;
    messageEl.textContent = message.text;
    chatHistory.appendChild(messageEl);
  });
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function addChatMessage(role, text) {
  chatMessages.push({ role, text });
  renderChatMessages();
}

async function sendChatMessage() {
  const query = (chatInput.value || '').trim();
  if (!currentFile || !query) return;

  addChatMessage('user', query);
  chatInput.value = '';
  chatInput.disabled = true;
  sendChatBtn.disabled = true;

  const formData = new FormData();
  formData.append('filename', currentFile.name);
  formData.append('query', query);

  const meta = documentMetadata[currentFile.name];
  if (meta) {
    formData.append('company', meta.company);
    formData.append('year', meta.year);
  }

  try {
    const res = await fetch('/document-query', { method: 'POST', body: formData });
    const body = await res.json();

    if (!res.ok) {
      addChatMessage('assistant', `Error: ${body.error || res.statusText}`);
      return;
    }

    addChatMessage('assistant', normalizeChatResponse(body));
  } catch (err) {
    addChatMessage('assistant', `Network error: ${err.message}`);
  } finally {
    updateChatAvailability();
    chatInput.focus();
  }
}

sendChatBtn.addEventListener('click', sendChatMessage);
chatInput.addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    event.preventDefault();
    sendChatMessage();
  }
});

// --- upload ---
uploadBtn.addEventListener('click', async () => {
  if (!currentFile) return;
  const email = (emailInput?.value || '').trim();
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email) {
    setStatus('Error: Email is required', 'error');
    emailInput?.focus();
    return;
  }
  if (!emailPattern.test(email)) {
    setStatus('Error: Enter a valid email address', 'error');
    emailInput?.focus();
    return;
  }

  uploadBtn.disabled = true;
  setStatus('Uploading…', 'busy');

  const formData = new FormData();
  formData.append('file', currentFile);
  formData.append('email', email);

  try {
    const res = await fetch('/upload-file', { method: 'POST', body: formData });
    const body = await res.json();

    if (!res.ok) {
      setStatus(`Error: ${body.error || res.statusText}`, 'error');
      return;
    }

    chatMessages = [];
    renderChatMessages();
    setStatus(`Done: ${body.filename}`, 'ok');
    setPreview(body);

    const result = body.result || {};
    if (result.company || result.year) {
      documentMetadata[body.filename] = {
        company: result.company || '',
        year: result.year || '',
      };
    }
  } catch (err) {
    setStatus(`Network error: ${err.message}`, 'error');
  } finally {
    uploadBtn.disabled = false;
    updateChatAvailability();
  }
});

updateChatAvailability();
renderChatMessages();
