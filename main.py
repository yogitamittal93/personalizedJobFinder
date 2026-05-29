import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv  
load_dotenv()  

from scraper import scrape_portfolio, scout_hidden_gems
from evaluator import evaluate_and_prioritize
from playwright.sync_api import sync_playwright

# Load API keys and environment configurations

# --- Configuration ---
PORTFOLIO_URL = "https://portfolio-three-sigma-mp0vvhcq3h.vercel.app/"  
CANDIDATE_DATA = {
    "full_name": "Yogita Singla",
    "email": "yogitamittal.tech@gmail.com",
    "portfolio": PORTFOLIO_URL
}

# --- DB Initialization ---
def init_db():
    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            title TEXT,
            url TEXT UNIQUE,
            salary_culture_tier INTEGER,
            match_score INTEGER,
            status TEXT DEFAULT 'Scouted',
            interview_process TEXT,
            prep_plan TEXT
        )
    ''')
    conn.commit()
    conn.close()

def send_email_update(message_body: str):
    """Sends a free email notification tracking dashboard statuses and interview plans with robust failover."""
    sender_emails = ["yogitasingla93@gmail.com", "yogitasinglamittal@gmail.com", "yogitamittal.tech@gmail.com"]
    receiver_emails = ["yogitasingla93@gmail.com", "yogitasinglamittal@gmail.com", "yogitamittal.tech@gmail.com"]
    
    # Ingest candidate profile if available to fetch custom emails
    if os.path.exists("candidate_profile.json"):
        try:
            with open("candidate_profile.json", "r", encoding="utf-8") as f:
                prof = json.load(f)
                p_email = prof.get("personal_info", {}).get("email")
                if p_email and p_email not in sender_emails:
                    sender_emails.append(p_email)
                if p_email and p_email not in receiver_emails:
                    receiver_emails.append(p_email)
        except Exception:
            pass

    # Gather potential app passwords and clean spaces and quotes
    passwords = []
    p1 = os.getenv("EMAIL_APP_PASSWORD", "")
    p2 = os.getenv("EMAIL_APP_PASSWORD2", "")
    
    for p in [p1, p2]:
        if p:
            cleaned = p.replace(" ", "").replace('"', '').replace("'", "").strip()
            if cleaned and cleaned not in passwords:
                passwords.append(cleaned)
            # Also keep raw just in case
            raw = p.strip()
            if raw and raw not in passwords:
                passwords.append(raw)
                
    if not passwords:
        passwords = ["your_fallback_app_password"]

    msg = MIMEText(message_body)
    msg['Subject'] = '🚀 GlobalJobAgent Sync Status Update'
    msg['To'] = ", ".join(receiver_emails)
    
    # Try multiple login combinations (Account Rotation, Port Failover, Password Failover)
    for sender in sender_emails:
        for pwd in passwords:
            # 1. Try Port 465 SSL
            try:
                msg['From'] = sender
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(sender, pwd)
                    server.sendmail(sender, receiver_emails, msg.as_string())
                print(f"📧 Operational update transmitted directly to your inbox via {sender} (Port 465 SSL)!")
                return
            except smtplib.SMTPAuthenticationError:
                # Password incorrect for this specific account, try next pwd
                continue
            except Exception as e:
                # Network or connection error, fall back to Port 587 STARTTLS
                pass
                
            # 2. Try Port 587 STARTTLS
            try:
                msg['From'] = sender
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(sender, pwd)
                server.sendmail(sender, receiver_emails, msg.as_string())
                server.quit()
                print(f"📧 Operational update transmitted directly to your inbox via {sender} (Port 587 STARTTLS)!")
                return
            except smtplib.SMTPAuthenticationError:
                # Password incorrect, try next pwd
                continue
            except Exception as e:
                # Try next configuration
                continue
                
    print("❌ Failed all SMTP authentication configurations. Please check App Passwords in your local .env.")

def interactive_apply_node(job_url: str):
    """Launches an interactive browser, auto-fills standard details, and pauses for your click."""
    print(f"\n[Agent Action] Opening: {job_url}")
    print("🤖 The agent is launching a secure browser window. Review and complete the form.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        page = browser.new_page()
        page.goto(job_url)
        
        # Pre-fill fields if they map to standard document patterns
        try:
            page.locator("input[name*='name']").first.fill(CANDIDATE_DATA['full_name'])
            page.locator("input[type='email']").first.fill(CANDIDATE_DATA['email'])
            page.locator("input[name*='url'], input[name*='portfolio']").first.fill(CANDIDATE_DATA['portfolio'])
        except Exception:
            pass
            
        input("\n👉 PROMPT: Review, edit, and click 'SUBMIT' on the web page. Once submitted successfully, hit ENTER here to log it...")
        browser.close()
    return "Applied"

def main():
    init_db()
    print("🔍 Scraping candidate portfolio metrics...")
    portfolio_text = scrape_portfolio(PORTFOLIO_URL)
    
    print("🚀 Scouting hidden, premium global-remote listings...")
    listings = scout_hidden_gems()
    print(f"Found {len(listings)} high-potential worldwide listings.")
    
    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()
    
    for job in listings:
        cursor.execute("SELECT id FROM jobs WHERE url=?", (job['url'],))
        if cursor.fetchone():
            continue # Skip roles we've already parsed
            
        print(f"\nEvaluating: {job['company']} - {job['title']}")
        analysis = evaluate_and_prioritize(job, portfolio_text)
        
        if analysis['match_score'] >= 80: 
            cursor.execute('''
                INSERT OR IGNORE INTO jobs (company, title, url, salary_culture_tier, match_score, interview_process, prep_plan, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Scouted')
            ''', (job['company'], job['title'], job['url'], analysis['tier'], analysis['match_score'], analysis['interview_process'], analysis['prep_plan']))
            conn.commit()
            
            # Launch Browser & Pause for manual confirmation
            status = interactive_apply_node(job['url'])
            
            if status == "Applied":
                cursor.execute("UPDATE jobs SET status='Applied' WHERE url=?", (job['url'],))
                conn.commit()
                
                # Fetch instant tracking matrix counts
                cursor.execute("SELECT COUNT(*) FROM jobs WHERE status='Applied'")
                applied_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM jobs WHERE status='Scouted'")
                backlog_count = cursor.fetchone()[0]
                
                # Send structured real-time alert updates to your email
                alert = (
                    f"🚀 *Application Logged Successfully!*\n\n"
                    f"🏢 *Company:* {job['company']}\n"
                    f"💼 *Role:* {job['title']}\n"
                    f"📊 *Dashboard:* {applied_count} Total Applied | {backlog_count} in Backlog\n\n"
                    f"📋 *Interview Stages Pattern:*\n{analysis['interview_process']}\n\n"
                    f"🧠 *AI Target Prep Plan:*\n{analysis['prep_plan']}"
                )
                send_email_update(alert)
                
    conn.close()
    print("\n🎉 Pipeline sync loop completed successfully.")

if __name__ == "__main__":
    main()