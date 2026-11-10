"""Real Browser End-to-End Verification using Chrome DevTools Protocol (CDP).

Launches headless Google Chrome, navigates to the running CallLens instance (http://127.0.0.1:8000),
exercises all major UI workflows, inspects console logs for zero uncaught errors,
and verifies DOM mutations across TTS Studio, STT Studio, Follow-up Desk, and My Recordings.
"""

import asyncio
import json
import os
import subprocess
import time
import urllib.request
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9222
APP_URL = "http://127.0.0.1:8000"


class CDPBrowser:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
        self._msg_id = 0
        self.console_errors = []

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=10 * 1024 * 1024)
        await self.send("Console.enable")
        await self.send("Runtime.enable")
        await self.send("Page.enable")
        asyncio.create_task(self._listen())

    async def _listen(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                if msg.get("method") == "Runtime.consoleAPICalled":
                    params = msg.get("params", {})
                    if params.get("type") == "error":
                        args = [str(a.get("value", a.get("description", ""))) for a in params.get("args", [])]
                        self.console_errors.append(" ".join(args))
                elif msg.get("method") == "Runtime.exceptionThrown":
                    details = msg.get("params", {}).get("exceptionDetails", {})
                    self.console_errors.append(f"UNCAUGHT: {details.get('text')} - {details.get('exception', {}).get('description')}")
        except Exception:
            pass

    async def send(self, method: str, params: dict | None = None) -> dict:
        self._msg_id += 1
        call_id = self._msg_id
        req = {"id": call_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(req))
        # Wait for reply with matching id
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == call_id:
                return data

    async def evaluate(self, expression: str) -> any:
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        result = res.get("result", {}).get("result", {})
        if "value" in result:
            return result["value"]
        return result

    async def close(self):
        if self.ws:
            await self.ws.close()


async def run_e2e_audit():
    print("==================================================")
    print("STARTING REAL BROWSER E2E FAILURE AUDIT & VERIFICATION")
    print("==================================================")

    # 0. Pre-flight health check to ensure we do not connect to a stale server
    print(f"[Pre-flight] Verifying running server at {APP_URL}/api/health...")
    try:
        with urllib.request.urlopen(f"{APP_URL}/api/health", timeout=5) as resp:
            health_data = json.loads(resp.read().decode())
            print(f"[Pre-flight] Server Status: {health_data.get('status')}, Live API: {health_data.get('live_api_enabled')}")
            assert health_data.get("status") == "healthy", f"Unhealthy server: {health_data}"
    except Exception as exc:
        raise RuntimeError(f"Cannot reach server at {APP_URL}/api/health. Is Uvicorn running? Error: {exc}")

    # 1. Start headless Chrome
    user_data_dir = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "calllens_chrome_e2e")
    chrome_proc = subprocess.Popen(
        [
            CHROME_PATH,
            "--headless=new",
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-gpu",
            "--mute-audio",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for CDP endpoint to be ready
        ws_url = None
        for _ in range(30):
            time.sleep(0.3)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json") as resp:
                    tabs = json.loads(resp.read().decode())
                    if tabs:
                        ws_url = tabs[0]["webSocketDebuggerUrl"]
                        break
            except Exception:
                pass

        if not ws_url:
            raise RuntimeError("Failed to attach to headless Chrome CDP port 9222")

        print(f"[CDP] Attached to Chrome browser session: {ws_url}")
        browser = CDPBrowser(ws_url)
        await browser.connect()

        # 2. Navigate to CallLens
        print(f"[CDP] Navigating to {APP_URL}...")
        await browser.send("Page.navigate", {"url": APP_URL})
        await asyncio.sleep(2.0)

        title = await browser.evaluate("document.title")
        print(f"[CDP] Document Title: '{title}'")
        assert "CallLens" in title, f"Unexpected page title: {title}"

        # 3. Test View 3: Convert Text to Speech (TTS Studio)
        print("\n--- TEST: TTS Studio Interaction ---")
        await browser.evaluate("window.switchView('tts-studio')")
        await asyncio.sleep(0.5)

        # Type text into tts text input
        await browser.evaluate("document.getElementById('tts-text-input').value = 'नमस्ते यह कॉललेंस का स्वचालित ब्राउज़र परीक्षण है'")
        # Ensure voice select is populated
        voice_count = await browser.evaluate("document.getElementById('tts-voice-select').options.length")
        selected_voice = await browser.evaluate("document.getElementById('tts-voice-select').value")
        print(f"[TTS Studio] Voices loaded: {voice_count}, Selected voice: '{selected_voice}'")
        assert voice_count >= 2, f"Voices dropdown was not populated: {voice_count}"
        assert selected_voice != "undefined", f"Selected voice is 'undefined'! Voice dropdown bug reproduced!"

        # Click submit button
        print("[TTS Studio] Triggering speech synthesis form submit...")
        await browser.evaluate("document.getElementById('tts-studio-form').dispatchEvent(new Event('submit'))")
        await asyncio.sleep(2.0)

        # Check output card visibility and stats
        card_hidden = await browser.evaluate("document.getElementById('tts-output-card').classList.contains('hidden')")
        dur_text = await browser.evaluate("document.getElementById('tts-stat-dur').textContent")
        lat_text = await browser.evaluate("document.getElementById('tts-stat-lat').textContent")
        chars_text = await browser.evaluate("document.getElementById('tts-stat-chars').textContent")
        audio_src = await browser.evaluate("document.getElementById('tts-audio-player').src")

        print(f"[TTS Studio] Output Card Hidden: {card_hidden}")
        print(f"[TTS Studio] Duration Display: '{dur_text}'")
        print(f"[TTS Studio] Latency Display: '{lat_text}'")
        print(f"[TTS Studio] Chars Display: '{chars_text}'")
        print(f"[TTS Studio] Audio Player src: '{audio_src}'")

        assert not card_hidden, "TTS output card remained hidden after synthesis!"
        assert dur_text != "NaNs" and "s" in dur_text and not dur_text.startswith("undefined"), f"Invalid duration display: {dur_text}"
        assert chars_text != "undefined", f"Chars display is 'undefined': {chars_text}"
        assert "/api/tts/audio/" in audio_src, f"Audio player src was not set: {audio_src}"

        # Verify real audio decoding in browser HTML5 Audio element
        audio_ready = await browser.evaluate("""
            (() => {
                const el = document.getElementById('tts-audio-player');
                return {
                    readyState: el ? el.readyState : 0,
                    duration: el ? el.duration : 0,
                    paused: el ? el.paused : true,
                    error: (el && el.error) ? el.error.message : null
                };
            })()
        """)
        print(f"[TTS Studio] Audio Element State: readyState={audio_ready.get('readyState')}, duration={audio_ready.get('duration')}")
        assert audio_ready.get("error") is None, f"Audio player decoding error: {audio_ready.get('error')}"
        print("✓ TTS Studio workflow PASSED in real browser!")

        # 4. Test View 2: Speech to Text (STT Studio)
        print("\n--- TEST: STT Studio Interaction ---")
        await browser.evaluate("window.switchView('stt-studio')")
        await asyncio.sleep(0.5)

        # Choose preloaded clip mode via tab click
        await browser.evaluate("document.getElementById('stt-tab-clip').click()")
        await asyncio.sleep(0.3)

        clip_options = await browser.evaluate("document.getElementById('stt-clip-select').options.length")
        print(f"[STT Studio] Preloaded clips in dropdown: {clip_options}")
        assert clip_options > 1, "Clips dropdown was not populated"

        # Select first valid clip
        await browser.evaluate("document.getElementById('stt-clip-select').selectedIndex = 1")
        selected_clip = await browser.evaluate("document.getElementById('stt-clip-select').value")
        print(f"[STT Studio] Selected clip ID: '{selected_clip}'")

        # Submit transcription
        print("[STT Studio] Submitting transcription request...")
        await browser.evaluate("document.getElementById('stt-studio-form').dispatchEvent(new Event('submit'))")
        await asyncio.sleep(2.0)

        stt_hidden = await browser.evaluate("document.getElementById('stt-output-card').classList.contains('hidden')")
        transcript_text = await browser.evaluate("document.getElementById('stt-output-text').textContent")
        stt_dur_text = await browser.evaluate("document.getElementById('stt-stat-dur').textContent")
        stt_words_text = await browser.evaluate("document.getElementById('stt-stat-words').textContent")

        print(f"[STT Studio] Output Card Hidden: {stt_hidden}")
        print(f"[STT Studio] Transcript: '{transcript_text[:60]}...'")
        print(f"[STT Studio] Duration Display: '{stt_dur_text}'")
        print(f"[STT Studio] Word Count: '{stt_words_text}'")

        assert not stt_hidden, "STT output card remained hidden after transcription!"
        assert len(transcript_text) > 0, "Empty transcript returned!"
        assert "s" in stt_dur_text and not stt_dur_text.startswith("undefined"), f"Invalid STT duration display: {stt_dur_text}"
        print("✓ STT Studio workflow PASSED in real browser!")

        # 5. Test View 4: Live Speech Playground (WebSocket In-Browser Lifecycle)
        print("\n--- TEST: Live Speech Playground (WebSocket In-Browser Lifecycle) ---")
        await browser.evaluate("window.switchView('live-playground')")
        await asyncio.sleep(0.5)

        ws_badge_text = await browser.evaluate("document.getElementById('ws-status-badge')?.textContent || ''")
        print(f"[Live Playground] Connection Badge: '{ws_badge_text.strip()}'")
        assert "Connected" in ws_badge_text, f"WebSocket was not connected: '{ws_badge_text}'"

        # Send an empty stop signal over browser WebSocket to test server handling & negative verification
        ws_test_result = await browser.evaluate("""
            new Promise((resolve) => {
                const sock = window.speechSocket;
                if (!sock || sock.readyState !== WebSocket.OPEN) {
                    resolve({ success: false, reason: 'socket_not_open' });
                    return;
                }
                const handler = (evt) => {
                    try {
                        const data = JSON.parse(evt.data);
                        if (data.type === 'operation_failed' && data.error_code === 'EMPTY_BUFFER') {
                            sock.removeEventListener('message', handler);
                            resolve({ success: true, received: data });
                        }
                    } catch (e) {}
                };
                sock.addEventListener('message', handler);
                sock.send(JSON.stringify({ action: 'stop' }));
                setTimeout(() => resolve({ success: false, reason: 'timeout' }), 4000);
            })
        """)
        print(f"[Live Playground] Empty Buffer Rejection Event: {ws_test_result}")
        assert ws_test_result.get("success"), f"Failed WebSocket negative test in browser: {ws_test_result}"
        print("✓ Live Speech Playground WebSocket lifecycle PASSED in real browser!")

        # 6. Test View 5: Payment Follow-up Assistant
        print("\n--- TEST: Payment Follow-up Assistant Interaction ---")
        await browser.evaluate("window.switchView('followup-desk')")
        await asyncio.sleep(0.5)

        chips_count = await browser.evaluate("document.querySelectorAll('#flw-scenario-chips .scenario-chip').length")
        print(f"[Follow-up Desk] Scenario chips loaded: {chips_count}")
        assert chips_count > 0, "No scenario chips rendered"

        # Click first chip
        await browser.evaluate("document.querySelector('#flw-scenario-chips .scenario-chip').click()")
        await asyncio.sleep(0.3)

        # Click Process
        print("[Follow-up Desk] Clicking 'Process & Extract Commitments'...")
        await browser.evaluate("document.getElementById('flw-btn-process').click()")
        await asyncio.sleep(1.5)

        review_hidden = await browser.evaluate("document.getElementById('flw-review-card').classList.contains('hidden')")
        cust_val = await browser.evaluate("document.getElementById('flw-customer-name').value")
        amt_val = await browser.evaluate("document.getElementById('flw-amount-input').value")
        print(f"[Follow-up Desk] Review Card Hidden: {review_hidden}, Customer: '{cust_val}', Amount: '{amt_val}'")
        assert not review_hidden, "Follow-up review card was not revealed!"

        # Operator verification checkbox
        print("[Follow-up Desk] Checking operator verification checkbox...")
        await browser.evaluate("document.getElementById('flw-chk-confirm').checked = true; document.getElementById('flw-chk-confirm').dispatchEvent(new Event('change'))")
        btn_confirm_disabled = await browser.evaluate("document.getElementById('flw-btn-confirm-step').disabled")
        assert not btn_confirm_disabled, "Confirm step button remained disabled after checking verification"

        # Click Confirm step
        print("[Follow-up Desk] Proceeding to reminder synthesis card...")
        await browser.evaluate("document.getElementById('flw-btn-confirm-step').click()")
        await asyncio.sleep(0.5)

        synth_hidden = await browser.evaluate("document.getElementById('flw-synthesis-card').classList.contains('hidden')")
        flw_voice_val = await browser.evaluate("document.getElementById('flw-voice-select').value")
        print(f"[Follow-up Desk] Synthesis Card Hidden: {synth_hidden}, Voice: '{flw_voice_val}'")
        assert not synth_hidden, "Synthesis card not visible"
        assert flw_voice_val in ("Pranav", "Kaveri"), f"Unexpected voice value in follow-up desk: {flw_voice_val}"

        # Click Synthesize Reminder
        print("[Follow-up Desk] Clicking 'Synthesize & Issue Reminder Notice'...")
        await browser.evaluate("document.getElementById('flw-btn-synthesize').click()")
        await asyncio.sleep(2.0)

        flw_audio_src = await browser.evaluate("document.getElementById('flw-audio-player').src")
        print(f"[Follow-up Desk] Audio Player Src: '{flw_audio_src[:60]}...'")
        assert flw_audio_src.startswith("blob:") or "followup_reminder" in flw_audio_src, f"Audio player was not populated: {flw_audio_src}"

        # Verify Follow-up Desk Audit Table rendered historical rows from SQLite
        flw_history_rows = await browser.evaluate("document.querySelectorAll('#flw-history-tbody tr').length")
        print(f"[Follow-up Desk] Audit History Table Rows: {flw_history_rows}")
        assert flw_history_rows >= 1, "Follow-up Desk audit table did not render database records!"
        print("✓ Payment Follow-up Assistant workflow PASSED in real browser!")

        # 6. Test View 8: My Recordings (History & Audio playback)
        print("\n--- TEST: My Recordings (Audio History) ---")
        await browser.evaluate("window.switchView('history')")
        await asyncio.sleep(1.0)

        rows_count = await browser.evaluate("document.querySelectorAll('#history-table-body tr').length")
        table_html = await browser.evaluate("document.getElementById('history-table-body').innerHTML")
        has_empty_message = "No history records found yet" in table_html
        play_buttons = await browser.evaluate("document.querySelectorAll('#history-table-body .history-play-btn').length")

        print(f"[My Recordings] Rows in table: {rows_count}")
        print(f"[My Recordings] Shows empty message: {has_empty_message}")
        print(f"[My Recordings] Audio Play buttons count: {play_buttons}")

        assert not has_empty_message, "My Recordings displays empty message even after running STT, TTS and Followup operations!"
        assert rows_count >= 3, f"Expected at least 3 history rows, found {rows_count}"
        assert play_buttons > 0, "No play audio buttons rendered in My Recordings"

        # Click first play button
        print("[My Recordings] Clicking first '▶ Play' button...")
        await browser.evaluate("document.querySelector('#history-table-body .history-play-btn').click()")
        await asyncio.sleep(0.5)

        # Verify Export CSV button
        export_href = await browser.evaluate("document.getElementById('history-export-btn')?.getAttribute('href')")
        print(f"[My Recordings] Export CSV Button Href: '{export_href}'")
        assert export_href == "/api/history?format=csv", f"Unexpected export CSV href: {export_href}"

        # Verify Delete buttons
        delete_buttons = await browser.evaluate("document.querySelectorAll('#history-table-body .history-delete-btn').length")
        print(f"[My Recordings] Delete buttons count: {delete_buttons}")
        assert delete_buttons > 0, "No delete buttons found in My Recordings"

        global_audio_src = await browser.evaluate("document.getElementById('history-global-audio')?.src")
        print(f"[My Recordings] Global audio player loaded: {global_audio_src}")
        assert global_audio_src and "/api/audio/" in global_audio_src, "Global audio player did not load audio file!"

        # Verify decoding status of global audio element
        global_audio_status = await browser.evaluate("""
            (() => {
                const el = document.getElementById('history-global-audio');
                return {
                    readyState: el ? el.readyState : 0,
                    error: (el && el.error) ? el.error.message : null
                };
            })()
        """)
        print(f"[My Recordings] Global audio readyState: {global_audio_status.get('readyState')}")
        assert global_audio_status.get("error") is None, f"Global audio decoding error: {global_audio_status.get('error')}"
        print("✓ My Recordings workflow PASSED in real browser!")

        # 7. Check for Console Errors
        print("\n--- CONSOLE EXCEPTION AUDIT ---")
        print(f"Total console error entries: {len(browser.console_errors)}")
        for err in browser.console_errors:
            print(f"  [Console Error] {err}")

        # Filter out benign warnings like favicon 404
        fatal_errors = [e for e in browser.console_errors if "favicon" not in e.lower() and "404" not in e]
        print(f"Fatal uncaught JS errors: {len(fatal_errors)}")
        assert len(fatal_errors) == 0, f"Uncaught JavaScript exceptions detected in browser: {fatal_errors}"

        await browser.close()
        print("\n==================================================")
        print("ALL BROWSER WORKFLOWS PASSED WITH 0 ERRORS!")
        print("==================================================")

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()


if __name__ == "__main__":
    asyncio.run(run_e2e_audit())
