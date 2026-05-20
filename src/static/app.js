const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const uploadBtn    = document.getElementById('upload-btn');
const selectedFile = document.getElementById('selected-file');
const statusEl     = document.getElementById('status');
const previewIframe = document.getElementById('preview-iframe');
const previewJson  = document.getElementById('preview-json');
const toggleRaw    = document.getElementById('toggle-raw');

let currentFile = null;
let rawJson = '';
let showingRaw = false;

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
  if (e.target.tagName !== 'LABEL') fileInput.click();
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
  previewIframe.style.display = 'block';
  previewJson.style.display   = 'none';
  previewIframe.srcdoc = html;
  showingRaw = false;
  toggleRaw.textContent = 'Show raw JSON';
}

function showJsonOnly(data) {
  previewIframe.style.display = 'none';
  previewJson.style.display   = 'block';
  previewJson.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  toggleRaw.hidden = true;
}

function setPreview(body) {
  const result = body.result;
  rawJson = JSON.stringify(body, null, 2);

  // Case 1: result is a string — check if it looks like HTML
  if (typeof result === 'string') {
    if (looksLikeHtml(result)) {
      showHtml(result);
      toggleRaw.hidden = false;
      toggleRaw.textContent = 'Show raw JSON';
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
      toggleRaw.hidden = false;
      toggleRaw.textContent = 'Show raw JSON';
      return;
    }
    // Non-HTML JSON object: show as formatted JSON
    showJsonOnly(result);
    return;
  }

  // Fallback
  showJsonOnly(result ?? body);
}

toggleRaw.addEventListener('click', () => {
  if (!showingRaw) {
    previewIframe.style.display = 'none';
    previewJson.style.display   = 'block';
    previewJson.textContent = rawJson;
    toggleRaw.textContent = 'Show preview';
    showingRaw = true;
  } else {
    previewJson.style.display = 'none';
    previewIframe.style.display = 'block';
    toggleRaw.textContent = 'Show raw JSON';
    showingRaw = false;
  }
});

// --- upload ---
uploadBtn.addEventListener('click', async () => {
  if (!currentFile) return;

  uploadBtn.disabled = true;
  setStatus('Uploading…', 'busy');

  const formData = new FormData();
  formData.append('file', currentFile);

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
