document.addEventListener('DOMContentLoaded', () => {
  const clipSelect = document.getElementById('clip-select');
  const stressForm = document.getElementById('stress-form');
  const btnSubmit = document.getElementById('btn-submit');
  const loader = document.getElementById('loader');
  const resultsSection = document.getElementById('results-section');
  const referenceCard = document.getElementById('reference-card');
  const refText = document.getElementById('ref-text');
  const gtEntities = document.getElementById('gt-entities');
  const gtAmtTag = document.getElementById('gt-amt-tag');
  const gtDayTag = document.getElementById('gt-day-tag');

  // Load clips list
  fetch('/api/clips')
    .then(res => res.json())
    .then(data => {
      if (data.clips) {
        data.clips.forEach(clip => {
          const opt = document.createElement('option');
          opt.value = clip.id;
          opt.textContent = `[${clip.category}] ${clip.label}`;
          clipSelect.appendChild(opt);
        });
      }
    })
    .catch(err => console.error('Failed to load clips:', err));

  // Form submission
  stressForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(stressForm);
    const audioFileInput = document.getElementById('audio-file');

    if (!formData.get('clip_id') && (!audioFileInput.files || audioFileInput.files.length === 0)) {
      alert('Please select a pre-loaded test clip or upload an audio file.');
      return;
    }

    btnSubmit.disabled = true;
    loader.classList.remove('hidden');

    try {
      let payload = {
        clip_id: formData.get('clip_id') || null,
        condition: formData.get('condition') || 'clean',
        live: 0,
      };

      if (audioFileInput.files && audioFileInput.files.length > 0) {
        const file = audioFileInput.files[0];
        const arrayBuf = await file.arrayBuffer();
        const base64Str = btoa(
          new Uint8Array(arrayBuf).reduce((data, byte) => data + String.fromCharCode(byte), '')
        );
        payload.audio_base64 = base64Str;
      }

      const response = await fetch('/api/stress', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });


      if (!response.ok) {
        const errorData = await response.json();
        alert(`Evaluation error: ${errorData.detail || 'Request failed'}`);
        return;
      }

      const res = await response.json();
      displayResults(res);
    } catch (err) {
      alert(`Network error: ${err.message}`);
    } finally {
      btnSubmit.disabled = false;
      loader.classList.add('hidden');
    }
  });

  function displayResults(data) {
    // Reference card
    if (data.reference_text) {
      refText.textContent = data.reference_text;
      referenceCard.classList.remove('hidden');

      if (data.ground_truth_entities) {
        gtEntities.classList.remove('hidden');
        gtAmtTag.textContent = `Amount: ₹${data.ground_truth_entities.amount || '-'}`;
        gtDayTag.textContent = `Due Day: ${data.ground_truth_entities.due_day || '-'}`;
      } else {
        gtEntities.classList.add('hidden');
      }
    } else {
      referenceCard.classList.add('hidden');
    }

    // Prisma v2.5
    const v25 = data.prisma_v25;
    document.getElementById('v25-wer').textContent = v25.wer !== null ? `${(v25.wer * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('v25-cer').textContent = v25.cer !== null ? `${(v25.cer * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('v25-lat').textContent = `${v25.latency_sec.toFixed(2)}s`;
    document.getElementById('v25-transcript').textContent = v25.transcript || '(empty / no speech detected)';
    document.getElementById('v25-cache-badge').textContent = v25.from_cache ? 'Cache Hit' : (v25.mock ? 'Mock Mode' : 'Live');

    if (v25.extracted_entities) {
      document.getElementById('v25-amt').textContent = v25.extracted_entities.amount !== null ? `₹${v25.extracted_entities.amount}` : 'None';
      document.getElementById('v25-day').textContent = v25.extracted_entities.due_day !== null ? `${v25.extracted_entities.due_day}` : 'None';
    }

    // Prisma v3.0
    const v30 = data.prisma_v30;
    document.getElementById('v30-wer').textContent = v30.wer !== null ? `${(v30.wer * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('v30-cer').textContent = v30.cer !== null ? `${(v30.cer * 100).toFixed(1)}%` : 'N/A';
    document.getElementById('v30-lat').textContent = `${v30.latency_sec.toFixed(2)}s`;
    document.getElementById('v30-transcript').textContent = v30.transcript || '(empty / no speech detected)';
    document.getElementById('v30-cache-badge').textContent = v30.from_cache ? 'Cache Hit' : (v30.mock ? 'Mock Mode' : 'Live');

    if (v30.extracted_entities) {
      document.getElementById('v30-amt').textContent = v30.extracted_entities.amount !== null ? `₹${v30.extracted_entities.amount}` : 'None';
      document.getElementById('v30-day').textContent = v30.extracted_entities.due_day !== null ? `${v30.extracted_entities.due_day}` : 'None';
    }

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
  }
});
