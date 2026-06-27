'use strict';

/* ═══════════════════════════════════════
   Utilities
═══════════════════════════════════════ */

function toast(msg, type = 'info', duration = 4000) {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), duration);
}

function fmtTime(secs) {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

/* ═══════════════════════════════════════
   Waveform Renderer (Canvas, no deps)
═══════════════════════════════════════ */

function drawWaveform(canvas, peaks, color = '#10b981', bgColor = 'rgba(0,0,0,0.3)') {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // Background
  ctx.fillStyle = bgColor;
  ctx.fillRect(0, 0, w, h);

  if (!peaks || !peaks.length) return;

  const barW = Math.max(1, w / peaks.length);
  const mid = h / 2;

  ctx.fillStyle = color;

  for (let i = 0; i < peaks.length; i++) {
    const barH = Math.max(1, peaks[i] * mid * 0.9);
    const x = i * barW;
    ctx.fillRect(x, mid - barH, Math.max(1, barW - 1), barH * 2);
  }

  // Centre line
  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  ctx.fillRect(0, mid, w, 1);
}

function resizeCanvas(canvas) {
  const rect = canvas.parentElement.getBoundingClientRect();
  if (rect.width > 0) {
    canvas.width = rect.width;
    canvas.height = 60;
  }
}

/* ═══════════════════════════════════════
   API
═══════════════════════════════════════ */

async function apiUpload(file) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch('/api/upload', { method: 'POST', body: fd });
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || 'Upload failed');
  return d;
}

async function apiWaveform(fileId) {
  const r = await fetch(`/api/waveform/${fileId}`);
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || 'Waveform failed');
  return d;
}

async function apiInfo(fileId) {
  const r = await fetch(`/api/info/${fileId}`);
  return r.json();
}

async function pollTask(taskId, onDone, onError, intervalMs = 1500) {
  const timer = setInterval(async () => {
    const r = await fetch(`/api/task/${taskId}`);
    const d = await r.json();
    if (d.status === 'done') {
      clearInterval(timer);
      onDone(d);
    } else if (d.status === 'error') {
      clearInterval(timer);
      onError(d.error || 'Processing failed');
    }
  }, intervalMs);
}

/* ═══════════════════════════════════════
   Sidebar navigation
═══════════════════════════════════════ */

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    const feature = item.dataset.feature;
    if (!feature) return;

    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    item.classList.add('active');

    // Switch page
    document.querySelectorAll('.feature-page').forEach(p => p.classList.remove('active'));
    const page = document.getElementById(`page-${feature}`);
    if (page) page.classList.add('active');
  });
});

// Group collapse/expand
document.querySelectorAll('.group-header').forEach(header => {
  header.addEventListener('click', () => {
    header.parentElement.classList.toggle('collapsed');
  });
});

// Sidebar toggle
const sidebarEl = document.getElementById('sidebar');
const toggleBtn = document.getElementById('sidebarToggle');
toggleBtn.addEventListener('click', () => {
  sidebarEl.classList.toggle('collapsed');
  toggleBtn.textContent = sidebarEl.classList.contains('collapsed') ? '›' : '‹';
});

/* ═══════════════════════════════════════
   Model card selection
═══════════════════════════════════════ */

document.querySelectorAll('.model-cards').forEach(container => {
  container.querySelectorAll('.model-card').forEach(card => {
    card.addEventListener('click', () => {
      if (card.classList.contains('selected')) {
        card.classList.remove('selected');
      } else {
        container.querySelectorAll('.model-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
      }
    });
  });
});

/* ═══════════════════════════════════════
   Drag-and-drop zones
═══════════════════════════════════════ */

function setupDropZone(zoneId, onFile) {
  const zone = document.getElementById(zoneId);
  if (!zone) return;

  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });

  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));

  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  });

  zone.addEventListener('click', e => {
    // find corresponding file input
    const page = zone.dataset.page;
    const prefix = pagePrefix(page);
    const input = document.getElementById(`${prefix}-file-input`);
    if (input) input.click();
  });
}

function pagePrefix(page) {
  const map = {
    'vocal-separation':  'vs',
    'noise-reduction':   'nr',
    'stem-separation':   'st',
    'speaker-separation':'sp',
    'extract-audio':     'ea',
    'format-conversion': 'fc',
    'pitch-adjustment':  'pa',
    'audio-trim':        'at',
  };
  return map[page] || page;
}

/* ═══════════════════════════════════════
   Generic feature handler factory
═══════════════════════════════════════ */

function makeFeatureHandler({
  prefix,
  dropZoneId,
  uploadBtnId,
  fileInputId,
  processBtnId,
  progressId,
  resultsId,
  resultListId,
  waveformCanvasId,        // optional
  waveformAreaId,          // optional
  placeholderId,           // optional
  durationId,              // optional
  waveformColor,
  onProcess,               // async (fileId) => { endpoint call } returning {taskId}
  accept = 'audio/*',
}) {
  let currentFileId = null;
  let currentPeaks = null;

  const fileInput   = document.getElementById(fileInputId);
  const uploadBtn   = document.getElementById(uploadBtnId);
  const processBtn  = document.getElementById(processBtnId);
  const progressEl  = document.getElementById(progressId);
  const resultsEl   = document.getElementById(resultsId);
  const resultList  = document.getElementById(resultListId);

  function setProgress(show) {
    if (progressEl) progressEl.style.display = show ? 'flex' : 'none';
  }

  function showResults(outputs) {
    resultsEl.style.display = 'block';
    resultList.innerHTML = '';
    outputs.forEach(o => {
      const item = document.createElement('div');
      item.className = 'result-item';
      item.innerHTML = `
        <div class="result-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 18V5l12-2v13"/>
            <circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
          </svg>
        </div>
        <div class="result-info">
          <div class="result-name">${escHtml(o.label)}</div>
          <div class="result-file">${escHtml(o.filename)}</div>
        </div>
        <a class="btn-download" href="${escHtml(o.download_url)}" download>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download
        </a>
      `;
      resultList.appendChild(item);
    });
  }

  async function handleFile(file) {
    try {
      currentFileId = null;
      if (processBtn) processBtn.disabled = true;
      toast(`Uploading ${file.name}…`, 'info');

      const data = await apiUpload(file);
      currentFileId = data.file_id;

      // Waveform
      if (waveformCanvasId && waveformAreaId) {
        const canvas = document.getElementById(waveformCanvasId);
        const area   = document.getElementById(waveformAreaId);
        const ph     = placeholderId ? document.getElementById(placeholderId) : null;
        const durEl  = durationId ? document.getElementById(durationId) : null;

        try {
          const wd = await apiWaveform(currentFileId);
          currentPeaks = wd.peaks;
          if (ph)  ph.style.display  = 'none';
          if (area) area.style.display = 'flex';
          resizeCanvas(canvas);
          drawWaveform(canvas, currentPeaks, waveformColor || '#10b981');
          if (durEl) durEl.textContent = fmtTime(wd.duration);
        } catch (_) { /* non-critical */ }
      }

      if (processBtn) processBtn.disabled = false;
      toast('File ready. Click process to start.', 'success');
    } catch (e) {
      toast(e.message, 'error');
    }
  }

  // File input change
  if (fileInput) {
    fileInput.accept = accept;
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) handleFile(fileInput.files[0]);
    });
  }

  // Upload button
  if (uploadBtn) {
    uploadBtn.addEventListener('click', e => {
      e.stopPropagation();
      if (fileInput) fileInput.click();
    });
  }

  // Drop zone
  setupDropZone(dropZoneId, handleFile);

  // Process button
  if (processBtn) {
    processBtn.addEventListener('click', async () => {
      if (!currentFileId) return;
      setProgress(true);
      if (resultsEl) resultsEl.style.display = 'none';
      try {
        const { taskId } = await onProcess(currentFileId);
        pollTask(
          taskId,
          (d) => {
            setProgress(false);
            if (d.outputs && d.outputs.length) {
              showResults(d.outputs);
              toast('Processing complete!', 'success');
            } else {
              toast('Done, but no output files found.', 'info');
            }
          },
          (err) => {
            setProgress(false);
            toast(`Error: ${err}`, 'error');
          }
        );
      } catch (e) {
        setProgress(false);
        toast(e.message, 'error');
      }
    });
  }
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ═══════════════════════════════════════
   Vocal Separation
═══════════════════════════════════════ */

makeFeatureHandler({
  prefix:          'vs',
  dropZoneId:      'vs-drop-zone',
  uploadBtnId:     'vs-upload-btn',
  fileInputId:     'vs-file-input',
  processBtnId:    'vs-process-btn',
  progressId:      'vs-progress',
  resultsId:       'vs-results',
  resultListId:    'vs-result-list',
  waveformCanvasId:'vs-music-canvas',
  waveformAreaId:  'vs-waveform-area',
  placeholderId:   'vs-placeholder',
  durationId:      'vs-duration',
  waveformColor:   '#10b981',
  accept: 'audio/*,video/*',
  onProcess: async (fileId) => {
    const selected = document.querySelector('#vs-model-cards .model-card.selected');
    const mode = selected ? selected.dataset.mode : 'vocals';
    const r = await fetch('/api/separate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, mode }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    return { taskId: d.task_id };
  },
});

// Draw the voice waveform (mirrored / purple tint) when upload happens
const vsMusicCanvas = document.getElementById('vs-music-canvas');
const vsVoiceCanvas = document.getElementById('vs-voice-canvas');
if (vsMusicCanvas && vsVoiceCanvas) {
  const obs = new MutationObserver(() => {
    if (document.getElementById('vs-waveform-area').style.display !== 'none') {
      resizeCanvas(vsVoiceCanvas);
      // Draw decorative purple waveform
      const ctx = vsVoiceCanvas.getContext('2d');
      ctx.clearRect(0, 0, vsVoiceCanvas.width, vsVoiceCanvas.height);
      const peaks = Array.from({ length: 200 }, () => Math.random() * 0.7 + 0.05);
      drawWaveform(vsVoiceCanvas, peaks, '#a855f7');
    }
  });
  obs.observe(document.getElementById('vs-waveform-area'), { attributes: true });
}

/* ═══════════════════════════════════════
   Noise Reduction
═══════════════════════════════════════ */

makeFeatureHandler({
  prefix:          'nr',
  dropZoneId:      'nr-drop-zone',
  uploadBtnId:     'nr-upload-btn',
  fileInputId:     'nr-file-input',
  processBtnId:    'nr-process-btn',
  progressId:      'nr-progress',
  resultsId:       'nr-results',
  resultListId:    'nr-result-list',
  waveformCanvasId:'nr-canvas',
  waveformAreaId:  'nr-waveform-area',
  placeholderId:   'nr-placeholder',
  durationId:      'nr-duration',
  waveformColor:   '#3b82f6',
  accept: 'audio/*',
  onProcess: async (fileId) => {
    const stationary = document.getElementById('nr-stationary').checked;
    const r = await fetch('/api/denoise', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, stationary }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    return { taskId: d.task_id };
  },
});

/* ═══════════════════════════════════════
   Stem Separation
═══════════════════════════════════════ */

makeFeatureHandler({
  prefix:          'st',
  dropZoneId:      'st-drop-zone',
  uploadBtnId:     'st-upload-btn',
  fileInputId:     'st-file-input',
  processBtnId:    'st-process-btn',
  progressId:      'st-progress',
  resultsId:       'st-results',
  resultListId:    'st-result-list',
  waveformCanvasId:'st-canvas',
  waveformAreaId:  'st-waveform-area',
  placeholderId:   'st-placeholder',
  durationId:      'st-duration',
  waveformColor:   '#f59e0b',
  accept: 'audio/*',
  onProcess: async (fileId) => {
    const r = await fetch('/api/separate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, mode: 'stems' }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    return { taskId: d.task_id };
  },
});

/* ═══════════════════════════════════════
   Speaker Separation
═══════════════════════════════════════ */

makeFeatureHandler({
  prefix:          'sp',
  dropZoneId:      'sp-drop-zone',
  uploadBtnId:     'sp-upload-btn',
  fileInputId:     'sp-file-input',
  processBtnId:    'sp-process-btn',
  progressId:      'sp-progress',
  resultsId:       'sp-results',
  resultListId:    'sp-result-list',
  waveformCanvasId:'sp-canvas',
  waveformAreaId:  'sp-waveform-area',
  placeholderId:   'sp-placeholder',
  durationId:      'sp-duration',
  waveformColor:   '#ec4899',
  accept: 'audio/*',
  onProcess: async (fileId) => {
    const num = parseInt(document.getElementById('sp-num-speakers').value, 10);
    const r = await fetch('/api/speaker-separate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, num_speakers: num }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    return { taskId: d.task_id };
  },
});

/* ═══════════════════════════════════════
   Extract Audio
═══════════════════════════════════════ */

makeFeatureHandler({
  prefix:          'ea',
  dropZoneId:      'ea-drop-zone',
  uploadBtnId:     'ea-upload-btn',
  fileInputId:     'ea-file-input',
  processBtnId:    'ea-process-btn',
  progressId:      'ea-progress',
  resultsId:       'ea-results',
  resultListId:    'ea-result-list',
  waveformColor:   '#10b981',
  accept: 'video/*,audio/*',
  onProcess: async (fileId) => {
    const fmt = document.getElementById('ea-format').value;
    const r = await fetch('/api/extract-audio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, format: fmt }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    return { taskId: d.task_id };
  },
});

/* ═══════════════════════════════════════
   Format Conversion
═══════════════════════════════════════ */

makeFeatureHandler({
  prefix:          'fc',
  dropZoneId:      'fc-drop-zone',
  uploadBtnId:     'fc-upload-btn',
  fileInputId:     'fc-file-input',
  processBtnId:    'fc-process-btn',
  progressId:      'fc-progress',
  resultsId:       'fc-results',
  resultListId:    'fc-result-list',
  waveformColor:   '#10b981',
  accept: 'audio/*',
  onProcess: async (fileId) => {
    const fmt     = document.getElementById('fc-format').value;
    const bitrate = document.getElementById('fc-bitrate').value;
    const r = await fetch('/api/convert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, format: fmt, bitrate }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    return { taskId: d.task_id };
  },
});

/* ═══════════════════════════════════════
   Pitch Adjustment
═══════════════════════════════════════ */

const paSlider  = document.getElementById('pa-semitones');
const paValSpan = document.getElementById('pa-semitones-val');
if (paSlider) {
  paSlider.addEventListener('input', () => {
    paValSpan.textContent = paSlider.value;
  });
}

makeFeatureHandler({
  prefix:          'pa',
  dropZoneId:      'pa-drop-zone',
  uploadBtnId:     'pa-upload-btn',
  fileInputId:     'pa-file-input',
  processBtnId:    'pa-process-btn',
  progressId:      'pa-progress',
  resultsId:       'pa-results',
  resultListId:    'pa-result-list',
  waveformColor:   '#10b981',
  accept: 'audio/*',
  onProcess: async (fileId) => {
    const semitones = parseFloat(document.getElementById('pa-semitones').value);
    const r = await fetch('/api/pitch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, semitones }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    return { taskId: d.task_id };
  },
});

/* ═══════════════════════════════════════
   Audio Trim
═══════════════════════════════════════ */

makeFeatureHandler({
  prefix:          'at',
  dropZoneId:      'at-drop-zone',
  uploadBtnId:     'at-upload-btn',
  fileInputId:     'at-file-input',
  processBtnId:    'at-process-btn',
  progressId:      'at-progress',
  resultsId:       'at-results',
  resultListId:    'at-result-list',
  waveformColor:   '#10b981',
  accept: 'audio/*',
  onProcess: async (fileId) => {
    const start = parseFloat(document.getElementById('at-start').value || 0) * 1000;
    const endVal = document.getElementById('at-end').value;
    const end = endVal ? parseFloat(endVal) * 1000 : null;
    const r = await fetch('/api/trim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, start_ms: start, end_ms: end }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error);
    return { taskId: d.task_id };
  },
});

/* ═══════════════════════════════════════
   Audio Merge
═══════════════════════════════════════ */

(function setupMerge() {
  const addBtn     = document.getElementById('am-add-btn');
  const fileInput  = document.getElementById('am-file-input');
  const processBtn = document.getElementById('am-process-btn');
  const progressEl = document.getElementById('am-progress');
  const resultsEl  = document.getElementById('am-results');
  const resultList = document.getElementById('am-result-list');
  const fileList   = document.getElementById('am-file-list');

  const uploadedFiles = []; // [{id, name}]

  function setProgress(show) {
    if (progressEl) progressEl.style.display = show ? 'flex' : 'none';
  }

  function refreshList() {
    fileList.innerHTML = '';
    if (uploadedFiles.length === 0) {
      fileList.innerHTML = '<p class="merge-hint">Add 2 or more audio files to merge</p>';
    } else {
      uploadedFiles.forEach((f, idx) => {
        const row = document.createElement('div');
        row.className = 'merge-file-row';
        row.innerHTML = `
          <span>${escHtml(f.name)}</span>
          <button class="btn-remove" data-idx="${idx}" aria-label="Remove">✕</button>
        `;
        fileList.appendChild(row);
      });
    }
    if (processBtn) processBtn.disabled = uploadedFiles.length < 2;
  }

  fileList.addEventListener('click', e => {
    const btn = e.target.closest('.btn-remove');
    if (btn) {
      const idx = parseInt(btn.dataset.idx, 10);
      uploadedFiles.splice(idx, 1);
      refreshList();
    }
  });

  async function handleFiles(files) {
    for (const file of files) {
      try {
        toast(`Uploading ${file.name}…`, 'info', 2000);
        const data = await apiUpload(file);
        uploadedFiles.push({ id: data.file_id, name: file.name });
        refreshList();
      } catch (e) {
        toast(e.message, 'error');
      }
    }
  }

  if (addBtn) addBtn.addEventListener('click', () => fileInput && fileInput.click());
  if (fileInput) fileInput.addEventListener('change', () => {
    if (fileInput.files.length) handleFiles(Array.from(fileInput.files));
  });

  if (processBtn) {
    processBtn.addEventListener('click', async () => {
      if (uploadedFiles.length < 2) return;
      setProgress(true);
      if (resultsEl) resultsEl.style.display = 'none';
      try {
        const crossfade = parseInt(document.getElementById('am-crossfade').value || 0, 10);
        const r = await fetch('/api/merge', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_ids: uploadedFiles.map(f => f.id),
            crossfade_ms: crossfade,
          }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.error);
        pollTask(
          d.task_id,
          (res) => {
            setProgress(false);
            if (res.outputs && res.outputs.length) {
              resultsEl.style.display = 'block';
              resultList.innerHTML = '';
              res.outputs.forEach(o => {
                const item = document.createElement('div');
                item.className = 'result-item';
                item.innerHTML = `
                  <div class="result-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M9 18V5l12-2v13"/>
                      <circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
                    </svg>
                  </div>
                  <div class="result-info">
                    <div class="result-name">${escHtml(o.label)}</div>
                    <div class="result-file">${escHtml(o.filename)}</div>
                  </div>
                  <a class="btn-download" href="${escHtml(o.download_url)}" download>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                      <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    Download
                  </a>
                `;
                resultList.appendChild(item);
              });
              toast('Merge complete!', 'success');
            }
          },
          (err) => {
            setProgress(false);
            toast(`Error: ${err}`, 'error');
          }
        );
      } catch (e) {
        setProgress(false);
        toast(e.message, 'error');
      }
    });
  }

  refreshList();
})();

/* ═══════════════════════════════════════
   Resize canvases on window resize
═══════════════════════════════════════ */

window.addEventListener('resize', () => {
  document.querySelectorAll('.waveform-canvas').forEach(c => {
    resizeCanvas(c);
    // Re-draw if we have data (basic — just clears for now; full re-draw
    // would require storing peaks per canvas, handled by waveform update flow)
  });
});
