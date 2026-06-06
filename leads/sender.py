import csv
import sys
import os
import time
import urllib.parse
from playwright.sync_api import sync_playwright

# --- SETTINGS ---
CSV_FILE = "leads_restaurant_johar_town_lahore.csv"

MESSAGE_1 = """Assalam u Alaikum! 🙏
Umeed hai aap aur aap ka business achha chal raha hoga.
Main Tayyab hoon, web developer. Aap ka waqt zeaya nahi karoonga — seedhi baat karta hoon.
Lahore mein jo restaurants tezi se grow kar rahe hain, unka ek common factor hai — unke paas apna online ordering system hai. Foodpanda pe hona kafi nahi, kyunki wo har order ka 25–30% commission le leta hai.
Apni website pe direct order = poora paisa aap ka, apni brand aap ki.
Maine ek ready system banaya hua hai:
✅ Poora menu online — customers phone se order karein
✅ Simple admin dashboard — har order ek jagah
✅ Koi commission nahi — har sale 100% aap ki
✅ Aap ki apni identity — kisi app ki listing nahi
Agar aap ko suitable lage toh 15–20 minute ki mulaqat mein aap ka system live kar dete hain. Main khud aap ke restaurant pe aane ko tayyar hoon — aap ka koi effort nahi.
Shukriya aap ke waqt ka. Aap ka jawab mera intezaar karega. 🤝
Tayyab Hussain
Agentic Automation & Web Developer"""

MESSAGE_2 = """Aur ek baat — aap ki convenience ke liye ek live demo website pehle se tayyar kar di hai taake aap khud dekh sakein ke yeh system exactly kaise kaam karta hai.
Ek baar zaroor visit karein 👇
🌐 https://urban-restaurant.vercel.app
Yahan aap poora menu, dishes aur ordering flow dekh sakte hain — exactly waise jaise aap ke customers ko nazar aayega.
Admin dashboard bhi zaroor check karein 👇
🔐 https://urban-restaurant.vercel.app/admin
📌 Password: admin123
Yahan dekhein ge ke customer orders kaise aate hain, kaise manage hote hain — sab kuch ek jagah, clear aur organized.
Ek baar poora system khud dekh lein, phir apni rai zaroor share karein. Aap ka feedback mera intezaar karega. 🙏"""

# --- CLEAN PHONE NUMBER ---
def clean_phone(phone):
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if phone.startswith("+"):
        phone = phone[1:]
    return phone

# --- MAIN LOOP ---
if len(sys.argv) > 3:
    CSV_FILE = sys.argv[1]
    MESSAGE_1 = sys.argv[2]
    MESSAGE_2 = sys.argv[3]

print(f"Starting campaign with source: {CSV_FILE}", flush=True)

try:
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        leads_list = list(reader)
except Exception as e:
    print(f"ERROR: Could not read CSV file: {e}", flush=True)
    sys.exit(1)

total = len(leads_list)
# Resolve paths relative to script location
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
profile_dir = os.path.join(root_dir, "playwright_whatsapp_profile")

if not os.path.exists(profile_dir) or not os.listdir(profile_dir):
    print("ERROR: WhatsApp Web session is not linked. Please pair your mobile device first.", flush=True)
    sys.exit(1)

print(f"Loaded {total} leads. Initializing Playwright and loading session...", flush=True)

try:
    with sync_playwright() as p:
        print("Launching browser context...", flush=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,         # headed — prevents WhatsApp Web bans
            slow_mo=50,             # humanises timing slightly
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = context.new_page()
        page.set_default_navigation_timeout(60000)
        page.set_default_timeout(30000)
        
        print("Opening WhatsApp Web...", flush=True)
        page.goto("https://web.whatsapp.com")
        
        # Verify authenticated session is loaded
        try:
            page.wait_for_selector('div[role="navigation"], #pane-side', timeout=25000)
            print("WhatsApp Web session loaded successfully.", flush=True)
        except Exception as auth_err:
            print("ERROR: WhatsApp Web session failed to load. Please re-authenticate your mobile device.", flush=True)
            context.close()
            sys.exit(1)

        for i, row in enumerate(leads_list, 1):
            name = row["name"]
            phone = clean_phone(row["phone"])
            
            if not phone:
                print(f"PROGRESS: {i}/{total} | Skipping {name} (Empty phone number)", flush=True)
                continue

            print(f"PROGRESS: {i}/{total} | Sending to {name} ({phone})", flush=True)
            
            # Use clean url without text param to avoid url length/routing issues on reload
            target_url = f"https://web.whatsapp.com/send?phone={phone}"
            
            try:
                page.goto(target_url)
                
                # Check for either the chat input box or the invalid dialog
                input_selector = 'footer div[role="textbox"], div[contenteditable="true"][data-tab="10"]'
                
                success = False
                invalid = False
                
                for attempt in range(45):  # Wait up to 45 seconds for WhatsApp Web client to load
                    # Check if input box is loaded and visible
                    input_box = page.query_selector(input_selector)
                    if input_box and input_box.is_visible():
                        success = True
                        break
                    
                    # Check for invalid number dialog
                    dialog = page.query_selector('div[role="dialog"]')
                    if dialog:
                        dialog_text = dialog.inner_text().lower()
                        # Only treat as invalid if dialog explicitly indicates registration/phone issues
                        if any(w in dialog_text for w in ["invalid", "phone", "url", "shared", "tidak", "não", "válido", "válida", "registrado", "registered", "no es", "number"]):
                            print(f"  Phone number {phone} is not registered on WhatsApp. (Dialog: {dialog.inner_text().strip()})", flush=True)
                            ok_btn = dialog.query_selector('button') or dialog.query_selector('[role="button"]') or dialog.query_selector('div[role="button"]')
                            if ok_btn:
                                try:
                                    ok_btn.click()
                                except:
                                    pass
                            invalid = True
                            break
                    time.sleep(1)
                
                if invalid:
                    # Skip to next contact
                    continue
                
                if success:
                    # Send Message 1
                    input_box = page.query_selector(input_selector)
                    if input_box:
                        input_box.focus()
                        page.keyboard.insert_text(MESSAGE_1)
                        time.sleep(1.5)
                        
                        # Try to click Send button, fallback to Enter key
                        send_btn = (
                            page.query_selector('span[data-icon="send"]')
                            or page.query_selector('[data-icon="send"]')
                            or page.query_selector('button:has(span[data-icon="send"])')
                        )
                        if send_btn:
                            send_btn.click()
                        else:
                            page.keyboard.press("Enter")
                        print("  MSG 1 response: Sent successfully", flush=True)
                        
                        # Wait between messages
                        time.sleep(6)
                        
                        # Send Message 2
                        input_box = page.query_selector(input_selector)
                        if input_box:
                            input_box.focus()
                            page.keyboard.insert_text(MESSAGE_2)
                            time.sleep(1.5)
                            
                            send_btn = (
                                page.query_selector('span[data-icon="send"]')
                                or page.query_selector('[data-icon="send"]')
                                or page.query_selector('button:has(span[data-icon="send"])')
                            )
                            if send_btn:
                                send_btn.click()
                            else:
                                page.keyboard.press("Enter")
                            print("  MSG 2 response: Sent successfully", flush=True)
                        else:
                            print("  MSG 2 response: Error locating text input area", flush=True)
                    else:
                        print("  MSG 1 response: Error locating text input area", flush=True)
                else:
                    print("  MSG response: Timeout loading chat input box", flush=True)
                    
            except Exception as item_err:
                print(f"  ERROR sending to {name}: {item_err}", flush=True)
                
            if i < total:
                print("Waiting 15 seconds before next contact...", flush=True)
                time.sleep(15)
                
        context.close()
        print("Campaign finished successfully!", flush=True)

except Exception as global_err:
    print(f"CRITICAL ERROR during campaign: {global_err}", flush=True)
    sys.exit(1)