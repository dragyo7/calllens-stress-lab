/**
 * CallLens — Speech Intelligence & Telephony Evaluation Platform
 * Frontend Application Engine
 *
 * Capabilities:
 * - STT Studio: Upload, live microphone, preloaded clips, format/model selector, download transcript.
 * - TTS Studio: 42 Timbre voices, speed control, templates, audio player, WAV download.
 * - Live Playground: WebSocket gateway, binary audio chunk streaming, lifecycle event logging.
 * - Telephony Stress Lab: ITU-T G.712 degradation, 360 live benchmark replays, BFSI extraction.
 * - Model Comparison: Head-to-head empirical metrics, bootstrap confidence intervals, CER.
 * - Audio History: SQLite audit trail of all speech operations.
 * - Command Palette (⌘K) and keyboard navigation [1] to [9].
 */

document.addEventListener('DOMContentLoaded', () => {
  // Global DOM elements
  const sidebar = document.getElementById('app-sidebar');
  const mobileToggleBtn = document.getElementById('mobile-toggle-btn');
  const breadcrumbTitle = document.getElementById('breadcrumb-title');
  const cmdBackdrop = document.getElementById('cmd-palette-backdrop');
  const cmdTriggerBtn = document.getElementById('cmd-trigger-btn');
  const cmdInput = document.getElementById('cmd-input');
  const toastContainer = document.getElementById('toast-container');

  // Stress Lab Form & Replay elements
  const stressForm = document.getElementById('stress-form');
  const clipSelect = document.getElementById('clip-select');
  const audioFileInput = document.getElementById('audio-file');
  const btnSubmit = document.getElementById('btn-submit');
  const loader = document.getElementById('loader');
  const errorBanner = document.getElementById('error-banner');
  const referenceCard = document.getElementById('reference-card');
  const refText = document.getElementById('ref-text');
  const refClipMeta = document.getElementById('ref-clip-meta');
  const gtEntities = document.getElementById('gt-entities');
  const gtAmtTag = document.getElementById('gt-amt-tag');
  const gtDayTag = document.getElementById('gt-day-tag');
  const resultsSection = document.getElementById('results-section');
  const clipAudioPlayer = document.getElementById('clip-audio-player');

  // Active state
  let currentView = 'overview';
  let chartInstances = {};
  let benchmarkClipsList = [];

  // View titles map (10 views)
  const viewTitles = {
    overview: 'Overview',
    'stt-studio': 'Speech-to-Text Studio',
    'tts-studio': 'Text-to-Speech Studio',
    'live-playground': 'Live Speech Playground',
    'followup-desk': 'Follow-up Desk',
    comparison: 'Model Comparison',
    'stress-lab': 'Telephony Stress Lab',
    history: 'Audio Audit History',
    diagnostics: 'Failures & Diagnostics',
    methodology: 'Methodology & Provenance',
  };

  // Toast notification system
  window.showToast = function(message, type = 'info') {
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 250);
    }, 3200);
  };

  // Copy text to clipboard
  window.copyText = function(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    navigator.clipboard.writeText(el.textContent).then(() => {
      window.showToast('Transcript copied to clipboard', 'success');
    }).catch(() => {
      window.showToast('Failed to copy text', 'error');
    });
  };

  // Switch View Function
  window.switchView = function(viewId) {
    if (!viewTitles[viewId]) return;
    currentView = viewId;

    // Update view panels
    document.querySelectorAll('.view-panel').forEach(panel => {
      panel.classList.add('hidden');
    });
    const targetPanel = document.getElementById(`view-${viewId}`);
    if (targetPanel) {
      targetPanel.classList.remove('hidden');
    }

    // Update sidebar nav items
    document.querySelectorAll('.nav-item').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-view') === viewId);
    });

    // Update breadcrumb
    if (breadcrumbTitle) {
      breadcrumbTitle.textContent = viewTitles[viewId];
    }

    // Close mobile drawer if open
    if (sidebar && sidebar.classList.contains('mobile-open')) {
      sidebar.classList.remove('mobile-open');
    }

    // Trigger chart resize if needed
    window.dispatchEvent(new Event('resize'));
    window.location.hash = viewId;

    if (viewId === 'history') {
      loadHistory();
    }
    if (viewId === 'followup-desk') {
      initFollowupDesk();
    }
  };

  // Sidebar navigation click listeners
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.getAttribute('data-view');
      window.switchView(view);
    });
  });

  // Mobile menu toggle
  if (mobileToggleBtn) {
    mobileToggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
    });
  }

  // Keyboard navigation shortcuts ([1] to [0], ⌘K, Escape)
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {
      if (e.key === 'Escape' && cmdBackdrop && !cmdBackdrop.classList.contains('hidden')) {
        closeCommandPalette();
      }
      return;
    }

    if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      openCommandPalette();
      return;
    }

    if (e.key === '/') {
      e.preventDefault();
      openCommandPalette();
      return;
    }

    if (e.key === 'Escape') {
      closeCommandPalette();
      return;
    }

    const keyNumberMap = {
      '1': 'overview',
      '2': 'stt-studio',
      '3': 'tts-studio',
      '4': 'live-playground',
      '5': 'followup-desk',
      '6': 'comparison',
      '7': 'stress-lab',
      '8': 'history',
      '9': 'diagnostics',
      '0': 'methodology',
    };

    if (keyNumberMap[e.key]) {
      window.switchView(keyNumberMap[e.key]);
    }
  });

  // Command palette controller
  function openCommandPalette() {
    if (!cmdBackdrop) return;
    cmdBackdrop.classList.remove('hidden');
    if (cmdInput) {
      cmdInput.value = '';
      cmdInput.focus();
    }
  }

  function closeCommandPalette() {
    if (!cmdBackdrop) return;
    cmdBackdrop.classList.add('hidden');
  }

  if (cmdTriggerBtn) {
    cmdTriggerBtn.addEventListener('click', openCommandPalette);
  }

  if (cmdBackdrop) {
    cmdBackdrop.addEventListener('click', (e) => {
      if (e.target === cmdBackdrop) {
        closeCommandPalette();
      }
    });
  }

  document.querySelectorAll('.cmd-item').forEach(item => {
    item.addEventListener('click', () => {
      const target = item.getAttribute('data-target');
      if (target) {
        window.switchView(target);
        closeCommandPalette();
      }
    });
  });

  if (cmdInput) {
    cmdInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase().trim();
      document.querySelectorAll('.cmd-item').forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(q) ? 'flex' : 'none';
      });
    });
  }

  // Initialize view from URL hash if present
  if (window.location.hash) {
    const initialView = window.location.hash.replace('#', '');
    if (viewTitles[initialView]) {
      window.switchView(initialView);
    }
  }

  // Error banners for Stress Lab
  function showError(msg, isNotice = false) {
    if (errorBanner) {
      errorBanner.textContent = msg;
      if (isNotice || msg.toLowerCase().includes('no live results')) {
        errorBanner.className = 'notice-banner';
      } else {
        errorBanner.className = 'error-banner';
      }
      errorBanner.classList.remove('hidden');
    } else {
      window.showToast(msg, 'error');
    }
  }

  function hideError() {
    if (errorBanner) {
      errorBanner.classList.add('hidden');
      errorBanner.textContent = '';
    }
  }

  // =========================================================================
  // 1. SPEECH-TO-TEXT (STT) STUDIO
  // =========================================================================
  let currentSttMode = 'upload';
  let sttMediaRecorder = null;
  let sttAudioChunks = [];
  let sttRecordedBlob = null;
  let sttTimerInterval = null;
  let sttStartTime = null;
  let sttAudioCtx = null;
  let sttAnalyser = null;
  let sttAnimationId = null;

  // Mode switching tabs
  const sttTabUpload = document.getElementById('stt-tab-upload');
  const sttTabMic = document.getElementById('stt-tab-mic');
  const sttTabClip = document.getElementById('stt-tab-clip');
  const sttModeUpload = document.getElementById('stt-mode-upload');
  const sttModeMic = document.getElementById('stt-mode-mic');
  const sttModeClip = document.getElementById('stt-mode-clip');

  function setSttMode(mode) {
    currentSttMode = mode;
    [sttTabUpload, sttTabMic, sttTabClip].forEach(t => t && t.classList.remove('active'));
    [sttModeUpload, sttModeMic, sttModeClip].forEach(m => m && m.classList.add('hidden'));

    if (mode === 'upload') {
      if (sttTabUpload) sttTabUpload.classList.add('active');
      if (sttModeUpload) sttModeUpload.classList.remove('hidden');
    } else if (mode === 'mic') {
      if (sttTabMic) sttTabMic.classList.add('active');
      if (sttModeMic) sttModeMic.classList.remove('hidden');
    } else if (mode === 'clip') {
      if (sttTabClip) sttTabClip.classList.add('active');
      if (sttModeClip) sttModeClip.classList.remove('hidden');
    }
  }

  if (sttTabUpload) sttTabUpload.addEventListener('click', () => setSttMode('upload'));
  if (sttTabMic) sttTabMic.addEventListener('click', () => setSttMode('mic'));
  if (sttTabClip) sttTabClip.addEventListener('click', () => setSttMode('clip'));

  // Drag and drop for STT file upload
  const sttDropZone = document.getElementById('stt-drop-zone');
  const sttFileInput = document.getElementById('stt-file-input');

  if (sttDropZone && sttFileInput) {
    ['dragenter', 'dragover'].forEach(eventName => {
      sttDropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        sttDropZone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      sttDropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        sttDropZone.classList.remove('drag-over');
      });
    });

    sttDropZone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files && files.length > 0) {
        sttFileInput.files = files;
        updateDropZoneLabel(files[0].name);
      }
    });

    sttFileInput.addEventListener('change', () => {
      if (sttFileInput.files && sttFileInput.files.length > 0) {
        updateDropZoneLabel(sttFileInput.files[0].name);
      }
    });
  }

  function updateDropZoneLabel(fileName) {
    const prompt = sttDropZone.querySelector('.drop-zone-prompt span');
    if (prompt) {
      prompt.textContent = `Selected: ${fileName}`;
    }
  }

  // Waveform Drawer Helper
  function startWaveformVisualization(stream, canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
      const animId = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      ctx.fillStyle = '#08090d';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const barWidth = (canvas.width / bufferLength) * 2.2;
      let barHeight;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        barHeight = (dataArray[i] / 255) * canvas.height * 0.9;
        ctx.fillStyle = `rgba(99, 102, 241, ${0.4 + (dataArray[i] / 255) * 0.6})`;
        ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
        x += barWidth + 1;
      }
      return animId;
    }

    const animId = draw();
    return { audioCtx, analyser, animId };
  }

  // STT Microphone Recording
  const sttBtnMicToggle = document.getElementById('stt-btn-mic-toggle');
  const sttMicStatusText = document.getElementById('stt-mic-status-text');
  const sttMicTimer = document.getElementById('stt-mic-timer');
  const sttMicPreviewBox = document.getElementById('stt-mic-preview-box');
  const sttMicAudioPreview = document.getElementById('stt-mic-audio-preview');

  if (sttBtnMicToggle) {
    sttBtnMicToggle.addEventListener('click', async () => {
      if (sttMediaRecorder && sttMediaRecorder.state === 'recording') {
        // Stop recording
        sttMediaRecorder.stop();
        sttBtnMicToggle.classList.remove('recording');
        if (sttMicStatusText) sttMicStatusText.textContent = 'Record Again';
        clearInterval(sttTimerInterval);
        if (sttAnimationId) cancelAnimationFrame(sttAnimationId);
        if (sttAudioCtx) sttAudioCtx.close();
      } else {
        // Start recording
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          sttAudioChunks = [];
          sttMediaRecorder = new MediaRecorder(stream);

          const wf = startWaveformVisualization(stream, 'stt-mic-canvas');
          if (wf) {
            sttAudioCtx = wf.audioCtx;
            sttAnalyser = wf.analyser;
            sttAnimationId = wf.animId;
          }

          sttMediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) sttAudioChunks.push(e.data);
          };

          sttMediaRecorder.onstop = () => {
            stream.getTracks().forEach(track => track.stop());
            sttRecordedBlob = new Blob(sttAudioChunks, { type: 'audio/wav' });
            if (sttMicAudioPreview) {
              sttMicAudioPreview.src = URL.createObjectURL(sttRecordedBlob);
              if (sttMicPreviewBox) sttMicPreviewBox.classList.remove('hidden');
            }
          };

          sttMediaRecorder.start();
          sttBtnMicToggle.classList.add('recording');
          if (sttMicStatusText) sttMicStatusText.textContent = 'Stop Recording';
          sttStartTime = Date.now();
          sttTimerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - sttStartTime) / 1000);
            const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const secs = String(elapsed % 60).padStart(2, '0');
            if (sttMicTimer) sttMicTimer.textContent = `${mins}:${secs}`;
          }, 500);
        } catch (err) {
          console.error('Microphone access denied:', err);
          window.showToast('Microphone access error: ' + err.message, 'error');
        }
      }
    });
  }

  // STT Form Submission
  const sttStudioForm = document.getElementById('stt-studio-form');
  const sttBtnSubmit = document.getElementById('stt-btn-submit');
  const sttLoader = document.getElementById('stt-loader');
  const sttOutputCard = document.getElementById('stt-output-card');
  const sttOutputText = document.getElementById('stt-output-text');
  const sttOutputMeta = document.getElementById('stt-output-meta');
  const sttBtnDownloadTxt = document.getElementById('stt-btn-download-txt');

  if (sttStudioForm) {
    sttStudioForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const model = document.getElementById('stt-model-select')?.value || 'prisma-v2.5';
      const lang = document.getElementById('stt-lang-select')?.value || 'hi-IN';
      const format = document.getElementById('stt-format-select')?.value || 'verbatim';

      sttBtnSubmit.disabled = true;
      if (sttLoader) sttLoader.classList.remove('hidden');

      try {
        let payload = {
          model: model,
          lang: lang,
          format: format,
          live: 0,
        };

        if (currentSttMode === 'upload') {
          if (!sttFileInput.files || sttFileInput.files.length === 0) {
            window.showToast('Please select an audio file to transcribe.', 'error');
            sttBtnSubmit.disabled = false;
            if (sttLoader) sttLoader.classList.add('hidden');
            return;
          }
          const file = sttFileInput.files[0];
          const arrayBuf = await file.arrayBuffer();
          payload.audio_base64 = btoa(
            new Uint8Array(arrayBuf).reduce((d, byte) => d + String.fromCharCode(byte), '')
          );
        } else if (currentSttMode === 'mic') {
          if (!sttRecordedBlob) {
            window.showToast('Please record audio first before transcribing.', 'error');
            sttBtnSubmit.disabled = false;
            if (sttLoader) sttLoader.classList.add('hidden');
            return;
          }
          const arrayBuf = await sttRecordedBlob.arrayBuffer();
          payload.audio_base64 = btoa(
            new Uint8Array(arrayBuf).reduce((d, byte) => d + String.fromCharCode(byte), '')
          );
        } else if (currentSttMode === 'clip') {
          const clipId = document.getElementById('stt-clip-select')?.value;
          if (!clipId) {
            window.showToast('Please choose a preloaded clip.', 'error');
            sttBtnSubmit.disabled = false;
            if (sttLoader) sttLoader.classList.add('hidden');
            return;
          }
          payload.clip_id = clipId;
        }

        const res = await fetch('/api/stt/transcribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const errData = await res.json();
          window.showToast(`Transcription error: ${errData.detail || 'Failed'}`, 'error');
          return;
        }

        const data = await res.json();
        // Display output
        if (sttOutputCard) sttOutputCard.classList.remove('hidden');
        if (sttOutputText) sttOutputText.textContent = data.transcript || '(No speech detected)';
        if (sttOutputMeta) sttOutputMeta.textContent = `${data.model} • ${data.lang} • Format: ${data.format}`;

        document.getElementById('stt-stat-model').textContent = data.model;
        document.getElementById('stt-stat-lat').textContent = `${data.latency_sec.toFixed(3)}s`;
        document.getElementById('stt-stat-words').textContent = data.word_count;
        document.getElementById('stt-stat-dur').textContent = `${data.audio_duration_sec.toFixed(2)}s`;

        if (sttBtnDownloadTxt) {
          sttBtnDownloadTxt.onclick = () => {
            const blob = new Blob([data.transcript], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `transcript_${data.model}_${Date.now()}.txt`;
            a.click();
            URL.revokeObjectURL(url);
          };
        }

        window.showToast('Transcription completed successfully', 'success');
        sttOutputCard.scrollIntoView({ behavior: 'smooth' });
      } catch (err) {
        window.showToast('Network error during transcription: ' + err.message, 'error');
      } finally {
        sttBtnSubmit.disabled = false;
        if (sttLoader) sttLoader.classList.add('hidden');
      }
    });
  }

  // =========================================================================
  // 2. TEXT-TO-SPEECH (TTS) STUDIO
  // =========================================================================
  const ttsStudioForm = document.getElementById('tts-studio-form');
  const ttsTextInput = document.getElementById('tts-text-input');
  const ttsCharCounter = document.getElementById('tts-char-counter');
  const ttsSpeedSlider = document.getElementById('tts-speed-slider');
  const ttsSpeedVal = document.getElementById('tts-speed-val');
  const ttsBtnSubmit = document.getElementById('tts-btn-submit');
  const ttsLoader = document.getElementById('tts-loader');
  const ttsOutputCard = document.getElementById('tts-output-card');
  const ttsAudioPlayer = document.getElementById('tts-audio-player');
  const ttsBtnDownloadWav = document.getElementById('tts-btn-download-wav');

  // Quick Template Buttons
  document.querySelectorAll('.btn-template').forEach(btn => {
    btn.addEventListener('click', () => {
      const text = btn.getAttribute('data-text');
      if (text && ttsTextInput) {
        ttsTextInput.value = text;
        updateTtsCharCounter();
      }
    });
  });

  function updateTtsCharCounter() {
    if (!ttsTextInput || !ttsCharCounter) return;
    const len = ttsTextInput.value.length;
    ttsCharCounter.textContent = `${len.toLocaleString()} / 2,000 chars`;
    if (len > 2000) {
      ttsCharCounter.style.color = '#f43f5e';
    } else {
      ttsCharCounter.style.color = '#8492a6';
    }
  }

  if (ttsTextInput) {
    ttsTextInput.addEventListener('input', updateTtsCharCounter);
  }

  if (ttsSpeedSlider && ttsSpeedVal) {
    ttsSpeedSlider.addEventListener('input', () => {
      ttsSpeedVal.textContent = `${parseFloat(ttsSpeedSlider.value).toFixed(2)}x`;
    });
  }

  // Populate Voices from catalog API
  fetch('/api/tts/voices')
    .then(r => r.json())
    .then(data => {
      const voiceSelect = document.getElementById('tts-voice-select');
      if (data.voices && voiceSelect) {
        voiceSelect.innerHTML = '';
        data.voices.forEach(v => {
          const opt = document.createElement('option');
          opt.value = v.voice;
          opt.textContent = `${v.voice} (${v.gender} • ${v.lang} ${v.is_recommended ? '• Recommended' : ''})`;
          if (v.voice === 'Pranav') opt.selected = true;
          voiceSelect.appendChild(opt);
        });
      }
    })
    .catch(err => console.warn('Could not load voice catalog:', err));

  // TTS Form Submission
  if (ttsStudioForm) {
    ttsStudioForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = ttsTextInput?.value.trim();
      if (!text) {
        window.showToast('Please enter text to synthesize.', 'error');
        return;
      }
      if (text.length > 2000) {
        window.showToast('Text exceeds 2,000 character maximum limit.', 'error');
        return;
      }

      const voice = document.getElementById('tts-voice-select')?.value || 'Pranav';
      const speed = parseFloat(ttsSpeedSlider?.value || '1.0');

      ttsBtnSubmit.disabled = true;
      if (ttsLoader) ttsLoader.classList.remove('hidden');

      try {
        const res = await fetch('/api/tts/synthesize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: text,
            voice: voice,
            speed: speed,
            format: 'wav',
          }),
        });

        if (!res.ok) {
          const errData = await res.json();
          window.showToast(`Synthesis error: ${errData.detail || 'Failed'}`, 'error');
          return;
        }

        const data = await res.json();
        if (ttsOutputCard) ttsOutputCard.classList.remove('hidden');

        document.getElementById('tts-stat-voice').textContent = data.voice;
        document.getElementById('tts-stat-dur').textContent = `${data.audio_duration_sec.toFixed(2)}s`;
        document.getElementById('tts-stat-lat').textContent = `${data.latency_sec.toFixed(3)}s`;
        document.getElementById('tts-stat-chars').textContent = data.character_count;

        if (ttsAudioPlayer) {
          ttsAudioPlayer.src = data.audio_url;
          ttsAudioPlayer.load();
          ttsAudioPlayer.play().catch(() => {});
        }

        if (ttsBtnDownloadWav) {
          ttsBtnDownloadWav.href = data.audio_url;
          ttsBtnDownloadWav.download = `timbre_${data.voice}_${Date.now()}.wav`;
        }

        window.showToast('Speech synthesized successfully with Timbre', 'success');
        ttsOutputCard.scrollIntoView({ behavior: 'smooth' });
      } catch (err) {
        window.showToast('Synthesis network error: ' + err.message, 'error');
      } finally {
        ttsBtnSubmit.disabled = false;
        if (ttsLoader) ttsLoader.classList.add('hidden');
      }
    });
  }

  // =========================================================================
  // 3. LIVE PLAYGROUND (WEBSOCKET & MIC)
  // =========================================================================
  let speechSocket = null;
  let liveMediaRecorder = null;
  let liveAudioCtx = null;
  let liveAnalyser = null;
  let liveAnimationId = null;
  let liveStartTime = null;
  let liveTimerInterval = null;
  let liveTotalBytes = 0;

  const liveBtnRecord = document.getElementById('live-btn-record');
  const liveRecordStatus = document.getElementById('live-record-status');
  const liveMicTimer = document.getElementById('live-mic-timer');
  const liveBufferBytes = document.getElementById('live-buffer-bytes');
  const liveEventsTerminal = document.getElementById('live-events-terminal');
  const liveTranscriptBox = document.getElementById('live-transcript-box');
  const liveAudioPlayer = document.getElementById('live-audio-player');
  const liveBtnClearEvents = document.getElementById('live-btn-clear-events');
  const wsStatusBadge = document.getElementById('ws-status-badge');

  function appendTerminalLog(msg, color = null) {
    if (!liveEventsTerminal) return;
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');
    const line = document.createElement('div');
    line.className = 'terminal-line';
    line.innerHTML = `<span class="term-time">[${timeStr}]</span> ${color ? `<span style="color:${color};">${msg}</span>` : msg}`;
    liveEventsTerminal.appendChild(line);
    liveEventsTerminal.scrollTop = liveEventsTerminal.scrollHeight;
  }

  if (liveBtnClearEvents) {
    liveBtnClearEvents.addEventListener('click', () => {
      if (liveEventsTerminal) {
        liveEventsTerminal.innerHTML = '<div class="terminal-line"><span class="term-time">[System]</span> Terminal log cleared.</div>';
      }
    });
  }

  function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/speech`;

    try {
      speechSocket = new WebSocket(wsUrl);

      speechSocket.onopen = () => {
        if (wsStatusBadge) {
          wsStatusBadge.className = 'status-pill status-live';
          wsStatusBadge.innerHTML = '<span class="status-dot"></span> WebSocket Connected';
        }
        appendTerminalLog('WebSocket connected to /ws/speech gateway', '#10b981');
      };

      speechSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const evType = data.type;

          if (evType === 'session_started') {
            appendTerminalLog(`Session started (ID: ${data.session_id})`, '#38bdf8');
          } else if (evType === 'session_configured') {
            appendTerminalLog(`Engine configured: ${data.model} (${data.lang})`, '#cbd5e1');
          } else if (evType === 'audio_chunk_received') {
            if (liveBufferBytes) liveBufferBytes.textContent = `${Math.round(data.total_bytes / 1024)} KB`;
          } else if (evType === 'transcription_started') {
            appendTerminalLog(`Transcribing buffered audio (${(data.bytes / 1024).toFixed(1)} KB)...`, '#f59e0b');
          } else if (evType === 'transcription_completed') {
            appendTerminalLog(`Transcription complete in ${(data.latency_sec * 1000).toFixed(0)}ms: "${data.transcript}"`, '#10b981');
            if (liveTranscriptBox) {
              liveTranscriptBox.textContent = data.transcript || '(No speech detected)';
            }
          } else if (evType === 'tts_generation_started') {
            appendTerminalLog(`Synthesizing feedback speech with voice "${data.voice}"...`, '#a855f7');
          } else if (evType === 'tts_audio_ready') {
            appendTerminalLog(`Feedback audio ready: ${data.audio_url}`, '#10b981');
            if (liveAudioPlayer) {
              liveAudioPlayer.src = data.audio_url;
              liveAudioPlayer.style.display = 'block';
              liveAudioPlayer.load();
              liveAudioPlayer.play().catch(() => {});
            }
          } else if (evType === 'operation_failed') {
            appendTerminalLog(`Error: ${data.detail}`, '#f43f5e');
            window.showToast(`Live gateway error: ${data.detail}`, 'error');
          }
        } catch (err) {
          appendTerminalLog(`Message: ${event.data}`);
        }
      };

      speechSocket.onclose = () => {
        if (wsStatusBadge) {
          wsStatusBadge.className = 'status-pill status-neutral';
          wsStatusBadge.innerHTML = '<span class="status-dot"></span> Disconnected';
        }
        appendTerminalLog('WebSocket connection closed. Reconnecting in 3s...', '#f59e0b');
        setTimeout(initWebSocket, 3000);
      };

      speechSocket.onerror = (err) => {
        console.warn('WebSocket error:', err);
      };
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
    }
  }

  // Initialize socket on load
  initWebSocket();

  // Live recording stream
  if (liveBtnRecord) {
    liveBtnRecord.addEventListener('click', async () => {
      if (liveMediaRecorder && liveMediaRecorder.state === 'recording') {
        // Stop recording
        liveMediaRecorder.stop();
        liveBtnRecord.classList.remove('recording');
        if (liveRecordStatus) liveRecordStatus.textContent = 'Record Audio Stream';
        clearInterval(liveTimerInterval);
        if (liveAnimationId) cancelAnimationFrame(liveAnimationId);
        if (liveAudioCtx) liveAudioCtx.close();

        // Signal stop to backend over WebSocket
        if (speechSocket && speechSocket.readyState === WebSocket.OPEN) {
          speechSocket.send(JSON.stringify({ type: 'stop' }));
          appendTerminalLog('Stop signal sent. Awaiting atomic transcription...', '#38bdf8');
        }
      } else {
        // Start recording
        try {
          if (!speechSocket || speechSocket.readyState !== WebSocket.OPEN) {
            window.showToast('WebSocket not connected. Please wait...', 'warning');
            return;
          }

          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          liveTotalBytes = 0;
          if (liveBufferBytes) liveBufferBytes.textContent = '0 KB';

          // Reset transcript
          if (liveTranscriptBox) liveTranscriptBox.textContent = 'Streaming audio to gateway...';

          const wf = startWaveformVisualization(stream, 'live-mic-canvas');
          if (wf) {
            liveAudioCtx = wf.audioCtx;
            liveAnalyser = wf.analyser;
            liveAnimationId = wf.animId;
          }

          liveMediaRecorder = new MediaRecorder(stream);
          liveMediaRecorder.ondataavailable = async (e) => {
            if (e.data.size > 0 && speechSocket && speechSocket.readyState === WebSocket.OPEN) {
              const arrayBuf = await e.data.arrayBuffer();
              speechSocket.send(arrayBuf);
              liveTotalBytes += e.data.size;
            }
          };

          liveMediaRecorder.onstop = () => {
            stream.getTracks().forEach(track => track.stop());
          };

          // Slice every 250ms
          liveMediaRecorder.start(250);
          liveBtnRecord.classList.add('recording');
          if (liveRecordStatus) liveRecordStatus.textContent = 'Stop & Transcribe';
          appendTerminalLog('Microphone streaming started (chunk slice: 250ms)', '#38bdf8');

          liveStartTime = Date.now();
          liveTimerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - liveStartTime) / 1000);
            const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const secs = String(elapsed % 60).padStart(2, '0');
            if (liveMicTimer) liveMicTimer.textContent = `${mins}:${secs}`;
          }, 500);
        } catch (err) {
          window.showToast('Microphone streaming error: ' + err.message, 'error');
        }
      }
    });
  }

  // =========================================================================
  // 4. AUDIO HISTORY & AUDIT TRAIL
  // =========================================================================
  const historyTableBody = document.getElementById('history-table-body');
  const historyBtnRefresh = document.getElementById('history-btn-refresh');
  const historyBtnClear = document.getElementById('history-btn-clear');
  const kpiHistoryCount = document.getElementById('kpi-history-count');

  async function loadHistory() {
    try {
      const res = await fetch('/api/history?limit=50');
      if (!res.ok) return;
      const data = await res.json();
      const records = data.records || [];

      if (kpiHistoryCount) {
        kpiHistoryCount.textContent = data.total_count !== undefined ? data.total_count : records.length;
      }

      if (!historyTableBody) return;
      if (records.length === 0) {
        historyTableBody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 30px;">No history records found yet. Run an STT or TTS operation to see entries here.</td></tr>';
        return;
      }

      historyTableBody.innerHTML = '';
      records.forEach(rec => {
        const tr = document.createElement('tr');
        const isStt = rec.kind === 'stt';
        const badgeClass = isStt ? 'badge-blue' : 'badge-cyan';
        const timeFormatted = rec.created_at ? rec.created_at.replace('T', ' ').substring(0, 19) : '-';

        tr.innerHTML = `
          <td class="font-mono">#${rec.id}</td>
          <td><span class="status-pill ${badgeClass}" style="text-transform: uppercase; font-size: 0.72rem; padding: 2px 8px;">${rec.kind}</span></td>
          <td class="font-mono" style="font-size: 0.78rem;">${timeFormatted}</td>
          <td><strong>${rec.model_or_voice}</strong></td>
          <td class="font-mono">${rec.language}</td>
          <td class="font-mono">${rec.latency_sec.toFixed(3)}s</td>
          <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${rec.input_preview}">${rec.input_preview}</td>
          <td style="max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${rec.output_preview}">${rec.output_preview}</td>
          <td><span class="badge-lead-v25">&check; ${rec.status}</span></td>
        `;
        historyTableBody.appendChild(tr);
      });
    } catch (err) {
      console.warn('Failed to load history:', err);
    }
  }

  if (historyBtnRefresh) {
    historyBtnRefresh.addEventListener('click', () => {
      loadHistory();
      window.showToast('Audit history refreshed', 'info');
    });
  }

  if (historyBtnClear) {
    historyBtnClear.addEventListener('click', async () => {
      if (!confirm('Are you sure you want to clear all audio history logs?')) return;
      try {
        const res = await fetch('/api/history', { method: 'DELETE' });
        if (res.ok) {
          window.showToast('Audit history cleared successfully', 'success');
          loadHistory();
        }
      } catch (err) {
        window.showToast('Failed to clear history: ' + err.message, 'error');
      }
    });
  }

  // Load history count on boot
  loadHistory();

  // =========================================================================
  // 5. TELEPHONY STRESS LAB & BENCHMARK REPLAY (PRESERVED)
  // =========================================================================

  // Fetch benchmark summary and populate charts & data tables
  async function loadBenchmarkSummary() {
    try {
      const res = await fetch('/api/benchmark/summary');
      const data = await res.json();
      if (!data || !data.has_data) {
        console.warn('Benchmark summary data not yet available:', data);
        return;
      }
      renderOverviewCharts(data);
      renderComparisonTableAndCharts(data);
      renderDiagnosticsView(data);
    } catch (err) {
      console.error('Failed to load benchmark summary:', err);
    }
  }

  // Render Overview Charts
  function renderOverviewCharts(data) {
    const expA = data.experiment_a;
    if (!expA || !expA['prisma-v2.5'] || !expA['prisma-v3.0']) return;

    const conditions = ['clean', 'tel', 'tel_snr10', 'tel_snr0'];
    const labels = ['Clean 16kHz', 'Telephony G.712', 'Tel + 10dB SNR', 'Tel + 0dB SNR'];

    const v25Wers = conditions.map(c => (expA['prisma-v2.5'][c].mean_wer * 100));
    const v30Wers = conditions.map(c => (expA['prisma-v3.0'][c].mean_wer * 100));

    // Chart 1: WER Grouped Bar Chart
    const ctxWer = document.getElementById('overview-wer-chart');
    if (ctxWer && window.Chart) {
      if (chartInstances.overviewWer) chartInstances.overviewWer.destroy();
      chartInstances.overviewWer = new Chart(ctxWer, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Prisma v2.5',
              data: v25Wers,
              backgroundColor: '#10b981',
              borderRadius: 6,
              borderSkipped: false,
            },
            {
              label: 'Prisma v3.0',
              data: v30Wers,
              backgroundColor: '#06b6d4',
              borderRadius: 6,
              borderSkipped: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#181d2e',
              titleColor: '#fff',
              bodyColor: '#cbd5e1',
              borderColor: 'rgba(255, 255, 255, 0.1)',
              borderWidth: 1,
              padding: 10,
              callbacks: {
                label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toFixed(2)}% WER`,
              },
            },
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: '#8492a6', font: { family: 'Inter', size: 11 } },
            },
            y: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: {
                color: '#8492a6',
                font: { family: 'JetBrains Mono', size: 11 },
                callback: (val) => `${val}%`,
              },
              beginAtZero: true,
            },
          },
        },
      });
    }

    // Chart 2: Accuracy vs Latency Trade-off
    const ctxTradeoff = document.getElementById('overview-tradeoff-chart');
    if (ctxTradeoff && window.Chart) {
      if (chartInstances.overviewTradeoff) chartInstances.overviewTradeoff.destroy();

      const scatterV25 = conditions.map((c, i) => ({
        x: expA['prisma-v2.5'][c].p50_latency * 1000,
        y: expA['prisma-v2.5'][c].mean_wer * 100,
        cond: labels[i],
      }));
      const scatterV30 = conditions.map((c, i) => ({
        x: expA['prisma-v3.0'][c].p50_latency * 1000,
        y: expA['prisma-v3.0'][c].mean_wer * 100,
        cond: labels[i],
      }));

      chartInstances.overviewTradeoff = new Chart(ctxTradeoff, {
        type: 'scatter',
        data: {
          datasets: [
            {
              label: 'Prisma v2.5',
              data: scatterV25,
              backgroundColor: '#10b981',
              borderColor: '#10b981',
              pointRadius: 7,
              pointHoverRadius: 10,
            },
            {
              label: 'Prisma v3.0',
              data: scatterV30,
              backgroundColor: '#06b6d4',
              borderColor: '#06b6d4',
              pointRadius: 7,
              pointHoverRadius: 10,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true,
              labels: { color: '#8492a6', font: { family: 'Inter' } },
            },
            tooltip: {
              backgroundColor: '#181d2e',
              titleColor: '#fff',
              bodyColor: '#cbd5e1',
              borderColor: 'rgba(255, 255, 255, 0.1)',
              borderWidth: 1,
              callbacks: {
                label: (ctx) => `${ctx.dataset.label} (${ctx.raw.cond}): WER ${ctx.raw.y.toFixed(2)}%, P50 Latency ${ctx.raw.x.toFixed(0)} ms`,
              },
            },
          },
          scales: {
            x: {
              title: { display: true, text: 'P50 Latency (ms)', color: '#8492a6' },
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#8492a6', font: { family: 'JetBrains Mono' } },
            },
            y: {
              title: { display: true, text: 'Mean WER (%)', color: '#8492a6' },
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: {
                color: '#8492a6',
                font: { family: 'JetBrains Mono' },
                callback: (val) => `${val}%`,
              },
            },
          },
        },
      });
    }
  }

  // Render Model Comparison Table & Charts
  function renderComparisonTableAndCharts(data) {
    const expA = data.experiment_a;
    if (!expA) return;

    const tbody = document.getElementById('comparison-table-body');
    if (tbody) {
      tbody.innerHTML = '';
      const conditions = [
        { key: 'clean', label: 'Clean (16 kHz Studio)' },
        { key: 'tel', label: 'Telephony (ITU-T G.712)' },
        { key: 'tel_snr10', label: 'Tel + 10 dB SNR' },
        { key: 'tel_snr0', label: 'Tel + 0 dB SNR' },
      ];

      conditions.forEach(cond => {
        const v25 = expA['prisma-v2.5'][cond.key];
        const v30 = expA['prisma-v3.0'][cond.key];
        if (!v25 || !v30) return;

        const delta = v25.mean_wer - v30.mean_wer;
        let deltaHtml = '';
        if (delta > 0) {
          deltaHtml = `<span class="badge-lead-v30">v3.0 leads by +${(delta * 100).toFixed(2)}%</span>`;
        } else if (delta < 0) {
          deltaHtml = `<span class="badge-lead-v25">v2.5 leads by +${(Math.abs(delta) * 100).toFixed(2)}%</span>`;
        } else {
          deltaHtml = `<span class="badge-subtle">Parity</span>`;
        }

        // Row for v2.5
        const tr1 = document.createElement('tr');
        tr1.innerHTML = `
          <td><strong style="color: #10b981;">Prisma v2.5</strong></td>
          <td>${cond.label}</td>
          <td class="font-mono">${v25.n}</td>
          <td class="font-mono"><strong>${(v25.mean_wer * 100).toFixed(2)}%</strong></td>
          <td class="font-mono">[${(v25.ci_lower * 100).toFixed(2)}%, ${(v25.ci_upper * 100).toFixed(2)}%]</td>
          <td class="font-mono">${(v25.mean_cer * 100).toFixed(2)}%</td>
          <td class="font-mono">${v25.p50_latency.toFixed(3)}s</td>
          <td class="font-mono">${v25.p95_latency.toFixed(3)}s</td>
          <td class="font-mono">${v25.rtf.toFixed(3)}</td>
          <td rowspan="2" style="vertical-align: middle;">${deltaHtml}</td>
        `;
        tbody.appendChild(tr1);

        // Row for v3.0
        const tr2 = document.createElement('tr');
        tr2.innerHTML = `
          <td><strong style="color: #06b6d4;">Prisma v3.0</strong></td>
          <td>${cond.label}</td>
          <td class="font-mono">${v30.n}</td>
          <td class="font-mono"><strong>${(v30.mean_wer * 100).toFixed(2)}%</strong></td>
          <td class="font-mono">[${(v30.ci_lower * 100).toFixed(2)}%, ${(v30.ci_upper * 100).toFixed(2)}%]</td>
          <td class="font-mono">${(v30.mean_cer * 100).toFixed(2)}%</td>
          <td class="font-mono">${v30.p50_latency.toFixed(3)}s</td>
          <td class="font-mono">${v30.p95_latency.toFixed(3)}s</td>
          <td class="font-mono">${v30.rtf.toFixed(3)}</td>
        `;
        tbody.appendChild(tr2);
      });
    }

    // Chart: Confidence Intervals Comparison
    const ctxCi = document.getElementById('ci-comparison-chart');
    if (ctxCi && window.Chart) {
      if (chartInstances.comparisonCi) chartInstances.comparisonCi.destroy();
      const condKeys = ['clean', 'tel', 'tel_snr10', 'tel_snr0'];
      const condLabels = ['Clean', 'Telephony', 'Tel + 10dB', 'Tel + 0dB'];

      chartInstances.comparisonCi = new Chart(ctxCi, {
        type: 'line',
        data: {
          labels: condLabels,
          datasets: [
            {
              label: 'Prisma v2.5 Mean WER',
              data: condKeys.map(k => expA['prisma-v2.5'][k].mean_wer * 100),
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              tension: 0.2,
              fill: false,
              pointRadius: 6,
            },
            {
              label: 'Prisma v3.0 Mean WER',
              data: condKeys.map(k => expA['prisma-v3.0'][k].mean_wer * 100),
              borderColor: '#06b6d4',
              backgroundColor: 'rgba(6, 182, 212, 0.1)',
              tension: 0.2,
              fill: false,
              pointRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#8492a6', font: { family: 'Inter' } } },
            tooltip: {
              backgroundColor: '#181d2e',
              titleColor: '#fff',
              callbacks: {
                label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toFixed(2)}% WER`,
              },
            },
          },
          scales: {
            x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#8492a6' } },
            y: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#8492a6', callback: (v) => `${v}%` },
            },
          },
        },
      });
    }

    // Chart: CER Comparison
    const ctxCer = document.getElementById('cer-comparison-chart');
    if (ctxCer && window.Chart) {
      if (chartInstances.comparisonCer) chartInstances.comparisonCer.destroy();
      const condKeys = ['clean', 'tel', 'tel_snr10', 'tel_snr0'];
      const condLabels = ['Clean', 'Telephony', 'Tel + 10dB', 'Tel + 0dB'];

      chartInstances.comparisonCer = new Chart(ctxCer, {
        type: 'bar',
        data: {
          labels: condLabels,
          datasets: [
            {
              label: 'Prisma v2.5 CER',
              data: condKeys.map(k => expA['prisma-v2.5'][k].mean_cer * 100),
              backgroundColor: '#10b981',
              borderRadius: 4,
            },
            {
              label: 'Prisma v3.0 CER',
              data: condKeys.map(k => expA['prisma-v3.0'][k].mean_cer * 100),
              backgroundColor: '#06b6d4',
              borderRadius: 4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#8492a6', font: { family: 'Inter' } } },
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: '#8492a6' } },
            y: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#8492a6', callback: (v) => `${v}%` },
            },
          },
        },
      });
    }
  }

  // Render Diagnostics View
  function renderDiagnosticsView(data) {
    const tbody = document.getElementById('diagnostics-log-body');
    if (!tbody || !data.accounting || !data.accounting.timeout_recoveries) return;
    tbody.innerHTML = '';

    data.accounting.timeout_recoveries.forEach(ev => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="font-mono"><strong>${ev.id}</strong></td>
        <td class="font-mono">${ev.time}</td>
        <td>${ev.stage}</td>
        <td class="font-mono">${ev.clip}</td>
        <td><span class="badge-subtle">${ev.condition}</span></td>
        <td><span style="color: #f43f5e; font-weight: 600;">${ev.error}</span></td>
        <td class="font-mono">${ev.backoff_sec}s exponential backoff</td>
        <td><span class="badge-lead-v25">&check; ${ev.status}</span></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Load pre-loaded test clips into Stress Lab and STT Studio selects
  fetch('/api/clips')
    .then(res => res.json())
    .then(data => {
      if (data.clips) {
        benchmarkClipsList = data.clips;
        const sttClipSelect = document.getElementById('stt-clip-select');

        // Populate Stress Lab select
        if (clipSelect) {
          clipSelect.innerHTML = '<option value="">-- Choose a pre-loaded test clip --</option>';
          data.clips.forEach(clip => {
            const opt = document.createElement('option');
            opt.value = clip.id;
            opt.textContent = `[${clip.category}] ${clip.label}`;
            clipSelect.appendChild(opt);
          });
        }

        // Populate STT Studio select
        if (sttClipSelect) {
          sttClipSelect.innerHTML = '<option value="">-- Choose a preloaded speech clip --</option>';
          data.clips.forEach(clip => {
            const opt = document.createElement('option');
            opt.value = clip.id;
            opt.textContent = `[${clip.category}] ${clip.label}`;
            sttClipSelect.appendChild(opt);
          });
        }

        const urlParams = new URLSearchParams(window.location.search);
        const qClip = urlParams.get('clip_id');
        const qCond = urlParams.get('condition');
        if (qClip && clipSelect) clipSelect.value = qClip;
        if (qCond) {
          const radio = document.querySelector(`input[name="condition"][value="${qCond}"]`);
          if (radio) radio.checked = true;
        }
        if (qClip || qCond) {
          window.switchView('stress-lab');
        }
      }
    })
    .catch(err => console.error('Failed to load clips:', err));

  // Audio player update helper
  function updateAudioPlayer(clipId, condition) {
    if (!clipAudioPlayer || !clipId) return;
    clipAudioPlayer.src = `/api/audio/${clipId}?condition=${condition}`;
    clipAudioPlayer.load();
  }

  if (clipSelect) {
    clipSelect.addEventListener('change', () => {
      const clipId = clipSelect.value;
      const cond = document.querySelector('input[name="condition"]:checked')?.value || 'clean';
      if (clipId) {
        updateAudioPlayer(clipId, cond);
      }
    });
  }

  document.querySelectorAll('input[name="condition"]').forEach(radio => {
    radio.addEventListener('change', () => {
      const clipId = clipSelect ? clipSelect.value : null;
      if (clipId) {
        updateAudioPlayer(clipId, radio.value);
      }
    });
  });

  // Stress Form Submission (Interactive Replay)
  if (stressForm) {
    stressForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideError();

      const formData = new FormData(stressForm);
      const clipId = formData.get('clip_id');
      const condition = formData.get('condition') || 'clean';

      if (!clipId && (!audioFileInput.files || audioFileInput.files.length === 0)) {
        showError('Please select a pre-loaded test clip or upload an audio file.');
        return;
      }

      btnSubmit.disabled = true;
      if (loader) loader.classList.remove('hidden');

      try {
        let payload = {
          clip_id: clipId || null,
          condition: condition,
          live: 0,
        };

        if (audioFileInput.files && audioFileInput.files.length > 0) {
          const file = audioFileInput.files[0];
          const arrayBuf = await file.arrayBuffer();
          payload.audio_base64 = btoa(
            new Uint8Array(arrayBuf).reduce((d, byte) => d + String.fromCharCode(byte), '')
          );
        }

        const response = await fetch('/api/stress', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const errorData = await response.json();
          showError(`Evaluation error: ${errorData.detail || 'Request failed'}`);
          return;
        }

        const res = await response.json();
        displayStressResults(res, clipId, condition);
      } catch (err) {
        showError(`Network error: ${err.message}`);
      } finally {
        btnSubmit.disabled = false;
        if (loader) loader.classList.add('hidden');
      }
    });
  }

  // Display Stress Test Results
  function displayStressResults(data, clipId, condition) {
    if (data.has_live_results === false || !data.prisma_v25) {
      if (resultsSection) resultsSection.classList.add('hidden');
      showError(data.message || 'no live results yet', true);
      return;
    }
    hideError();

    // Update audio player
    if (clipId) {
      updateAudioPlayer(clipId, condition);
    }

    // Reference Card
    if (data.reference_text) {
      refText.textContent = data.reference_text;
      if (refClipMeta) {
        refClipMeta.textContent = `Clip: ${data.clip_id || clipId || 'Custom'} • Condition: ${data.condition || condition}`;
      }
      referenceCard.classList.remove('hidden');

      if (data.ground_truth_entities) {
        gtEntities.classList.remove('hidden');
        gtAmtTag.textContent = `Amount: ₹${data.ground_truth_entities.amount !== null ? data.ground_truth_entities.amount.toLocaleString('en-IN') : '-'}`;
        gtDayTag.textContent = `Due Day: ${data.ground_truth_entities.due_day || '-'}`;
      } else {
        gtEntities.classList.add('hidden');
      }
    } else {
      referenceCard.classList.add('hidden');
    }

    // Prisma v2.5 Card
    const v25 = data.prisma_v25;
    document.getElementById('v25-wer').textContent = v25.wer !== null ? `${(v25.wer * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('v25-cer').textContent = v25.cer !== null ? `${(v25.cer * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('v25-lat').textContent = `${v25.latency_sec.toFixed(3)}s`;
    document.getElementById('v25-transcript').textContent = v25.transcript || '(empty / no speech detected)';
    document.getElementById('v25-cache-badge').textContent = v25.from_cache ? 'Cache Hit' : 'Recorded Live';

    if (v25.extracted_entities) {
      const v25AmtEl = document.getElementById('v25-amt');
      const v25DayEl = document.getElementById('v25-day');
      const v25AmtStatus = document.getElementById('v25-amt-status');
      const v25DayStatus = document.getElementById('v25-day-status');

      v25AmtEl.textContent = v25.extracted_entities.amount !== null ? `₹${v25.extracted_entities.amount.toLocaleString('en-IN')}` : 'None';
      v25DayEl.textContent = v25.extracted_entities.due_day !== null ? `${v25.extracted_entities.due_day}` : 'None';

      if (data.ground_truth_entities && data.ground_truth_entities.amount !== null) {
        const isMatch = v25.extracted_entities.amount === data.ground_truth_entities.amount;
        v25AmtStatus.textContent = isMatch ? '✓ Exact Match' : '✗ Mismatch';
        v25AmtStatus.className = isMatch ? 'ep-status match' : 'ep-status mismatch';
      } else {
        v25AmtStatus.textContent = '';
      }

      if (data.ground_truth_entities && data.ground_truth_entities.due_day !== null) {
        const isMatch = v25.extracted_entities.due_day === data.ground_truth_entities.due_day;
        v25DayStatus.textContent = isMatch ? '✓ Exact Match' : '✗ Mismatch';
        v25DayStatus.className = isMatch ? 'ep-status match' : 'ep-status mismatch';
      } else {
        v25DayStatus.textContent = '';
      }
    }

    // Prisma v3.0 Card
    const v30 = data.prisma_v30;
    document.getElementById('v30-wer').textContent = v30.wer !== null ? `${(v30.wer * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('v30-cer').textContent = v30.cer !== null ? `${(v30.cer * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('v30-lat').textContent = `${v30.latency_sec.toFixed(3)}s`;
    document.getElementById('v30-transcript').textContent = v30.transcript || '(empty / no speech detected)';
    document.getElementById('v30-cache-badge').textContent = v30.from_cache ? 'Cache Hit' : 'Recorded Live';

    if (v30.extracted_entities) {
      const v30AmtEl = document.getElementById('v30-amt');
      const v30DayEl = document.getElementById('v30-day');
      const v30AmtStatus = document.getElementById('v30-amt-status');
      const v30DayStatus = document.getElementById('v30-day-status');

      v30AmtEl.textContent = v30.extracted_entities.amount !== null ? `₹${v30.extracted_entities.amount.toLocaleString('en-IN')}` : 'None';
      v30DayEl.textContent = v30.extracted_entities.due_day !== null ? `${v30.extracted_entities.due_day}` : 'None';

      if (data.ground_truth_entities && data.ground_truth_entities.amount !== null) {
        const isMatch = v30.extracted_entities.amount === data.ground_truth_entities.amount;
        v30AmtStatus.textContent = isMatch ? '✓ Exact Match' : '✗ Mismatch';
        v30AmtStatus.className = isMatch ? 'ep-status match' : 'ep-status mismatch';
      } else {
        v30AmtStatus.textContent = '';
      }

      if (data.ground_truth_entities && data.ground_truth_entities.due_day !== null) {
        const isMatch = v30.extracted_entities.due_day === data.ground_truth_entities.due_day;
        v30DayStatus.textContent = isMatch ? '✓ Exact Match' : '✗ Mismatch';
        v30DayStatus.className = isMatch ? 'ep-status match' : 'ep-status mismatch';
      } else {
        v30DayStatus.textContent = '';
      }
    }

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
    window.showToast('Evaluation replayed from verified live benchmark', 'success');
  }

  // Helper: HTML Escaper
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  window.playFlwAudio = function(url) {
    const p = document.getElementById('flw-audio-player');
    if (p) {
      p.src = url;
      p.play();
    }
  };

  // Follow-up Desk Controller
  let flwScenarios = [];
  let flwSelectedScenarioId = 'scenario_01';
  let flwInitialized = false;

  async function initFollowupDesk() {
    if (flwInitialized) return;
    flwInitialized = true;

    const customTranscript = document.getElementById('flw-custom-transcript');
    const modelSelect = document.getElementById('flw-model-select');
    const langSelect = document.getElementById('flw-lang-select');
    const btnProcess = document.getElementById('flw-btn-process');
    const processLoader = document.getElementById('flw-process-loader');
    const reviewCard = document.getElementById('flw-review-card');
    const missingAlert = document.getElementById('flw-missing-alert');
    const missingFieldsText = document.getElementById('flw-missing-fields-text');
    const transcriptText = document.getElementById('flw-transcript-text');
    const summaryText = document.getElementById('flw-summary-text');
    const customerName = document.getElementById('flw-customer-name');
    const amountInput = document.getElementById('flw-amount-input');
    const amountBadge = document.getElementById('flw-amount-badge');
    const dueInput = document.getElementById('flw-due-input');
    const dueBadge = document.getElementById('flw-due-badge');
    const ptpInput = document.getElementById('flw-ptp-input');
    const ptpBadge = document.getElementById('flw-ptp-badge');
    const concernSelect = document.getElementById('flw-concern-select');
    const chkConfirm = document.getElementById('flw-chk-confirm');
    const operatorNotes = document.getElementById('flw-operator-notes');
    const btnConfirmStep = document.getElementById('flw-btn-confirm-step');
    const synthesisCard = document.getElementById('flw-synthesis-card');
    const reminderText = document.getElementById('flw-reminder-text');
    const voiceSelect = document.getElementById('flw-voice-select');
    const btnSynthesize = document.getElementById('flw-btn-synthesize');
    const synthLoader = document.getElementById('flw-synth-loader');
    const audioOutputWrapper = document.getElementById('flw-audio-output-wrapper');
    const audioPlayer = document.getElementById('flw-audio-player');
    const btnDownloadWav = document.getElementById('flw-btn-download-wav');
    const audioMeta = document.getElementById('flw-audio-meta');
    const historyTbody = document.getElementById('flw-history-tbody');
    const step1 = document.getElementById('flw-step-ind-1');
    const step2 = document.getElementById('flw-step-ind-2');
    const step3 = document.getElementById('flw-step-ind-3');

    // Load scenarios catalog
    try {
      const res = await fetch('/api/followup/scenarios');
      if (res.ok) {
        const data = await res.json();
        flwScenarios = data.scenarios || [];
        if (flwScenarios.length > 0 && customTranscript) {
          customTranscript.value = flwScenarios[0].transcript || '';
        }
      }
    } catch (err) {
      console.warn('Could not fetch followup scenarios:', err);
    }

    // Scenario chip listeners
    document.querySelectorAll('#flw-scenario-chips .scenario-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('#flw-scenario-chips .scenario-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        flwSelectedScenarioId = chip.getAttribute('data-id');

        const found = flwScenarios.find(s => s.id === flwSelectedScenarioId);
        if (found && customTranscript) {
          customTranscript.value = found.transcript || '';
        }

        // Reset downstream cards for fresh process
        if (reviewCard) reviewCard.classList.add('hidden');
        if (synthesisCard) synthesisCard.classList.add('hidden');
        if (audioOutputWrapper) audioOutputWrapper.classList.add('hidden');
        if (step1) step1.classList.add('active');
        if (step2) step2.classList.remove('active');
        if (step3) step3.classList.remove('active');
      });
    });

    // Process button click
    if (btnProcess) {
      btnProcess.addEventListener('click', async () => {
        btnProcess.disabled = true;
        if (processLoader) processLoader.classList.remove('hidden');

        try {
          const payload = {
            scenario_id: flwSelectedScenarioId,
            transcript: customTranscript ? customTranscript.value.trim() : undefined,
            model: modelSelect ? modelSelect.value : 'prisma-v3.0',
            language: langSelect ? langSelect.value : 'hi-IN'
          };

          const res = await fetch('/api/followup/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });

          if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Failed to process follow-up call');
          }

          const data = await res.json();
          const d = data.details || {};

          // Populate step 2 fields
          if (transcriptText) transcriptText.value = data.transcript || '';
          if (summaryText) summaryText.value = d.summary || '';
          if (customerName) customerName.value = data.customer || '';
          if (amountInput) amountInput.value = (d.amount !== null && d.amount !== undefined) ? d.amount : '';

          if (amountBadge) {
            if (d.amount_detected) {
              amountBadge.className = 'field-badge-extracted';
              amountBadge.textContent = 'Detected';
            } else {
              amountBadge.className = 'field-badge-missing';
              amountBadge.textContent = 'Not Detected — Operator Required';
            }
          }

          if (dueInput) dueInput.value = d.due_date_formatted || '';
          if (dueBadge) {
            if (d.due_date_detected) {
              dueBadge.className = 'field-badge-extracted';
              dueBadge.textContent = 'Detected';
            } else {
              dueBadge.className = 'field-badge-missing';
              dueBadge.textContent = 'Not Detected';
            }
          }

          if (ptpInput) ptpInput.value = d.ptp_date_formatted || '';
          if (ptpBadge) {
            if (d.ptp_date_detected) {
              ptpBadge.className = 'field-badge-extracted';
              ptpBadge.textContent = 'Detected';
            } else {
              ptpBadge.className = 'field-badge-missing';
              ptpBadge.textContent = 'Not Detected — Operator Required';
            }
          }

          if (concernSelect && d.concern) {
            concernSelect.value = d.concern;
          }

          // Missing fields alert
          if (missingAlert && missingFieldsText) {
            if (d.missing_fields && d.missing_fields.length > 0) {
              missingFieldsText.textContent = `Field(s) requiring verification: ${d.missing_fields.join(', ')}.`;
              missingAlert.classList.remove('hidden');
            } else {
              missingAlert.classList.add('hidden');
            }
          }

          if (reminderText) {
            reminderText.value = data.suggested_reminder_text || '';
          }

          // Reset confirmation controls
          if (chkConfirm) chkConfirm.checked = false;
          if (btnConfirmStep) btnConfirmStep.disabled = true;

          // Reveal step 2 and update stepper
          if (reviewCard) reviewCard.classList.remove('hidden');
          if (step1) step1.classList.remove('active');
          if (step2) step2.classList.add('active');

          reviewCard.scrollIntoView({ behavior: 'smooth' });
          window.showToast('Call commitments extracted. Operator review ready.', 'info');
        } catch (err) {
          console.error(err);
          window.showToast('Error processing call: ' + err.message, 'error');
        } finally {
          btnProcess.disabled = false;
          if (processLoader) processLoader.classList.add('hidden');
        }
      });
    }

    // Checkbox operator confirm toggle
    if (chkConfirm && btnConfirmStep) {
      chkConfirm.addEventListener('change', () => {
        btnConfirmStep.disabled = !chkConfirm.checked;
      });
    }

    // Confirm step button
    if (btnConfirmStep) {
      btnConfirmStep.addEventListener('click', () => {
        if (!chkConfirm.checked) return;

        if (step2) step2.classList.remove('active');
        if (step3) step3.classList.add('active');
        if (synthesisCard) {
          synthesisCard.classList.remove('hidden');
          synthesisCard.scrollIntoView({ behavior: 'smooth' });
        }
        window.showToast('Commitment audit confirmed by operator. Proceeding to voice synthesis.', 'success');
      });
    }

    // Synthesize reminder audio button
    if (btnSynthesize) {
      btnSynthesize.addEventListener('click', async () => {
        btnSynthesize.disabled = true;
        if (synthLoader) synthLoader.classList.remove('hidden');

        try {
          const amtParsed = amountInput && amountInput.value.trim() ? parseFloat(amountInput.value) : null;
          const payload = {
            customer: customerName ? customerName.value.trim() : 'Customer',
            amount: isNaN(amtParsed) ? null : amtParsed,
            due_date: dueInput ? dueInput.value.trim() : null,
            ptp_date: ptpInput ? ptpInput.value.trim() : null,
            concern: concernSelect ? concernSelect.value : null,
            summary: summaryText ? summaryText.value.trim() : 'Confirmed follow-up summary',
            reminder_text: reminderText ? reminderText.value.trim() : 'Payment reminder notice',
            voice: voiceSelect ? voiceSelect.value : 'pranav',
            language: 'hi-IN',
            operator_notes: operatorNotes ? operatorNotes.value.trim() : null
          };

          const res = await fetch('/api/followup/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });

          if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Failed to synthesize reminder audio');
          }

          const data = await res.json();

          // Audio player setup
          if (data.audio_b64) {
            const byteChars = atob(data.audio_b64);
            const byteNums = new Array(byteChars.length);
            for (let i = 0; i < byteChars.length; i++) {
              byteNums[i] = byteChars.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNums);
            const blob = new Blob([byteArray], { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(blob);

            if (audioPlayer) {
              audioPlayer.src = audioUrl;
              audioPlayer.load();
            }

            if (btnDownloadWav) {
              btnDownloadWav.href = audioUrl;
              const safeCust = (data.customer || 'customer').replace(/[^a-zA-Z0-9_-]/g, '_');
              btnDownloadWav.download = `${safeCust}_reminder.wav`;
            }

            if (audioMeta) {
              audioMeta.textContent = `Gnani Timbre (${data.voice}) • ${data.duration_s ? data.duration_s.toFixed(2) : '1.50'}s • Record ID: ${data.record_id ? data.record_id.slice(0, 8) : 'rec-live'}`;
            }

            if (audioOutputWrapper) {
              audioOutputWrapper.classList.remove('hidden');
              audioOutputWrapper.scrollIntoView({ behavior: 'smooth' });
            }

            // Append to history table
            if (historyTbody) {
              const emptyTd = historyTbody.querySelector('td[colspan="7"]');
              if (emptyTd) emptyTd.closest('tr').remove();

              const tr = document.createElement('tr');
              const amtDisplay = (amtParsed !== null && !isNaN(amtParsed)) ? `₹${amtParsed.toLocaleString('en-IN')}` : '<span class="text-amber">Not set</span>';
              const concernText = concernSelect ? concernSelect.options[concernSelect.selectedIndex].text : 'General';

              tr.innerHTML = `
                <td class="font-mono">${new Date().toLocaleTimeString()}</td>
                <td><strong>${escapeHtml(data.customer)}</strong></td>
                <td class="font-mono text-cyan">${amtDisplay}</td>
                <td><span class="badge-subtle">${escapeHtml(payload.ptp_date || '-')}</span></td>
                <td>${escapeHtml(concernText)}</td>
                <td><span class="field-badge-confirmed">Synthesized</span></td>
                <td>
                  <button type="button" class="btn btn-ghost btn-sm" onclick="window.playFlwAudio('${audioUrl}')">▶ Play</button>
                </td>
              `;
              historyTbody.prepend(tr);
            }

            window.showToast('Voice reminder synthesized and recorded to audit log.', 'success');
          }
        } catch (err) {
          console.error(err);
          window.showToast('Error synthesizing voice reminder: ' + err.message, 'error');
        } finally {
          btnSynthesize.disabled = false;
          if (synthLoader) synthLoader.classList.add('hidden');
        }
      });
    }
  }

  // Load summary on start
  loadBenchmarkSummary();
  initFollowupDesk();
});
