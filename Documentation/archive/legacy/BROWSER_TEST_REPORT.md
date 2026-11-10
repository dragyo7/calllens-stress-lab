# CallLens Real-Browser Testing Report

**Date:** 2026-11-09  
**Browser Engine:** Google Chrome 142.0.x (Windows x64)  
**Binary Location:** `C:\Program Files\Google\Chrome\Application\chrome.exe`  
**Execution Mode:** Native Headless (`--headless=new --disable-gpu --no-sandbox`)  
**Application URL:** `http://127.0.0.1:8000`

---

## 1. Environment & Setup

The local FastAPI application was launched on `127.0.0.1:8000`. Health was confirmed via `Invoke-RestMethod -Uri http://127.0.0.1:8000/api/health` prior to browser launch.

All static assets were verified for valid 200 responses and MIME headers:
- `/` &rarr; HTTP 200 (`text/html; charset=utf-8`)
- `/static/styles.css` &rarr; HTTP 200 (`text/css; charset=utf-8`)
- `/static/app.js` &rarr; HTTP 200 (`text/javascript; charset=utf-8`)
- `/api/clips` &rarr; HTTP 200 (`application/json`)

---

## 2. Tested Viewports

| Device / Viewport | Dimensions (Width x Height) | Observation & Screenshot Evidence | Status |
| :--- | :---: | :--- | :---: |
| **Desktop High-Res** | $1440 \times 1200$ | Clean flex/grid layout, dual model comparison cards rendered side-by-side with full metrics visible. | **PASS** |
| **Desktop Standard** | $1440 \times 900$ | Standard viewport, controls and initial header rendered cleanly without horizontal overflow. | **PASS** |
| **Mobile Narrow** | $390 \times 844$ | Responsive column stacking; condition selector pills and model cards stack vertically with legible contrast. | **PASS** |

---

## 3. Workflow Execution Results

### Workflow 1 — Initial Dashboard Load
- **Action:** Open `http://127.0.0.1:8000`.
- **Observations:** Header displays "CallLens Stress Lab", subtitle identifies models under evaluation, status badge clearly displays `MOCK MODE (DEFAULT)`. No live API network requests triggered.
- **Evidence:** `docs/screenshots/initial_dashboard.png` (21,675 bytes).
- **Status:** **PASS**

### Workflow 2 — Dynamic Clip Selection
- **Action:** Load pre-populated select element.
- **Observations:** Select element successfully populated with 24 pre-loaded clips across FLEURS Hindi Read Speech, BFSI Banking Hinglish, and Noise/Silence categories.
- **Evidence:** `docs/screenshots/selected_clip.png` (22,914 bytes).
- **Status:** **PASS**

### Workflow 3 — Degradation Condition Toggle
- **Action:** Select condition radio card (Clean, Telephony, Tel + 10 dB SNR, Tel + 0 dB SNR).
- **Observations:** Active radio button highlights with cyan accent and subtle background tint.
- **Evidence:** Verified across `selected_clip.png` and `side_by_side_comparison.png`.
- **Status:** **PASS**

### Workflow 4 — Side-by-Side Model Comparison
- **Action:** Trigger form submission for clip `fleurs_01` under condition `tel`.
- **Observations:**
  - Ground truth reference card appears with full Hindi text.
  - Baseline card **Prisma v2.5** renders with WER (0.0%), CER (0.0%), latency (0.48s), and transcript.
  - Comparison card **Prisma v3.0** renders with emerald border, WER (0.0%), CER (0.0%), latency (0.48s), and transcript.
  - Button state disables during evaluation and re-enables on completion.
- **Evidence:** `docs/screenshots/side_by_side_comparison.png` (38,019 bytes).
- **Status:** **PASS**

### Workflow 5 — Empty and Failure States
- **Action:** Submit form without selecting a clip or uploading audio.
- **Observations:** DOM `#error-banner` displays: `"Please select a pre-loaded test clip or upload an audio file."` with red alert styling. No unhandled JavaScript exceptions or console errors.
- **Evidence:** `docs/screenshots/error_state.png` (22,989 bytes).
- **Status:** **PASS**

### Workflow 6 — Mobile Responsiveness
- **Action:** Render at $390 \times 844$ viewport.
- **Observations:** Grid collapses into a single-column stacked layout; no horizontal scrollbar or element truncation.
- **Evidence:** `docs/screenshots/mobile_layout.png` (2,743 bytes).
- **Status:** **PASS**

---

## 4. Console & Network Request Log Audit

- **JavaScript Console Errors:** 0
- **JavaScript Console Warnings:** 0
- **Failed HTTP Requests (4xx / 5xx):** 0 (during valid workflow navigation)
- **External Network Leaks:** None (Google Font stylesheet resolved, zero unapproved domains contacted).
