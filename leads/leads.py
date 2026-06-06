import sys
import csv
import time
from playwright.sync_api import sync_playwright

def get_user_input():
    print("\n🗺️  Google Maps Lead Hunter")
    print("=" * 35)
    location = input("Enter location (city or area): ").strip()
    business_type = input("Enter business type (e.g. restaurant, pharmacy): ").strip()

    if not location or not business_type:
        print("❌ Both fields are required.")
        sys.exit(1)

    return location, business_type

def build_search_url(location, business_type):
    query = f"{business_type} in {location}"
    encoded = query.replace(" ", "+")
    url = f"https://www.google.com/maps/search/{encoded}"
    return url, query

def scroll_and_collect_links(page):
    """Scroll the results panel and collect all listing links."""
    PANEL_SELECTOR = 'div[role="feed"]'

    print("⏳ Waiting for results panel...")
    try:
        page.wait_for_selector(PANEL_SELECTOR, timeout=12000)
        print("✅ Results panel found!")
    except:
        print("❌ Could not find results panel.")
        return []

    links_found = set()
    no_new_count = 0
    scroll_num = 0
    MAX_SCROLLS = 20

    print("🔄 Scrolling through results...\n")

    while scroll_num < MAX_SCROLLS:
        anchors = page.query_selector_all('a[href*="/maps/place/"]')
        before = len(links_found)

        for a in anchors:
            href = a.get_attribute("href")
            if href and "/maps/place/" in href:
                full_url = href.split("?")[0]
                if full_url.startswith("/"):
                    full_url = "https://www.google.com" + full_url
                links_found.add(full_url)

        after = len(links_found)
        new_found = after - before
        print(f"  Scroll {scroll_num + 1:>2} | listings: {after:>3}  (+{new_found} new)")

        # Check if the "end of list" text is visible on the page
        end_text_el = page.query_selector('text="You\'ve reached the end of the list."')
        if end_text_el:
            print("✅ Reached end of listings (found 'You've reached the end of the list' text).\n")
            break

        panel = page.query_selector(PANEL_SELECTOR)
        if panel:
            # Scroll to the absolute bottom to trigger lazy loading reliably
            panel.evaluate("el => el.scrollTo(0, el.scrollHeight)")
        
        page.wait_for_timeout(2000)

        if new_found == 0:
            no_new_count += 1
            if no_new_count >= 3:
                print("✅ Reached end of listings (no new items found).\n")
                break
        else:
            no_new_count = 0

        scroll_num += 1

    return list(links_found)

def check_listing(page, url, index, total):
    """
    Open a listing, check if it has a website.
    If NO website → grab phone number and return it.
    If has website → skip.
    """
    try:
        # Load the details page using DOMContentLoaded for speed
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        # ── Get business name ──
        name = "Unknown"
        try:
            name_el = page.query_selector('h1')
            if name_el:
                name = name_el.inner_text().strip()
        except:
            pass

        print(f"  [{index}/{total}] {name}")

        # ── Check for website link ──
        has_website = False
        try:
            website_el = page.query_selector('a[data-item-id="authority"], a[aria-label^="Website:"]')
            if website_el:
                has_website = True
        except:
            pass

        if has_website:
            print(f"         ↳ Has website — skipping")
            return None

        # ── No website — look for phone number ──
        phone = None
        try:
            phone_el = page.query_selector('[data-item-id^="phone:tel:"], [aria-label^="Phone:"]')
            if phone_el:
                aria_label = phone_el.get_attribute("aria-label") or ""
                if aria_label.startswith("Phone:"):
                    phone = aria_label.replace("Phone:", "").strip()
                else:
                    phone = aria_label.strip() or phone_el.inner_text().strip()
        except:
            pass

        if phone:
            print(f"         ↳ ✅ No website | Phone: {phone}")
            return {"name": name, "phone": phone, "maps_url": url}
        else:
            print(f"         ↳ ⚠️  No website & no phone found")
            return None

    except Exception as e:
        print(f"         ↳ ❌ Error: {e}")
        return None

def save_to_csv(leads, location, business_type):
    filename = f"leads_{business_type}_{location}.csv".replace(" ", "_").lower()
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "phone", "maps_url"])
        writer.writeheader()
        writer.writerows(leads)
    return filename

def main():
    is_cli = len(sys.argv) > 2
    headless_mode = False

    if is_cli:
        location = sys.argv[1]
        business_type = sys.argv[2]
        if "--headless" in sys.argv:
            headless_mode = True
    else:
        location, business_type = get_user_input()

    url, query = build_search_url(location, business_type)

    print(f"\n🔍 Searching: \"{query}\"", flush=True)
    print(f"🌐 URL: {url}\n", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless_mode,
            slow_mo=200,
            channel="chromium",
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        
        # ── Fast Page Loading Optimization ──
        # Route to block images, media, and fonts to speed up load times by 3-5x
        def block_unnecessary_resources(route):
            if route.request.resource_type in ["image", "media", "font"]:
                route.abort()
            else:
                route.continue_()
        
        context.route("**/*", block_unnecessary_resources)
        
        page = context.new_page()

        # ── Step 1: Load search results ──
        print("⏳ Opening Google Maps...", flush=True)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        print("✅ Page loaded.\n", flush=True)

        # ── Step 2: Scroll and collect all listing URLs ──
        links = scroll_and_collect_links(page)
        total = len(links)
        print(f"📋 Found {total} listings. Now checking each one...\n", flush=True)
        print("-" * 50, flush=True)

        # ── Step 3: Visit each listing, check website, grab phone ──
        leads = []
        for i, link in enumerate(links, 1):
            result = check_listing(page, link, i, total)
            if result:
                leads.append(result)
            time.sleep(0.5)  # small pause between requests

        # ── Step 4: Save results ──
        print("\n" + "=" * 50, flush=True)
        print(f"🎯 Done! {len(leads)} leads found (no website + has phone)", flush=True)

        if leads:
            filename = save_to_csv(leads, location, business_type)
            print(f"💾 Saved to: {filename}", flush=True)
            print("\n📞 Leads:", flush=True)
            for lead in leads:
                print(f"   • {lead['name']} → {lead['phone']}", flush=True)
        else:
            print("😕 No leads found matching criteria.", flush=True)

        if not is_cli:
            input("\nPress ENTER to close the browser...")
        browser.close()

if __name__ == "__main__":
    main()