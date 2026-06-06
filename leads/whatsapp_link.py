import os
import sys
import time
from playwright.sync_api import sync_playwright

# The script is always invoked from the project root by Flask,
# so ./static and ./playwright_whatsapp_profile resolve correctly.

def run_login():
    # Resolve paths relative to this script's directory (works from any working directory)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    
    profile_dir = os.path.join(root_dir, "playwright_whatsapp_profile")
    static_dir = os.path.join(root_dir, "static")
    os.makedirs(static_dir, exist_ok=True)
    qr_path = os.path.join(static_dir, "whatsapp_qr.png")

    # Remove stale QR image so the frontend knows a new one is loading
    if os.path.exists(qr_path):
        try:
            os.remove(qr_path)
        except Exception as e:
            print(f"Warning: could not remove old QR image: {e}", flush=True)

    print("Initializing Playwright...", flush=True)

    try:
        with sync_playwright() as p:
            print("Launching persistent Chromium context...", flush=True)
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,          # headed — prevents WhatsApp Web bans
                slow_mo=50,              # humanises timing slightly
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 800},
            )

            page = context.new_page()
            page.set_default_navigation_timeout(60_000)
            page.set_default_timeout(30_000)

            print("Navigating to WhatsApp Web...", flush=True)
            page.goto("https://web.whatsapp.com")

            # Give the page time to settle before entering polling loop
            time.sleep(3)

            start_time = time.time()
            timeout_seconds = 180  # 3 minutes for the user to scan

            print("Monitoring login state...", flush=True)

            while time.time() - start_time < timeout_seconds:

                # ── 1. Authenticated? ──────────────────────────────────────────
                # WhatsApp Web shows a nav rail and/or a chat-list pane once signed in
                if (
                    page.query_selector('div[role="navigation"]')
                    or page.query_selector('#pane-side')
                    or page.query_selector('[data-testid="chat-list"]')
                ):
                    print("SUCCESS: Authenticated successfully", flush=True)
                    # Allow IndexedDB / cookies to flush to disk
                    time.sleep(4)
                    context.close()
                    sys.exit(0)

                # ── 2. Expired QR / reload button ─────────────────────────────
                reload_btn = (
                    page.query_selector('div[data-ref] button')
                    or page.query_selector('div[data-ref] span[data-icon="refresh"]')
                    or page.query_selector('button:has-text("Click to reload")')
                    or page.query_selector('div[data-ref] [data-testid="qr-code-refresh"]')
                )
                if reload_btn:
                    print("Refreshing expired QR code...", flush=True)
                    try:
                        reload_btn.click()
                        time.sleep(3)
                    except Exception as click_err:
                        print(f"  Reload click error (ignored): {click_err}", flush=True)

                # ── 3. Capture QR canvas ──────────────────────────────────────
                # Try progressively broader selectors
                qr_element = (
                    page.query_selector('canvas[aria-label="Scan me!"]')
                    or page.query_selector('[data-ref] canvas')
                    or page.query_selector('canvas')                     # broadest fallback
                )

                if qr_element:
                    try:
                        qr_element.screenshot(path=qr_path)
                        print(f"QR_UPDATE: {int(time.time())}", flush=True)
                    except Exception:
                        # Canvas is animating / being replaced – skip this frame
                        pass
                else:
                    # Still loading – nothing to do this iteration
                    pass

                time.sleep(2.5)

            # Timed out waiting for the user to scan
            print("ERROR: Connection timed out. Please try again.", flush=True)
            context.close()
            sys.exit(1)

    except Exception as e:
        print(f"CRITICAL ERROR in login linker: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    run_login()
