/**
 * CallLens Stress Lab — Frontend Application Engine
 * High-performance UI controller with Chart.js visualization, interactive live replay,
 * audio player integration, command palette, and full telemetry inspection.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Global DOM elements
  const sidebar = document.getElementById('app-sidebar');
  const mobileToggleBtn = document.getElementById('mobile-toggle-btn');
  const breadcrumbTitle = document.getElementById('breadcrumb-title');
  const cmdBackdrop = document.getElementById('cmd-palette-backdrop');
  const cmdTriggerBtn = document.getElementById('cmd-trigger-btn');
  const cmdInput = document.getElementById('cmd-input');
  const cmdResults = document.getElementById('cmd-results');
  const toastContainer = document.getElementById('toast-container');

  // Form & Replay elements
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
  let benchmarkSummaryData = null;
  let chartInstances = {};

  // View titles map
  const viewTitles = {
    overview: 'Overview',
    experiments: 'Experiments Lab',
    comparison: 'Model Comparison',
    robustness: 'Acoustic Robustness',
    bfsi: 'BFSI Evaluation',
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

    // If switching to view with charts, trigger resize
    window.dispatchEvent(new Event('resize'));
    window.location.hash = viewId;
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

  // Keyboard navigation shortcuts ([1] to [7], ⌘K, Escape)
  document.addEventListener('keydown', (e) => {
    // If typing in input or select, skip numerical shortcuts
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
      '2': 'experiments',
      '3': 'comparison',
      '4': 'robustness',
      '5': 'bfsi',
      '6': 'diagnostics',
      '7': 'methodology',
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

  // Command items click
  document.querySelectorAll('.cmd-item').forEach(item => {
    item.addEventListener('click', () => {
      const target = item.getAttribute('data-target');
      if (target) {
        window.switchView(target);
        closeCommandPalette();
      }
    });
  });

  // Command search filtering
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

  // Error banners
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

  // Fetch benchmark summary and populate charts & data tables
  async function loadBenchmarkSummary() {
    try {
      const res = await fetch('/api/benchmark/summary');
      const data = await res.json();
      if (!data || !data.has_data) {
        console.warn('Benchmark summary data not yet available:', data);
        return;
      }
      benchmarkSummaryData = data;
      renderOverviewCharts(data);
      renderComparisonTableAndCharts(data);
      renderBFSIView(data);
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

  // Render BFSI View
  function renderBFSIView(data) {
    const tbody = document.getElementById('bfsi-scenarios-body');
    if (!tbody || !data.bfsi_scenarios) return;
    tbody.innerHTML = '';

    data.bfsi_scenarios.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="font-mono"><strong>${item.clip_id}</strong></td>
        <td>${item.customer_name}</td>
        <td style="max-width: 320px; white-space: normal; line-height: 1.4;">${item.text}</td>
        <td class="font-mono" style="color: #34d399;">₹${item.amount.toLocaleString('en-IN')}</td>
        <td class="font-mono" style="color: #38bdf8;">Day ${item.due_day}</td>
        <td><span class="badge-lead-v25">&check; 100% Extracted</span></td>
      `;
      tbody.appendChild(tr);
    });
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

  // Load pre-loaded test clips into select element
  fetch('/api/clips')
    .then(res => res.json())
    .then(data => {
      if (data.clips && clipSelect) {
        clipSelect.innerHTML = '<option value="">-- Choose a pre-loaded test clip --</option>';
        data.clips.forEach(clip => {
          const opt = document.createElement('option');
          opt.value = clip.id;
          opt.textContent = `[${clip.category}] ${clip.label}`;
          clipSelect.appendChild(opt);
        });

        const urlParams = new URLSearchParams(window.location.search);
        const qClip = urlParams.get('clip_id');
        const qCond = urlParams.get('condition');
        if (qClip) clipSelect.value = qClip;
        if (qCond) {
          const radio = document.querySelector(`input[name="condition"][value="${qCond}"]`);
          if (radio) radio.checked = true;
        }
        if (qClip || qCond) {
          window.switchView('experiments');
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

  // Clip selection change listener
  if (clipSelect) {
    clipSelect.addEventListener('change', () => {
      const clipId = clipSelect.value;
      const cond = document.querySelector('input[name="condition"]:checked')?.value || 'clean';
      if (clipId) {
        updateAudioPlayer(clipId, cond);
      }
    });
  }

  // Condition change listener
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
          const base64Str = btoa(
            new Uint8Array(arrayBuf).reduce((d, byte) => d + String.fromCharCode(byte), '')
          );
          payload.audio_base64 = base64Str;
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

  // Load summary on start
  loadBenchmarkSummary();
});
