/* ════════════════════════════════════════════════════════
   FastSave – app.js  |  Full Frontend Logic
   ════════════════════════════════════════════════════════ */

'use strict';

// ── Config ──────────────────────────────────────────────────
// Automatically detect if we are on Netlify or Local network
let API_BASE = '';
if (window.location.hostname.includes('netlify.app') || window.location.hostname.includes('loca.lt')) {
  API_BASE = 'https://wmw-fastsave.loca.lt';
}

// ── State ───────────────────────────────────────────────────
const state = {
  url:           '',
  platform:      '',
  selectedTab:   'video',    // 'video' | 'audio'
  quality:       '1080',
  type:          'mp4',
  audioQuality:  '320',
  videoInfo:     null,
  fetching:      false,
  downloading:   false,
};

// ── DOM refs ─────────────────────────────────────────────────
const $  = (id) => document.getElementById(id);
const $$ = (sel) => document.querySelectorAll(sel);

const videoUrlInput   = $('videoUrl');
const fetchBtn        = $('fetchBtn');
const startDownloadBtn= $('startDownloadBtn');
const progressWrapper = $('progressWrapper');
const progressFill    = $('progressBarFill');
const progressText    = $('progressText');
const toast           = $('toast');

const thumbnailImg    = $('thumbnailImg');
const thumbPlaceholder= $('thumbPlaceholder');
const durationBadge   = $('durationBadge');
const videoTitle      = $('videoTitle');
const videoAuthor     = $('videoAuthor');
const metaPlatform    = $('metaPlatform');
const metaDuration    = $('metaDuration');
const metaQuality     = $('metaQuality');
const metaSize        = $('metaSize');

const progressCircle  = $('progressCircle');
const progressPercent = $('progressPercent');

// ── Theme Toggle ──────────────────────────────────────────────
const themeToggleBtn = $('themeToggle');
const themeIcon = $('themeIcon');

function setTheme(theme) {
  if (theme === 'light') {
    document.body.dataset.theme = 'light';
    themeIcon.innerHTML = `<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>`;
    localStorage.setItem('fastsave-theme', 'light');
  } else {
    delete document.body.dataset.theme;
    themeIcon.innerHTML = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>`;
    localStorage.setItem('fastsave-theme', 'dark');
  }
}

// Init theme
const savedTheme = localStorage.getItem('fastsave-theme');
if (savedTheme === 'light') setTheme('light');

themeToggleBtn.addEventListener('click', () => {
  const current = document.body.dataset.theme === 'light' ? 'light' : 'dark';
  setTheme(current === 'light' ? 'dark' : 'light');
});

// ── Toast ─────────────────────────────────────────────────────
let toastTimer = null;
function showToast(msg, type = 'info', duration = 4000) {
  const icons = {
    success: '✅',
    error:   '❌',
    info:    'ℹ️',
    warning: '⚠️',
  };
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), duration);
}

// ── Platform detection ────────────────────────────────────────
function detectPlatform(url) {
  if (!url) return '';
  const u = url.toLowerCase();
  if (u.includes('youtube.com') || u.includes('youtu.be'))           return 'youtube';
  if (u.includes('tiktok.com'))                                       return 'tiktok';
  if (u.includes('facebook.com') || u.includes('fb.watch') || u.includes('fb.com')) return 'facebook';
  if (u.includes('instagram.com'))                                    return 'instagram';
  return '';
}

function highlightPlatformCard(platform) {
  $$('.platform-card').forEach(card => card.classList.remove('active-card'));
  if (platform) {
    const card = $(`card-${platform}`);
    if (card) card.classList.add('active-card');
  }
}

// ── URL input live detection ───────────────────────────────────
videoUrlInput.addEventListener('input', () => {
  state.url = videoUrlInput.value.trim();
  const p = detectPlatform(state.url);
  if (p !== state.platform) {
    state.platform = p;
    highlightPlatformCard(p);
    if (p) showToast(`${p.charAt(0).toUpperCase() + p.slice(1)} detected automatically!`, 'info', 2500);
  }
});

videoUrlInput.addEventListener('paste', (e) => {
  setTimeout(() => {
    state.url = videoUrlInput.value.trim();
    const p = detectPlatform(state.url);
    state.platform = p;
    highlightPlatformCard(p);
  }, 0);
});

// ── Platform card click → fill input ──────────────────────────
$$('.platform-card').forEach(card => {
  card.addEventListener('click', (e) => {
    e.preventDefault();
    const platform = card.dataset.platform;
    state.platform = platform;
    highlightPlatformCard(platform);
    
    // Auto-scroll to top instantly
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    // Focus after scroll
    setTimeout(() => { videoUrlInput.focus(); }, 300);
    
    showToast(`Paste your ${platform.charAt(0).toUpperCase() + platform.slice(1)} link above!`, 'info', 2500);
  });
});

$$('.platform-card').forEach(card => {
  card.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      card.querySelector('.platform-download-btn')?.click();
    }
  });
});

// ── Format Tabs ───────────────────────────────────────────────
$$('.format-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.dataset.tab;
    state.selectedTab = target;

    $$('.format-tab').forEach(t => {
      t.classList.remove('active');
      t.setAttribute('aria-selected', 'false');
    });
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');

    // Show/hide panels
    $('panel-video').hidden = (target !== 'video');
    $('panel-audio').hidden = (target !== 'audio');

    // Update type based on tab
    if (target === 'audio') {
      state.type = 'mp3';
    } else {
      state.type = 'mp4';
      $$('.type-btn').forEach(b => b.classList.remove('active'));
      $('type-mp4')?.classList.add('active');
    }
    updateMetaQuality();
  });
});

// ── Quality selection ─────────────────────────────────────────
$$('.quality-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const parent = btn.closest('.quality-grid');
    parent.querySelectorAll('.quality-btn').forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-pressed', 'false');
    });
    btn.classList.add('active');
    btn.setAttribute('aria-pressed', 'true');

    if (btn.dataset.quality) {
      state.quality = btn.dataset.quality;
    }
    updateMetaQuality();
  });
});

// ── Type selection ────────────────────────────────────────────
$$('.type-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('.type-btn').forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-pressed', 'false');
    });
    btn.classList.add('active');
    btn.setAttribute('aria-pressed', 'true');
    state.type = btn.dataset.type;
    updateMetaQuality();
  });
});

function updateMetaQuality() {
  if (state.type === 'mp3') {
    metaQuality.textContent = `${state.audioQuality}kbps MP3`;
  } else if (state.type === 'thumbnail') {
    metaQuality.textContent = 'Original';
  } else {
    metaQuality.textContent = state.quality === 'best' ? 'Best Quality' : `${state.quality}p HD`;
  }
}

// ── Fetch video info ──────────────────────────────────────────
fetchBtn.addEventListener('click', fetchVideoInfo);
videoUrlInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') fetchVideoInfo();
});

const clearUrlBtn = $('clearUrlBtn');
if (clearUrlBtn) {
  videoUrlInput.addEventListener('input', () => {
    clearUrlBtn.hidden = videoUrlInput.value.length === 0;
  });

  clearUrlBtn.addEventListener('click', () => {
    videoUrlInput.value = '';
    clearUrlBtn.hidden = true;
    videoUrlInput.focus();
    
    // Reset state & platform highlight
    state.url = '';
    state.platform = '';
    state.videoInfo = null;
    $$('.platform-card').forEach(c => c.classList.remove('active'));

    // Reset Meta Texts
    videoTitle.textContent = 'Ready to Download';
    videoAuthor.textContent = '';
    metaPlatform.textContent = 'Auto-Detect';
    metaDuration.textContent = '—';
    metaSize.textContent = '—';

    // Revert thumbnail to placeholder
    const thumbnailWrapper = document.getElementById('thumbnailWrapper');
    if (thumbnailWrapper) {
      thumbnailWrapper.innerHTML = `
        <img id="thumbnailImg" src="" alt="Video thumbnail" class="thumbnail-img" />
        <div class="thumbnail-placeholder" id="thumbPlaceholder" style="display:flex;">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <rect x="2" y="7" width="20" height="10" rx="2"/>
            <path d="M9.5 10l5 2-5 2V10z" fill="currentColor"/>
          </svg>
          <span>Thumbnail will appear here</span>
        </div>
        <div class="duration-badge" id="durationBadge" hidden></div>
      `;
    }
  });
}

async function fetchVideoInfo() {
  const url = videoUrlInput.value.trim();
  if (!url) {
    showToast('Please paste a video URL first!', 'warning');
    videoUrlInput.focus();
    return;
  }
  if (!isValidURL(url)) {
    showToast('Please enter a valid URL.', 'error');
    return;
  }

  state.url = url;
  state.platform = detectPlatform(url);
  highlightPlatformCard(state.platform);

  // ── Instant Preview Injection ─────────────────────────────────
  // Instantly show thumbnail before backend responds!
  if (state.platform === 'youtube') {
    const ytMatch = url.match(/(?:v=|youtu\.be\/)([^&]+)/);
    if (ytMatch && ytMatch[1]) {
      const videoId = ytMatch[1];
      const thumbnailWrapper = document.getElementById('thumbnailWrapper');
      if (thumbnailWrapper && !document.getElementById('thumbnailImg')) {
         // Revert to image template if previously embedded
         thumbnailWrapper.innerHTML = `
            <img id="thumbnailImg" src="" alt="Video thumbnail" class="thumbnail-img" />
            <div class="thumbnail-placeholder" id="thumbPlaceholder" style="display:none;"></div>
            <div class="duration-badge" id="durationBadge" hidden></div>
         `;
      }
      const tImg = document.getElementById('thumbnailImg');
      const tPlace = document.getElementById('thumbPlaceholder');
      if (tImg) {
        tImg.src = `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;
        tImg.onload = () => { tImg.classList.add('loaded'); };
        if (tPlace) tPlace.style.display = 'none';
      }
      videoTitle.textContent = 'Analyzing video...';
      metaPlatform.textContent = 'YouTube';
    }
  }

  // Show loading state
  state.fetching = true;
  setFetchBtnLoading(true);
  
  if (state.platform !== 'youtube') {
    const tPlace = document.getElementById('thumbPlaceholder');
    if (tPlace) {
      tPlace.innerHTML = `<div class="spinner"></div><span style="margin-top:10px;">Fetching info...</span>`;
      tPlace.style.display = 'flex';
    }
  }

  try {
    const res = await fetch(`${API_BASE}/api/info`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Bypass-Tunnel-Reminder': 'true'
      },
      body: JSON.stringify({ url }),
    });

    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.error || 'Failed to fetch video info');
    }

    state.videoInfo = data;
    renderVideoInfo(data);
    showToast('Video info loaded successfully!', 'success');

    // Auto-scroll to preview section reliably
    setTimeout(() => {
      const previewSection = document.getElementById('options-preview');
      if (previewSection) {
        const yOffset = -50; 
        const y = previewSection.getBoundingClientRect().top + window.scrollY + yOffset;
        window.scrollTo({ top: y, behavior: 'smooth' });
      }
    }, 150);

  } catch (err) {
    console.error(err);
    showToast(err.message || 'Could not reach the server. Is the backend running?', 'error');
    thumbPlaceholder.innerHTML = `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="2" y="7" width="20" height="10" rx="2"/><path d="M9.5 10l5 2-5 2V10z" fill="currentColor"/></svg><span>Thumbnail will appear here</span>`;
  } finally {
    state.fetching = false;
    setFetchBtnLoading(false);
  }
}

function renderVideoInfo(data) {
  const plat = (data.platform || state.platform || '').toLowerCase();
  let embedded = false;
  
  // ── YouTube Embed ───────────────────────────────────────────
  if (plat === 'youtube' && (data.webpage_url || state.url)) {
    const urlStr = data.webpage_url || state.url;
    const ytMatch = urlStr.match(/(?:v=|youtu\.be\/)([^&]+)/);
    if (ytMatch && ytMatch[1]) {
      const videoId = ytMatch[1];
      const thumbnailWrapper = document.getElementById('thumbnailWrapper');
      thumbnailWrapper.innerHTML = `
        <iframe width="100%" height="100%" src="https://www.youtube.com/embed/${videoId}?autoplay=0" 
                title="YouTube video player" frameborder="0" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                allowfullscreen style="border-radius: inherit; display: block;"></iframe>
        <div class="duration-badge" id="durationBadge" hidden></div>
      `;
      // Re-query duration badge
      const newDurationBadge = document.getElementById('durationBadge');
      if (data.duration) {
        newDurationBadge.textContent = formatDuration(data.duration);
        newDurationBadge.hidden = false;
      }
      embedded = true;
    }
  }

  // ── Standard Image Thumbnail ────────────────────────────────
  if (!embedded) {
    const thumbnailWrapper = document.getElementById('thumbnailWrapper');
    if (!document.getElementById('thumbnailImg')) {
      // Revert to image template if previously embedded
      thumbnailWrapper.innerHTML = `
        <img id="thumbnailImg" src="" alt="Video thumbnail" class="thumbnail-img" />
        <div class="thumbnail-placeholder" id="thumbPlaceholder">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <rect x="2" y="7" width="20" height="10" rx="2"/>
            <path d="M9.5 10l5 2-5 2V10z" fill="currentColor"/>
          </svg>
          <span>Thumbnail will appear here</span>
        </div>
        <div class="duration-badge" id="durationBadge" hidden></div>
      `;
    }
    const tImg = document.getElementById('thumbnailImg');
    const tPlace = document.getElementById('thumbPlaceholder');
    const dBadge = document.getElementById('durationBadge');

    if (data.thumbnail) {
      tImg.src = data.thumbnail;
      tImg.onload = () => {
        tImg.classList.add('loaded');
        tPlace.style.display = 'none';
      };
      tImg.onerror = () => {
        tImg.classList.remove('loaded');
        tPlace.style.display = 'flex';
      };
    }
    if (data.duration) {
      dBadge.textContent = formatDuration(data.duration);
      dBadge.hidden = false;
    }
  }

  // Meta
  videoTitle.textContent  = data.title  || 'Unknown Title';
  videoAuthor.textContent = data.uploader ? `by ${data.uploader}` : '';
  metaPlatform.textContent = platformLabel(data.platform || state.platform);
  metaDuration.textContent = data.duration ? formatDuration(data.duration) : '—';
  metaSize.textContent     = data.filesize ? formatSize(data.filesize) : 'N/A';

  // Style platform color
  const pColors = { youtube:'#ef4444', tiktok:'#64d2c8', facebook:'#6baeff', instagram:'#d87bb9' };
  metaPlatform.style.color = pColors[plat] || '#ef4444';

  updateMetaQuality();
}

// ── Start Download ────────────────────────────────────────────
startDownloadBtn.addEventListener('click', startDownload);

function updateCircularProgress(percent) {
  const offset = 163.36 - (percent / 100) * 163.36;
  if (progressCircle) progressCircle.style.strokeDashoffset = offset;
  if (progressPercent) progressPercent.textContent = Math.round(percent) + '%';
}

async function startDownload() {
  const url = videoUrlInput.value.trim();
  if (!url) {
    showToast('Please paste a video URL first!', 'warning');
    return;
  }
  if (!isValidURL(url)) {
    showToast('Please enter a valid URL.', 'error');
    return;
  }

  state.url = url;
  state.downloading = true;
  startDownloadBtn.disabled = true;
  startDownloadBtn.innerHTML = `<div class="spinner"></div> Preparing...`;

  progressWrapper.hidden = false;
  updateCircularProgress(0);
  progressText.textContent = 'Starting download...';

  let params = { url };
  if (state.type === 'thumbnail') {
    params.type = 'thumbnail';
  } else if (state.type === 'mp3' || state.selectedTab === 'audio') {
    params.type = 'mp3';
    params.quality = state.audioQuality;
  } else {
    params.type = 'mp4';
    params.quality = state.quality;
  }

  try {
    // 1. Start download task
    const startRes = await fetch(`${API_BASE}/api/start-download`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Bypass-Tunnel-Reminder': 'true'
      },
      body: JSON.stringify(params),
    });
    
    if (!startRes.ok) {
      const errData = await startRes.json().catch(()=>({error:'Server error'}));
      throw new Error(errData.error || `HTTP ${startRes.status}`);
    }
    const { task_id } = await startRes.json();
    
    // 2. Poll for progress
    progressText.textContent = 'Downloading...';
    let completed = false;
    
    while (!completed) {
      await new Promise(r => setTimeout(r, 500));
      const progRes = await fetch(`${API_BASE || window.location.origin}/api/progress/${task_id}`, {
        headers: { 'Bypass-Tunnel-Reminder': 'true' }
      });
      if (!progRes.ok) throw new Error('Progress polling failed');
      const stateData = await progRes.json();
      
      if (stateData.status === 'error') {
        throw new Error(stateData.error || 'Download failed on server');
      }
      
      if (stateData.status === 'downloading') {
        // If external (Netlify), backend is 50% of the work. If local, it's 100%
        const visualPercent = API_BASE ? (stateData.percent / 2) : stateData.percent;
        updateCircularProgress(visualPercent);
      }
      
      if (stateData.status === 'completed') {
        const finalPercent = API_BASE ? 50 : 100;
        updateCircularProgress(finalPercent);
        completed = true;
      }
    }

    // 3. Trigger actual file download
    const downloadUrl = `${API_BASE || window.location.origin}/api/download-file/${task_id}`;
    
    if (API_BASE) {
      // Netlify: Transfer file from laptop to mobile through tunnel
      progressText.textContent = 'Transferring to Gallery...';
      
      const fileRes = await fetch(downloadUrl, {
        headers: { 'Bypass-Tunnel-Reminder': 'true' }
      });
      
      if (!fileRes.ok) throw new Error('File transfer failed');
      
      const contentLength = fileRes.headers.get('content-length');
      const total = contentLength ? parseInt(contentLength, 10) : 0;
      let loaded = 0;
      
      // Read stream for progress
      const reader = fileRes.body.getReader();
      const chunks = [];
      
      while(true) {
        const {done, value} = await reader.read();
        if (done) break;
        chunks.push(value);
        loaded += value.length;
        if (total > 0) {
          const blobPercent = (loaded / total) * 100;
          updateCircularProgress(50 + (blobPercent / 2)); // 50% to 100%
        }
      }
      
      updateCircularProgress(100);
      progressText.textContent = 'Done! Saving file...';
      
      const blob = new Blob(chunks);
      const urlBlob = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = urlBlob;
      
      let filename = 'downloaded_media.' + (state.type || 'mp4');
      const cd = fileRes.headers.get('Content-Disposition');
      if (cd && cd.includes('filename=')) {
          const matches = cd.match(/filename="?([^"]+)"?/);
          if (matches && matches[1]) filename = matches[1];
      }
      
      a.download = filename;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(urlBlob);
      
    } else {
      // Local network - native ultra-fast download
      progressText.textContent = 'Done! Saving file...';
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }

    showToast('Download completed successfully! 🎉', 'success');

    setTimeout(() => {
      progressWrapper.hidden = true;
      updateCircularProgress(0);
      progressText.textContent = 'Starting download...';
    }, 3000);

  } catch (err) {
    console.error(err);
    showToast(err.message || 'Download failed. Is the backend running?', 'error');
    progressWrapper.hidden = true;
    updateCircularProgress(0);
  } finally {
    state.downloading = false;
    startDownloadBtn.disabled = false;
    startDownloadBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Start Download`;
  }
}

// ── Fetch button loading state ────────────────────────────────
function setFetchBtnLoading(loading) {
  if (loading) {
    fetchBtn.innerHTML = `<div class="spinner"></div> Fetching...`;
    fetchBtn.disabled = true;
  } else {
    fetchBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download`;
    fetchBtn.disabled = false;
  }
}

// ── Navbar ────────────────────────────────────────────────────
const hamburger = $('hamburger');
const navMenu   = $('navMenu');

hamburger?.addEventListener('click', () => {
  navMenu?.classList.toggle('open');
  hamburger?.classList.toggle('open');
});

// Close menu when clicking a link
document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', () => {
    navMenu?.classList.remove('open');
    hamburger?.classList.remove('open');
  });
});

// Lang selector
const langSelector  = $('langSelector');
const langDropdown  = $('langDropdown');
const langSpan      = langSelector?.querySelector('span');

langSelector?.addEventListener('click', (e) => {
  e.stopPropagation();
  langSelector.classList.toggle('open');
});
langDropdown?.querySelectorAll('li').forEach(li => {
  li.addEventListener('click', () => {
    if (langSpan) langSpan.textContent = li.dataset.lang;
    langSelector.classList.remove('open');
  });
});

document.addEventListener('click', () => {
  langSelector?.classList.remove('open');
  navLinks?.classList.remove('open');
});

// Theme toggle (cosmetic – already dark)
const themeToggle = $('themeToggle');
themeToggle?.addEventListener('click', () => {
  showToast('Dark mode is optimal for this app!', 'info', 2000);
});

// ── Nav links smooth scroll ───────────────────────────────────
$$('.nav-link').forEach(link => {
  link.addEventListener('click', function (e) {
    $$('.nav-link').forEach(l => l.classList.remove('active'));
    this.classList.add('active');
    navLinks.classList.remove('open');
  });
});

// ── Helpers ───────────────────────────────────────────────────
function isValidURL(url) {
  try { new URL(url); return true; } catch { return false; }
}

function formatDuration(seconds) {
  if (!seconds || isNaN(seconds)) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${pad(m)}:${pad(s)}`;
  return `${pad(m)}:${pad(s)}`;
}

function pad(n) { return String(n).padStart(2, '0'); }

function formatSize(bytes) {
  if (!bytes) return 'N/A';
  const gb = bytes / 1e9;
  const mb = bytes / 1e6;
  if (gb >= 1) return gb.toFixed(1) + ' GB';
  return mb.toFixed(1) + ' MB';
}

function platformLabel(p) {
  const labels = { youtube:'YouTube', tiktok:'TikTok', facebook:'Facebook', instagram:'Instagram' };
  return labels[p?.toLowerCase()] || (p || '—');
}

function extractFilename(contentDisp) {
  const match = contentDisp.match(/filename[^;=\n]*=['"]?([^'";\n]+)['"]?/i);
  return match ? decodeURIComponent(match[1].trim()) : null;
}

function guessFilename(type) {
  const ts = Date.now();
  if (type === 'mp3')       return `fastsave_audio_${ts}.mp3`;
  if (type === 'thumbnail') return `fastsave_thumb_${ts}.jpg`;
  return `fastsave_video_${ts}.mp4`;
}
