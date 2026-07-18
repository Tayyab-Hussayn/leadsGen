from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import subprocess
import threading
import shutil
import sys
import os
import csv
import json
import re
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Create OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://opencode.ai/zen/v1/"
)

# Chat history stored in memory
chat_history = [
    {
        "role": "system",
        "content": """You are a helpful coding assistant named **Axon**.

YOUR IDENTITY:
- Your name is: **Axon**
- You were created by: **Ayesha & Tayyab ** ❤️
- Your purpose is: To help beginner Python and web development students learn coding easily, and assist with lead outreach templates.
- Your personality: Friendly, patient, and encouraging

# ABOUT THE USER:
- User is a Professional senior-level software and web developer
- He builds projects like chatbots to practice Python and does client outreach for lead generation.

 YOUR TONE & STYLE:
- Be friendly, encouraging, and patient
- Use simple language, avoid heavy jargon
- When explaining code, break it down step by step
- Format replies cleanly using emojis and sections
- Use dividers and section headers

IDENTITY RULE (IMPORTANT!)
If anyone asks who made you, always reply:
➤ "I was created by Ayesha & Tayyab"

END EVERY RESPONSE WITH:
Always finish with:
Tip of the Message:
[One practical coding/web dev or business outreach tip — 1-2 sentences]"""
    }
]

# -----------------------------------------------------------------------------
# BACKGROUND TASK MANAGER
# -----------------------------------------------------------------------------

class BackgroundTask:
    def __init__(self, name):
        self.name = name
        self.process = None
        self.status = "idle" # idle, running, completed, stopped, failed
        self.logs = []
        self.progress = {
            "current": 0,
            "total": 0,
            "percentage": 0,
            "status_text": "Not started"
        }
        self.thread = None
        self.lock = threading.Lock()

    def add_log(self, line):
        with self.lock:
            # Strip ANSI escape codes
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_line = ansi_escape.sub('', line)
            self.logs.append(clean_line)
            if len(self.logs) > 800:
                self.logs.pop(0)

    def start(self, cmd, cwd=".", on_progress_parse=None):
        with self.lock:
            if self.status == "running":
                return False, "Task is already running"
            
            self.status = "running"
            self.logs = []
            self.progress = {
                "current": 0,
                "total": 0,
                "percentage": 0,
                "status_text": "Initializing process..."
            }

        def run():
            try:
                self.process = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=os.environ.copy()
                )

                for line in self.process.stdout:
                    clean_line = line.strip()
                    if not clean_line:
                        continue
                    self.add_log(clean_line)
                    
                    if on_progress_parse:
                        with self.lock:
                            on_progress_parse(clean_line, self.progress)

                self.process.wait()
                exit_code = self.process.returncode
                
                with self.lock:
                    if self.status == "running":
                        if exit_code == 0:
                            self.status = "completed"
                            self.progress["percentage"] = 100
                            self.progress["status_text"] = "Task completed successfully"
                        else:
                            self.status = "failed"
                            self.progress["status_text"] = f"Task failed with exit code {exit_code}"
            except Exception as e:
                with self.lock:
                    self.status = "failed"
                    self.add_log(f"Process Error: {str(e)}")
                    self.progress["status_text"] = f"Error: {str(e)}"

        self.thread = threading.Thread(target=run)
        self.thread.daemon = True
        self.thread.start()
        return True, "Task started successfully"

    def stop(self):
        with self.lock:
            if self.status != "running":
                return False, "Task is not running"
            
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        self.process.kill()
                    except:
                        pass
                except Exception as e:
                    self.add_log(f"Error terminating process: {e}")
            
            self.status = "stopped"
            self.progress["status_text"] = "Stopped by user"
            return True, "Task stopped by user"

    def get_state(self):
        with self.lock:
            return {
                "status": self.status,
                "logs": self.logs,
                "progress": self.progress
            }

class WhatsAppLoginTask:
    def __init__(self):
        self.process = None
        self.qr_code_text = ""
        self.status = "idle" # idle, waiting_qr, logged_in, failed
        self.thread = None
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            if self.status == "waiting_qr":
                return False, "Login already in progress"
            self.status = "waiting_qr"
            self.qr_code_text = "Initializing Playwright browser login..."
            
            # Clean up old QR code image
            qr_img = "./static/whatsapp_qr.png"
            if os.path.exists(qr_img):
                try:
                    os.remove(qr_img)
                except:
                    pass

        def run():
            try:
                python_exe = sys.executable if sys.executable else "python3"
                cmd = [python_exe, "-u", "leads/whatsapp_link.py"]
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=os.environ.copy()
                )

                for line in self.process.stdout:
                    line_lower = line.lower()
                    if "success: authenticated" in line_lower:
                        with self.lock:
                            self.status = "logged_in"
                            self.qr_code_text = "Authenticated"
                    elif "error" in line_lower:
                        with self.lock:
                            # Don't overwrite if already stopped by user
                            if self.status not in ("idle", "logged_in"):
                                self.status = "failed"
                                self.qr_code_text = f"Failed: {line.strip()}"
                    elif "qr_update" in line_lower:
                        with self.lock:
                            self.qr_code_text = f"QR_READY_{int(time.time())}"

                # Process finished — only mark failed if not already handled
                proc = self.process
                if proc is not None:
                    proc.wait()
                with self.lock:
                    if self.status == "waiting_qr":
                        # Timed out without success
                        self.status = "failed"
                        self.qr_code_text = "QR code expired. Please try again."
            except Exception as e:
                with self.lock:
                    if self.status not in ("idle", "logged_in"):
                        self.status = "failed"
                        self.qr_code_text = f"Error starting login: {e}"

        self.thread = threading.Thread(target=run)
        self.thread.daemon = True
        self.thread.start()
        return True, "Login process initiated"

    def stop(self):
        with self.lock:
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        self.process.kill()
                        self.process.wait(timeout=2)
                    except:
                        pass
                except:
                    pass
                finally:
                    self.process = None
            self.status = "idle"
            self.qr_code_text = ""
            return True, "Login process stopped"

    def get_state(self):
        with self.lock:
            # Check if QR image actually exists on disk
            qr_exists = os.path.exists("./static/whatsapp_qr.png")
            return {
                "status": self.status,
                "qr_code": self.qr_code_text,
                "qr_exists": qr_exists
            }

# Global task handlers
scraper_task = BackgroundTask("Scraper")
sender_task = BackgroundTask("Sender")
login_task = WhatsAppLoginTask()

# Helper parsers
def parse_scraper_progress(line, progress_dict):
    # Scroll  3 | listings:  45  (+15 new)
    scroll_match = re.search(r"Scroll\s+(\d+)\s+\|\s+listings:\s+(\d+)", line)
    if scroll_match:
        scroll_num = int(scroll_match.group(1))
        listings = int(scroll_match.group(2))
        progress_dict["status_text"] = f"Searching: Scroll {scroll_num}, found {listings} listings..."
        progress_dict["current"] = scroll_num
        progress_dict["total"] = 20 # MAX_SCROLLS

    # 📋 Found 45 listings. Now checking each one...
    found_match = re.search(r"📋 Found (\d+) listings", line)
    if found_match:
        progress_dict["total"] = int(found_match.group(1))
        progress_dict["current"] = 0
        progress_dict["status_text"] = f"Checking listings (0/{found_match.group(1)})..."

    # [5/45] Burger Joint
    checking_match = re.search(r"\[(\d+)/(\d+)\]\s+(.*)", line)
    if checking_match:
        current = int(checking_match.group(1))
        total = int(checking_match.group(2))
        name = checking_match.group(3).strip()
        progress_dict["current"] = current
        progress_dict["total"] = total
        progress_dict["percentage"] = int((current / total) * 100)
        progress_dict["status_text"] = f"Verifying [{current}/{total}]: {name}"

    # Saved to: leads_restaurant_lahore.csv
    save_match = re.search(r"Saved to:\s*(.*)", line)
    if save_match:
        progress_dict["status_text"] = f"Finished! Results saved to {save_match.group(1)}"
        progress_dict["percentage"] = 100

def parse_sender_progress(line, progress_dict):
    # PROGRESS: 2/10 | Sending to Burger Hub (0300...)
    match = re.search(r"PROGRESS:\s+(\d+)/(\d+)\s+\|\s+(.*)", line)
    if match:
        current = int(match.group(1))
        total = int(match.group(2))
        details = match.group(3).strip()
        progress_dict["current"] = current
        progress_dict["total"] = total
        progress_dict["percentage"] = int((current / total) * 100)
        progress_dict["status_text"] = f"Outreach queue [{current}/{total}]: {details}"

# Helper to check WhatsApp login state based on persistent profile directory
def check_whatsapp_status():
    """
    Determine WhatsApp Web auth state by inspecting the IndexedDB that WhatsApp
    Web writes authentication keys into.  An unauthenticated (QR-scan pending)
    profile contains only a tiny log file (<20 KB).  A fully authenticated
    session writes hundreds of KB of IndexedDB data.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    idb_path = os.path.join(
        base_dir,
        "playwright_whatsapp_profile",
        "Default",
        "IndexedDB",
        "https_web.whatsapp.com_0.indexeddb.leveldb"
    )
    logged_in = False
    if os.path.isdir(idb_path):
        # Sum up all file sizes inside the leveldb directory
        total_bytes = sum(
            os.path.getsize(os.path.join(idb_path, f))
            for f in os.listdir(idb_path)
            if os.path.isfile(os.path.join(idb_path, f))
        )
        # Authenticated sessions exceed 50 KB; empty profiles stay under 20 KB
        logged_in = total_bytes > 50_000
    return {"connected": logged_in, "logged_in": logged_in}

def whatsapp_logout():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, "playwright_whatsapp_profile")

    # Remove QR image if present
    qr_img = os.path.join(base_dir, "static", "whatsapp_qr.png")
    if os.path.exists(qr_img):
        try:
            os.remove(qr_img)
        except:
            pass

    if os.path.exists(profile_dir):
        # Give the browser subprocess time to release file locks
        time.sleep(1.5)
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception as e:
            print(f"Warning: profile cleanup error (ignored): {e}", flush=True)
    return True

# -----------------------------------------------------------------------------
# CHATBOT API ROUTES
# -----------------------------------------------------------------------------

from flask import send_file

@app.route("/")
def home():
    if os.path.exists("index.html"):
        return send_file("index.html")
    return "Axon Backend Agent is running"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400
        
    chat_history.append(
        {"role": "user", "content": user_message}
    )

    if len(chat_history) > 15:
        del chat_history[1:-14]

    models = ["nemotron-3-super-free", "minimax-m2.5-free", "qwen3.6-plus-free", "deepseek-v4-flash-free"]
    response = None
    last_error = None
    
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=chat_history
            )
            break
        except Exception as e:
            last_error = e
            print(f"Model {model} failed: {e}")
            continue

    if response is None:
        return jsonify({"error": f"All models failed. Last error: {str(last_error)}"}), 500
    
    ai_reply = response.choices[0].message.content

    chat_history.append({
        "role": "assistant",
        "content": ai_reply
    })

    return jsonify({"reply": ai_reply})

# -----------------------------------------------------------------------------
# LEAD SCRAEPER / HUNTER API ROUTES
# -----------------------------------------------------------------------------

@app.route("/api/leads/hunt", methods=["POST"])
def hunt_leads():
    data = request.json or {}
    location = data.get("location", "").strip()
    business_type = data.get("business_type", "").strip()
    headless = data.get("headless", True)
    
    if not location or not business_type:
        return jsonify({"error": "Location and Business Type are required"}), 400
        
    python_exe = sys.executable if sys.executable else "python3"
    cmd = [python_exe, "-u", "leads/leads.py", location, business_type]
    if headless:
        cmd.append("--headless")
        
    success, msg = scraper_task.start(
        cmd, 
        cwd=".", 
        on_progress_parse=parse_scraper_progress
    )
    if success:
        return jsonify({"message": msg, "status": "running"})
    else:
        return jsonify({"error": msg}), 400

@app.route("/api/leads/status", methods=["GET"])
def get_scraper_status():
    return jsonify(scraper_task.get_state())

@app.route("/api/leads/stop", methods=["POST"])
def stop_scraper():
    success, msg = scraper_task.stop()
    if success:
        return jsonify({"message": msg})
    else:
        return jsonify({"error": msg}), 400

@app.route("/api/leads/history", methods=["GET"])
def get_leads_history():
    history = []
    # Search root and leads/ directory for CSV files starting with 'leads_'
    dirs_to_check = [".", "leads"]
    for d in dirs_to_check:
        if not os.path.exists(d):
            continue
        try:
            for file in os.listdir(d):
                if file.startswith("leads_") and file.endswith(".csv"):
                    full_path = os.path.join(d, file)
                    stat = os.stat(full_path)
                    
                    # Count rows
                    count = 0
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            count = sum(1 for line in f) - 1
                    except:
                        pass
                        
                    history.append({
                        "name": file,
                        "path": full_path,
                        "size_bytes": stat.st_size,
                        "last_modified": stat.st_mtime,
                        "leads_count": count if count >= 0 else 0
                    })
        except Exception as e:
            print(f"Error checking directory {d}: {e}")
            
    history.sort(key=lambda x: x["last_modified"], reverse=True)
    return jsonify(history)

@app.route("/api/leads/view", methods=["GET"])
def view_leads_csv():
    file_path = request.args.get("path", "")
    if not file_path:
        return jsonify({"error": "No file path provided"}), 400
    
    abs_path = os.path.abspath(file_path)
    workspace_dir = os.path.abspath(".")
    if not abs_path.startswith(workspace_dir):
        return jsonify({"error": "Access denied"}), 403
        
    if not os.path.exists(abs_path):
        return jsonify({"error": "File not found"}), 404
        
    leads = []
    try:
        with open(abs_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                leads.append(row)
        return jsonify({
            "name": os.path.basename(abs_path),
            "path": file_path,
            "leads": leads
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# WHATSAPP OUTREACH CAMPAIGN API ROUTES
# -----------------------------------------------------------------------------

@app.route("/api/sender/start", methods=["POST"])
def start_sender():
    data = request.json or {}
    csv_file = data.get("csv_file", "").strip()
    message_1 = data.get("message_1", "").strip()
    message_2 = data.get("message_2", "").strip()
    
    if not csv_file or not message_1 or not message_2:
        return jsonify({"error": "CSV File, Message 1, and Message 2 are required"}), 400
        
    if not os.path.exists(csv_file):
        return jsonify({"error": f"CSV file '{csv_file}' not found"}), 404
        
    # Check if WhatsApp client is logged in
    status = check_whatsapp_status()
    if not status.get("logged_in"):
        return jsonify({"error": "WhatsApp Web session is not linked. Please scan the QR code first."}), 400

    python_exe = sys.executable if sys.executable else "python3"
    cmd = [python_exe, "-u", "leads/sender.py", csv_file, message_1, message_2]
    
    success, msg = sender_task.start(
        cmd,
        cwd=".",
        on_progress_parse=parse_sender_progress
    )
    if success:
        return jsonify({"message": msg, "status": "running"})
    else:
        return jsonify({"error": msg}), 400

@app.route("/api/sender/status", methods=["GET"])
def get_sender_status():
    return jsonify(sender_task.get_state())

@app.route("/api/sender/stop", methods=["POST"])
def stop_sender():
    success, msg = sender_task.stop()
    if success:
        return jsonify({"message": msg})
    else:
        return jsonify({"error": msg}), 400

# -----------------------------------------------------------------------------
# WHATSAPP CLI CLIENT AUTH API ROUTES
# -----------------------------------------------------------------------------

@app.route("/api/whatsapp/status", methods=["GET"])
def get_whatsapp_client_status():
    status = check_whatsapp_status()
    status["login_task"] = login_task.get_state()
    return jsonify(status)

@app.route("/api/whatsapp/login", methods=["POST"])
def start_whatsapp_login():
    success, msg = login_task.start()
    if success:
        return jsonify({"message": msg, "status": "started"})
    else:
        return jsonify({"error": msg}), 400

@app.route("/api/whatsapp/qr", methods=["GET"])
def get_whatsapp_qr():
    return jsonify(login_task.get_state())

@app.route("/api/whatsapp/logout", methods=["POST"])
def do_whatsapp_logout():
    login_task.stop()    # kill any running Playwright login subprocess
    whatsapp_logout()    # wipe profile dir and QR image (best-effort)
    return jsonify({"message": "Logged out successfully"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=False)