const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const uploadBtn    = document.getElementById('upload-btn');
const chooseFileBtn = document.getElementById('choose-file-btn');
const selectedFile = document.getElementById('selected-file');
const emailInput   = document.getElementById('email-input');
const statusEl     = document.getElementById('status');
const previewIframe = document.getElementById('preview-iframe');
const previewJson  = document.getElementById('preview-json');
const htmlResult   = document.getElementById('html-result');
const emptyState   = document.getElementById('empty-state');
const downloadBtn  = document.getElementById('download-btn');

let currentFile = null;

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
function setFile(file) {
  currentFile = file;
  selectedFile.textContent = file ? `Selected: ${file.name}` : '';
  uploadBtn.disabled = !file;
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
  statusEl.className = type;
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

  // Case 1: result is a string — check if it looks like HTML
  if (typeof result === 'string') {
    if (looksLikeHtml(result)) {
      showHtml(result);
    } else {
      showJsonOnly(result);
    }
    return;
  }

  // Case 2: result is a JSON object — check for a "text" field containing HTML
  if (result !== null && typeof result === 'object') {
    const textField = result.text;
    if (typeof textField === 'string' && looksLikeHtml(textField)) {
      showHtml(textField);
      return;
    }
    // Non-HTML JSON object: show as formatted JSON
    showJsonOnly(result);
    return;
  }

  // Fallback
  showJsonOnly(result ?? body);
}

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

    setStatus(`Done: ${body.filename}`, 'ok');
    setPreview(body);
  } catch (err) {
    setStatus(`Network error: ${err.message}`, 'error');
  } finally {
    uploadBtn.disabled = false;
  }
});
