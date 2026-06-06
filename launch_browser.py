from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir="/home/krawin/exp.code/python-l/Leads/playwright_whatsapp_profile",
        headless=False,
        channel="chromium",
        args=["--no-sandbox"],
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    page.goto("about:blank")
    input("Press Enter to close...")
    browser.close()
