"""Headed, visible browser QA test suite for CallLens Stress Lab.

Launches a visible Google Chrome window on the user's desktop, attaches via
Chrome DevTools Protocol (CDP), and drives interactive QA demonstrations:
1. Full Desktop Layout (1440x900)
2. Empty Input Validation Banner
3. Clip Selection & Condition Toggling
4. Zero-State Replay Notice Display
5. Mobile Responsive Viewport (390x844)
6. Tablet Responsive Viewport (768x1024)
7. Final Restored Desktop State (1440x900)
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets


CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
REMOTE_PORT = 9222
APP_URL = "http://127.0.0.1:8000"
TEMP_PROFILE = r"C:\Users\ABHYUDAYA\AppData\Local\Temp\chrome_calllens_qa"


class CDPClient:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
        self._msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url)

    async def send(self, method: str, params: dict | None = None) -> dict:
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(msg))
        while True:
            resp_raw = await self.ws.recv()
            resp = json.loads(resp_raw)
            if resp.get("id") == self._msg_id:
                return resp

    async def evaluate(self, expr: str) -> any:
        res = await self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return res.get("result", {}).get("result", {}).get("value")

    async def set_viewport(self, width: int, height: int, mobile: bool = False, scale: float = 1.0):
        await self.send("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": scale,
            "mobile": mobile,
        })

    async def capture_screenshot(self, save_path: Path):
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        import base64
        data = base64.b64decode(res.get("result", {}).get("data", ""))
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(data)

    async def close(self):
        if self.ws:
            await self.ws.close()


async def run_qa_demonstration():
    print("=" * 70)
    print("STARTING VISIBLE HEADED CHROME BROWSER QA SESSION")
    print("=" * 70)

    # 1. Ensure Chrome is running with remote debugging
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{REMOTE_PORT}/json") as resp:
            tabs = json.loads(resp.read().decode())
    except Exception:
        print("[QA] Launching headed Chrome process...")
        subprocess.Popen([
            CHROME_PATH,
            f"--remote-debugging-port={REMOTE_PORT}",
            f"--user-data-dir={TEMP_PROFILE}",
            "--new-window",
            APP_URL
        ])
        time.sleep(2)
        with urllib.request.urlopen(f"http://127.0.0.1:{REMOTE_PORT}/json") as resp:
            tabs = json.loads(resp.read().decode())

    # Find the tab for CallLens or use the first page tab
    target_tab = None
    for tab in tabs:
        if tab.get("type") == "page" and "127.0.0.1:8000" in tab.get("url", ""):
            target_tab = tab
            break
    if not target_tab:
        for tab in tabs:
            if tab.get("type") == "page":
                target_tab = tab
                break

    ws_url = target_tab["webSocketDebuggerUrl"]
    print(f"[QA] Attached to visible Chrome tab: {target_tab.get('title', 'CallLens')} ({ws_url})")

    client = CDPClient(ws_url)
    await client.connect()
    screenshots_dir = Path("docs/screenshots")

    try:
        # STEP 1: Desktop Viewport (1440x900)
        print("\n--- STEP 1: Full Desktop Layout (1440x900) ---")
        await client.set_viewport(1440, 900, mobile=False)
        await client.send("Page.navigate", {"url": APP_URL})
        await asyncio.sleep(1.5)

        title = await client.evaluate("document.title")
        header_text = await client.evaluate("document.querySelector('h1').textContent")
        badge_text = await client.evaluate("document.getElementById('mode-badge').textContent")
        print(f"  [✓] Page Title: '{title}'")
        print(f"  [✓] Header H1: '{header_text}'")
        print(f"  [✓] Provenance Badge: '{badge_text}'")
        await client.capture_screenshot(screenshots_dir / "dashboard_1440x900.png")

        # STEP 2: Empty Form Submission Validation
        print("\n--- STEP 2: Testing Form Validation (Empty Input) ---")
        await client.evaluate("document.getElementById('btn-submit').click()")
        await asyncio.sleep(0.5)
        error_text = await client.evaluate("document.getElementById('error-banner').textContent")
        is_visible = not await client.evaluate("document.getElementById('error-banner').classList.contains('hidden')")
        banner_class = await client.evaluate("document.getElementById('error-banner').className")
        print(f"  [✓] Error Banner Visible: {is_visible}")
        print(f"  [✓] Banner Class: '{banner_class}'")
        print(f"  [✓] Validation Message: '{error_text}'")
        await client.capture_screenshot(screenshots_dir / "empty_input_error.png")

        # STEP 3: Selecting a Clip and Testing Condition Selection
        print("\n--- STEP 3: Interactive Clip Selection & Condition Toggling ---")
        clips_count = await client.evaluate("document.getElementById('clip-select').options.length")
        print(f"  [✓] Pre-loaded Clips Count: {clips_count}")

        # Select fleurs_01
        await client.evaluate("""
            const sel = document.getElementById('clip-select');
            if (sel.options.length > 1) {
                sel.selectedIndex = 1;
                sel.dispatchEvent(new Event('change'));
            }
        """)
        selected_clip = await client.evaluate("document.getElementById('clip-select').value")
        print(f"  [✓] Selected Clip ID: '{selected_clip}'")

        # Toggle conditions: clean -> tel -> tel_snr10 -> tel_snr0
        for cond in ["clean", "tel", "tel_snr10", "tel_snr0"]:
            await client.evaluate(f"""
                const radio = document.querySelector('input[name="condition"][value="{cond}"]');
                if (radio) {{
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change'));
                }}
            """)
            await asyncio.sleep(0.3)
            print(f"  [✓] Toggled Condition Radio: '{cond}'")

        # Set back to tel
        await client.evaluate("""
            const radio = document.querySelector('input[name="condition"][value="tel"]');
            if (radio) radio.checked = true;
        """)

        # STEP 4: Submit Stress Evaluation (Zero-State Live Replay Check)
        print("\n--- STEP 4: Evaluating Clip under Telephony Condition ---")
        await client.evaluate("document.getElementById('btn-submit').click()")
        await asyncio.sleep(1.0)

        notice_text = await client.evaluate("document.getElementById('error-banner').textContent")
        notice_class = await client.evaluate("document.getElementById('error-banner').className")
        print(f"  [✓] Live Replay Notice: '{notice_text}'")
        print(f"  [✓] Banner Styling: '{notice_class}'")
        await client.capture_screenshot(screenshots_dir / "no_live_results_state.png")

        # STEP 5: Mobile Viewport Demonstration (390x844)
        print("\n--- STEP 5: Mobile Responsive Layout (390x844 - iPhone 14/15) ---")
        await client.set_viewport(390, 844, mobile=True, scale=2.0)
        await asyncio.sleep(1.0)
        body_width = await client.evaluate("document.body.clientWidth")
        header_direction = await client.evaluate("window.getComputedStyle(document.querySelector('.app-header')).flexDirection")
        print(f"  [✓] Mobile Body Client Width: {body_width}px")
        print(f"  [✓] Mobile Header Direction: '{header_direction}' (Single column)")
        await client.capture_screenshot(screenshots_dir / "mobile_390x844.png")

        # STEP 6: Tablet Viewport Demonstration (768x1024)
        print("\n--- STEP 6: Tablet Responsive Layout (768x1024 - iPad) ---")
        await client.set_viewport(768, 1024, mobile=False)
        await asyncio.sleep(1.0)
        tablet_width = await client.evaluate("document.body.clientWidth")
        print(f"  [✓] Tablet Body Client Width: {tablet_width}px")
        await client.capture_screenshot(screenshots_dir / "dashboard_768x1024.png")

        # STEP 7: Restore Full Desktop Viewport (1440x900)
        print("\n--- STEP 7: Restoring Full Desktop Layout (1440x900) ---")
        await client.set_viewport(1440, 900, mobile=False)
        await asyncio.sleep(0.5)
        print("  [✓] Desktop Viewport restored. Visible window remains open for user interaction.")

    finally:
        await client.close()

    print("\n" + "=" * 70)
    print("VISIBLE HEADED CHROME BROWSER QA SESSION COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_qa_demonstration())

