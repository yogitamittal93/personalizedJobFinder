import os
import sys
import time
import json
import re
import sqlite3
import argparse
from datetime import datetime
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Import our modular JobCraft AI cores
from profile_manager import ingest_profile, update_learned_response
from scraper import scrape_portfolio, scout_hidden_gems, scrape_custom_job_page
from evaluator import evaluate_and_prioritize
from resume_builder import generate_tailored_resume
from intel_researcher import compile_strategy_brief
from main import interactive_apply_node, send_email_update

load_dotenv()

PORTFOLIO_URL = "https://portfolio-three-sigma-mp0vvhcq3h.vercel.app/"
CANDIDATE_DATA = {
    "full_name": "Yogita Singla",
    "email": "yogitamittal.tech@gmail.com",
    "portfolio": PORTFOLIO_URL
}

def is_role_relevant(job: dict) -> bool:
    """Pre-filters roles using keywords to respect strict Free Tier API quotas."""
    keywords = [
        "php", "next.js", "react", "wordpress", "hubspot", "laravel", "javascript", 
        "typescript", "full stack", "frontend", "front-end", "web developer", 
        "web dev", "e-commerce", "shopify", "supabase", "marketing engineer", 
        "checkout", "remote", "developer", "node", "ui", "ux", "engineer", "software"
    ]
    title_desc = (job.get('title', '') + " " + job.get('description', '')).lower()
    return any(kw in title_desc for kw in keywords)

# Rich Terminal Colors
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

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
    
    # Run self-healing schema migrations for new columns if they do not exist
    new_columns = {
        "competition_level": "TEXT DEFAULT 'Medium'",
        "growth_signals": "TEXT DEFAULT 'Medium'",
        "compensation_signals": "TEXT DEFAULT 'Tier 2'",
        "citations": "TEXT DEFAULT '[]'",
        "unknown_fields": "TEXT DEFAULT '[]'",
        "description": "TEXT DEFAULT ''"
    }
    
    for col_name, col_type in new_columns.items():
        try:
            cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            # Column already exists, bypass
            pass
            
    conn.commit()
    conn.close()

def display_dashboard():
    """Prints a beautiful, premium visual dashboard showing JobCraft AI metrics."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{BOLD}{BLUE}==========================================================================")
    print(f"   🚀  JOBCRAFT AI — ELITE AUTONOMOUS JOB APPLICATION AGENT  🚀   ")
    print(f"=========================================================================={RESET}")
    
    # 1. Fetch Profile Metrics
    profile_loaded = "❌ Unsynced"
    skills_count = 0
    experiences_count = 0
    learned_count = 0
    
    if os.path.exists("candidate_profile.json"):
        try:
            with open("candidate_profile.json", "r", encoding="utf-8") as f:
                prof = json.load(f)
                profile_loaded = f"{GREEN}✅ Synced ({prof['personal_info']['full_name']}){RESET}"
                skills_count = len(prof.get("skills", {}).get("languages", [])) + len(prof.get("skills", {}).get("frameworks", []))
                experiences_count = len(prof.get("experiences", []))
                learned_count = len(prof.get("custom_responses", {}))
        except Exception:
            profile_loaded = f"{YELLOW}⚠️ Corrupt profile JSON{RESET}"
            
    # 2. Fetch Database Metrics
    total_scouted = 0
    high_match = 0
    total_applied = 0
    
    try:
        conn = sqlite3.connect('job_tracker.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs")
        total_scouted = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE match_score >= 80")
        high_match = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'Applied'")
        total_applied = cursor.fetchone()[0]
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
        
    print(f"{BOLD}📊 PIPELINE STATUS METRICS:{RESET}")
    print(f"  Candidate Profile : {profile_loaded}")
    print(f"  Core Skills Mapped: {CYAN}{skills_count}{RESET} | Experiences: {CYAN}{experiences_count}{RESET} | Learned Responses: {GREEN}{learned_count}{RESET}")
    print(f"  Scouted Jobs      : {MAGENTA}{total_scouted}{RESET} total listed | Match Score >= 80%: {GREEN}{high_match}{RESET}")
    print(f"  Applied Status    : {GREEN}{total_applied} Applied{RESET} | Backlog Queue: {YELLOW}{high_match - total_applied}{RESET}")
    print(f"{BLUE}--------------------------------------------------------------------------{RESET}")
    
def display_menu():
    print(f"{BOLD}🛠️  OPERATIONAL MODES & ACTIONS:{RESET}")
    print(f"  {BOLD}{CYAN}1. PROFILE_MODE{RESET} — Ingest, parse, and synchronize candidate profile JSON")
    print(f"  {BOLD}{CYAN}2. DISCOVERY_MODE{RESET} — Crawl career boards & evaluate positions (Priority Ordered)")
    print(f"  {BOLD}{CYAN}3. DISCOVERY_MODE (CUSTOM){RESET} — Scrape and score a specific custom single job URL")
    print(f"  {BOLD}{CYAN}4. RESUME_MODE{RESET} — Generate tailored LaTeX resume & Alignment Audit for a role")
    print(f"  {BOLD}{CYAN}5. INTEL_MODE{RESET} — Compile Markdown application strategy & culture brief")
    print(f"  {BOLD}{CYAN}6. LEARNING_MODE{RESET} — Interactive feedback loop: resolve unknown profile fields")
    print(f"  {BOLD}{CYAN}7. APPLY_NODE{RESET} — Launch interactive browser to review & submit application")
    print(f"  {BOLD}{CYAN}8. SYSTEM_SYNC_DAILY{RESET} — Trigger automated email status summary update")
    print(f"  {BOLD}{RED}0. EXIT{RESET}")
    print(f"{BLUE}=========================================================================={RESET}")
    
def discovery_scout_mode():
    """Triggers background scraping, evaluations, and displays sorted alignments."""
    print(f"\n{BOLD}{YELLOW}📡 Launching DISCOVERY_MODE crawler...{RESET}")
    if not os.path.exists("candidate_profile.json"):
        print(f"{RED}❌ Error: You must sync the Candidate Profile first (Mode 1)!{RESET}")
        input("\nHit ENTER to return to menu...")
        return
        
    with open("candidate_profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)
        
    listings = scout_hidden_gems()
    print(f"🔍 Crawl complete. Evaluating {len(listings)} listings...")
    
    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()
    
    new_jobs = 0
    skipped_by_filter = 0
    quota_pause = False
    
    for job in listings:
        cursor.execute("SELECT id FROM jobs WHERE url=?", (job['url'],))
        if cursor.fetchone():
            continue
            
        # 1. Quota pre-filtering based on candidate relevance
        if not is_role_relevant(job):
            skipped_by_filter += 1
            continue
            
        # 2. Daily/Minute Free Quota Protection Cap
        if new_jobs >= 10:
            quota_pause = True
            # Log placeholder Scouted role without calling Gemini API
            cursor.execute('''
                INSERT OR IGNORE INTO jobs (
                    company, title, url, salary_culture_tier, match_score, status, 
                    interview_process, prep_plan, competition_level, growth_signals, 
                    compensation_signals, citations, unknown_fields, description
                )
                VALUES (?, ?, ?, 2, 60, 'Scouted', 'TBD', 'Review stack details', 'Medium', 'Medium', 'Tier 2', '[]', '[]', ?)
            ''', (job['company'], job['title'], job['url'], job.get('description', '')))
            conn.commit()
            continue
            
        print(f"⚡ Scoring via Gemini: {job['company']} - {job['title']}")
        analysis = evaluate_and_prioritize(job, profile)
        
        cursor.execute('''
            INSERT OR IGNORE INTO jobs (
                company, title, url, salary_culture_tier, match_score, status, 
                interview_process, prep_plan, competition_level, growth_signals, 
                compensation_signals, citations, unknown_fields, description
            )
            VALUES (?, ?, ?, ?, ?, 'Scouted', ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job['company'], 
            job['title'], 
            job['url'], 
            analysis.get('tier', 2), 
            analysis.get('match_score', 75), 
            analysis.get('interview_process', ''), 
            analysis.get('prep_plan', ''),
            analysis.get('competition_level', 'Medium'),
            analysis.get('growth_signals', 'Medium'),
            analysis.get('compensation_signals', 'Tier 2'),
            json.dumps(analysis.get('citations', [])),
            json.dumps(analysis.get('unknown_fields', [])),
            job.get('description', '')
        ))
        conn.commit()
        new_jobs += 1
        
        # 3. Rate-limiting sleep delay to prevent 429 minute-limit spikes
        time.sleep(3.5)
        
    print(f"\n{GREEN}✅ DISCOVERY_MODE completed.{RESET}")
    print(f"  • Matched & Scored: {CYAN}{new_jobs}{RESET} new relevant roles.")
    print(f"  • Pre-filtered out : {YELLOW}{skipped_by_filter}{RESET} completely unrelated roles (saved API quota).")
    if quota_pause:
        print(f"  • {YELLOW}[API Quota Protection]{RESET} Paused Gemini scoring after 10 calls. Saved remaining roles as Scouted backlog.")
    
    # Display top 10 prioritization
    print(f"\n{BOLD}⭐ TOP PRIORITIZED ROLES IN PIPELINE:{RESET}")
    cursor.execute("""
        SELECT company, title, match_score, competition_level, growth_signals, compensation_signals, status 
        FROM jobs 
        ORDER BY match_score DESC, 
                 CASE competition_level WHEN 'Low' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
                 CASE growth_signals WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
        LIMIT 10
    """)
    rows = cursor.fetchall()
    
    print(f"{'Company':<20} | {'Role Title':<30} | {'Score':<5} | {'Comp':<6} | {'Growth':<6} | {'Status':<10}")
    print("-" * 90)
    for r in rows:
        print(f"{r[0]:<20} | {r[1][:28]:<30} | {r[2]:<5}% | {r[3]:<6} | {r[4]:<6} | {r[6]:<10}")
        
    conn.close()
    input("\nHit ENTER to return to menu...")

def custom_discovery_mode():
    """Scrapes a specific single job application link and evaluates it."""
    url = input(f"\n👉 Enter custom job posting URL: ").strip()
    if not url:
        return
        
    print(f"{YELLOW}📡 Scraping custom URL...{RESET}")
    job = scrape_custom_job_page(url)
    
    if not os.path.exists("candidate_profile.json"):
        print(f"{RED}❌ Error: You must sync the Candidate Profile first (Mode 1)!{RESET}")
        input("\nHit ENTER to return to menu...")
        return
        
    with open("candidate_profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)
        
    print(f"⚡ Scoring: {job['company']} - {job['title']}")
    analysis = evaluate_and_prioritize(job, profile)
    
    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO jobs (
            company, title, url, salary_culture_tier, match_score, status, 
            interview_process, prep_plan, competition_level, growth_signals, 
            compensation_signals, citations, unknown_fields
        )
        VALUES (?, ?, ?, ?, ?, 'Scouted', ?, ?, ?, ?, ?, ?, ?)
    ''', (
        job['company'], 
        job['title'], 
        job['url'], 
        analysis.get('tier', 2), 
        analysis.get('match_score', 75), 
        analysis.get('interview_process', ''), 
        analysis.get('prep_plan', ''),
        analysis.get('competition_level', 'Medium'),
        analysis.get('growth_signals', 'Medium'),
        analysis.get('compensation_signals', 'Tier 2'),
        json.dumps(analysis.get('citations', [])),
        json.dumps(analysis.get('unknown_fields', []))
    ))
    conn.commit()
    conn.close()
    
    print(f"\n{GREEN}✅ Custom job evaluated. Alignment Match Score: {BOLD}{analysis.get('match_score')}%{RESET}")
    print(f"📋 Citations matched: {analysis.get('citations')}")
    if analysis.get('unknown_fields'):
        print(f"{YELLOW}⚠️ Unknown fields detected ({len(analysis.get('unknown_fields'))}). Run Mode 6 to resolve!{RESET}")
    input("\nHit ENTER to return to menu...")

def select_job_dialog(action_verb: str) -> dict:
    """Helper to display qualifying roles and let candidate pick one."""
    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, company, title, match_score FROM jobs WHERE match_score >= 70 ORDER BY match_score DESC")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print(f"{RED}❌ No qualifying jobs found. Run DISCOVERY_MODE first!{RESET}")
        return None
        
    print(f"\n{BOLD}Select role to {action_verb}:{RESET}")
    for idx, r in enumerate(rows):
        print(f"  [{idx + 1}] {BOLD}{r[1]}{RESET} - {r[2]} ({r[3]}% match)")
        
    choice = input("\n👉 Enter selection number: ").strip()
    try:
        selection_idx = int(choice) - 1
        if 0 <= selection_idx < len(rows):
            job_id = rows[selection_idx][0]
            
            # Fetch complete job
            conn = sqlite3.connect('job_tracker.db')
            cursor = conn.cursor()
            cursor.execute("SELECT company, title, url, description, match_score FROM jobs WHERE id=?", (job_id,))
            j = cursor.fetchone()
            conn.close()
            
            return {
                "id": job_id,
                "company": j[0],
                "title": j[1],
                "url": j[2],
                "description": j[3],
                "match_score": j[4]
            }
    except Exception:
        pass
        
    print(f"{RED}❌ Invalid selection.{RESET}")
    return None

def trigger_resume_generation():
    """Launches LaTeX tailoring and companion Markdown alignment report."""
    if not os.path.exists("candidate_profile.json"):
        print(f"{RED}❌ Ingest your living profile first (Mode 1)!{RESET}")
        input("\nHit ENTER to continue...")
        return
        
    job = select_job_dialog("tailor LaTeX resume for")
    if not job:
        return
        
    with open("candidate_profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)
        
    tex_path, md_path = generate_tailored_resume(job, profile)
    print(f"\n{GREEN}🎉 Success! Tailored assets generated:{RESET}")
    print(f"  📄 LaTeX: {tex_path}")
    print(f"  📋 Report: {md_path}")
    input("\nHit ENTER to return to menu...")

def trigger_intel_brief():
    """Generates an intelligence strategy brief."""
    if not os.path.exists("candidate_profile.json"):
        print(f"{RED}❌ Ingest your living profile first (Mode 1)!{RESET}")
        input("\nHit ENTER to continue...")
        return
        
    job = select_job_dialog("generate Application Strategy Brief for")
    if not job:
        return
        
    with open("candidate_profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)
        
    brief_path = compile_strategy_brief(job, profile)
    print(f"\n{GREEN}🎉 Success! Application Strategy Brief compiled:{RESET}")
    print(f"  📄 Markdown: {brief_path}")
    input("\nHit ENTER to return to menu...")

def run_learning_loop():
    """
    LEARNING_MODE — Scans jobs in DB for non-empty unknown_fields.
    Prompts candidate for missing answers and consolidates into candidate_profile.json.
    """
    print(f"\n{BOLD}{YELLOW}🧠 Entering LEARNING_MODE Loop...{RESET}")
    
    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, company, title, unknown_fields FROM jobs")
    rows = cursor.fetchall()
    
    unresolved_questions = {}
    for r in rows:
        job_id, company, title, u_fields_str = r
        try:
            u_fields = json.loads(u_fields_str)
            for f in u_fields:
                if f.startswith("UNKNOWN:"):
                    clean_field = f.replace("UNKNOWN:", "").split("—")[0].strip()
                    if clean_field not in unresolved_questions:
                        unresolved_questions[clean_field] = []
                    unresolved_questions[clean_field].append((job_id, company, title))
        except Exception:
            continue
            
    conn.close()
    
    if not unresolved_questions:
        print(f"{GREEN}✅ High parity! No unknown application fields are currently flagged in database.{RESET}")
        input("\nHit ENTER to return...")
        return
        
    print(f"Found {len(unresolved_questions)} unique unknown questions/fields in pipeline:")
    
    # Display and ask questions
    for idx, (field, references) in enumerate(unresolved_questions.items()):
        print(f"\n[{idx + 1}/{len(unresolved_questions)}] QUESTION FIELD: {BOLD}{YELLOW}{field}{RESET}")
        print(f"  Flagged by roles: " + ", ".join([f"{ref[1]} ({ref[2]})" for ref in references[:3]]))
        
        ans = input(f"👉 Please provide your answer (or hit ENTER to skip): ").strip()
        if ans:
            # Save response to LIVING profile
            update_learned_response(field, ans)
            
            # Remove from this job's unknown field in DB
            conn = sqlite3.connect('job_tracker.db')
            cursor = conn.cursor()
            for ref in references:
                cursor.execute("SELECT unknown_fields FROM jobs WHERE id=?", (ref[0],))
                curr_fields = json.loads(cursor.fetchone()[0])
                # Filter out
                updated_fields = [cf for cf in curr_fields if clean_field not in cf]
                cursor.execute("UPDATE jobs SET unknown_fields=? WHERE id=?", (json.dumps(updated_fields), ref[0]))
            conn.commit()
            conn.close()
            
    print(f"\n{GREEN}✅ LEARNING_MODE session complete. Living profile updated.{RESET}")
    input("\nHit ENTER to return to menu...")

def trigger_apply_node():
    """Performs browser launching, standard pre-fill, and application logging."""
    job = select_job_dialog("apply for")
    if not job:
        return
        
    status = interactive_apply_node(job['url'])
    
    if status == "Applied":
        conn = sqlite3.connect('job_tracker.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE jobs SET status='Applied' WHERE id=?", (job['id'],))
        conn.commit()
        
        # Pull counters
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE status='Applied'")
        applied_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE status='Scouted'")
        backlog_count = cursor.fetchone()[0]
        conn.close()
        
        # Build targets
        alert = (
            f"🚀 *Application Logged Successfully!*\n\n"
            f"🏢 *Company:* {job['company']}\n"
            f"💼 *Role:* {job['title']}\n"
            f"📊 *Dashboard:* {applied_count} Total Applied | {backlog_count} in Backlog"
        )
        send_email_update(alert)
        print(f"{GREEN}✅ Application successfully logged and tracking email transmitted!{RESET}")
    input("\nHit ENTER to return to menu...")

def send_daily_newsletter_summary():
    """Compiles pipeline statistics and outstanding preps; transmits as newsletter email."""
    print(f"\n{BOLD}{YELLOW}📡 Generating pipeline sync newsletter summary...{RESET}")
    
    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()
    
    # 1. Pipeline Stats
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status='Applied'")
    applied_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE match_score >= 80 AND status='Scouted'")
    high_priority_backlog = cursor.fetchall()
    
    # 2. Get top backlog roles
    cursor.execute("""
        SELECT company, title, match_score, prep_plan, url, description FROM jobs 
        WHERE match_score >= 80 AND status='Scouted' 
        ORDER BY match_score DESC LIMIT 5
    """)
    backlog_roles = cursor.fetchall()
    conn.close()
    
    # Load candidate profile
    profile = {}
    if os.path.exists("candidate_profile.json"):
        try:
            with open("candidate_profile.json", "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception:
            pass

    # Build email body
    now_str = datetime.now().strftime("%A, %B %d, %Y")
    body = f"🚀 JOBCRAFT AI — DAILY SYNC SYSTEM NEWSLETTER 🚀\n"
    body += f"Sync Date: {now_str}\n"
    body += f"============================================================\n\n"
    
    body += f"📊 PIPELINE METRICS STATUS:\n"
    body += f"  • Total Scouted Positions : {total_count}\n"
    body += f"  • Applications Completed   : {applied_count}\n"
    body += f"  • Hot Lead Backlog (>=80%) : {len(high_priority_backlog) if high_priority_backlog else 0}\n\n"
    
    if backlog_roles:
        body += f"🔥 TOP HOT LEADS BACKLOG PLAYBOOK (NEEDS ACTION):\n"
        for idx, r in enumerate(backlog_roles):
            company_clean = re.sub(r'\W+', '', r[0]).capitalize()
            title_clean = re.sub(r'\W+', '', r[1]).capitalize()
            
            # Automatically tailor resume if not already generated!
            resume_path = os.path.join("tailored_resumes", f"{company_clean}_{title_clean}_Resume.tex")
            if profile and not os.path.exists(resume_path):
                print(f"📄 Background Action: Auto-tailoring LaTeX resume for {r[0]}...")
                try:
                    desc = r[5]
                    if not desc or len(desc.strip()) < 10:
                        # Fallback: Scrape description on-the-fly!
                        scraped = scrape_custom_job_page(r[4])
                        desc = scraped.get('description', '')
                    job_dict = {"company": r[0], "title": r[1], "url": r[4], "description": desc}
                    generate_tailored_resume(job_dict, profile)
                except Exception as e:
                    print(f"⚠️ Resume tailoring fail: {e}")
            
            body += f"  {idx + 1}. {r[0]} — {r[1]} ({r[2]}% match score)\n"
            body += f"     🔗 Direct Apply Link: {r[4]}\n"
            body += f"     📄 Auto-Tailored LaTeX Resume: tailored_resumes/{company_clean}_{title_clean}_Resume.tex\n"
            body += f"     📋 Alignment Audit Report: tailored_resumes/{company_clean}_{title_clean}_Alignment.md\n"
            body += f"     🎯 Target Prep Playbook:\n{r[3]}\n\n"
            
    body += f"🧠 LIVING PROFILE INTELLIGENCE:\n"
    if os.path.exists("candidate_profile.json"):
        with open("candidate_profile.json", "r", encoding="utf-8") as f:
            prof = json.load(f)
            body += f"  • Living profile synchronised successfully for {prof['personal_info']['full_name']}.\n"
            body += f"  • Custom absorbed responses count: {len(prof.get('custom_responses', {}))}\n"
    else:
        body += "  • PROFILE UNSYNCED. Run Mode 1 immediately.\n"
        
    body += f"\n============================================================\n"
    body += f"This is an automated operational sync from your JobCraft AI Agent.\n"
    
    send_email_update(body)
    print(f"{GREEN}📧 Daily dashboard sync newsletter emailed directly to {CANDIDATE_DATA['email']}!{RESET}")
    input("\nHit ENTER to return to menu...")

def cron_scraping_mode():
    """Non-interactive entry point for background scheduling. Crawls and evaluates."""
    print("🤖 Cron trigger: scouting new positions...")
    if not os.path.exists("candidate_profile.json"):
        print("Error: candidate_profile.json not synced.")
        return
        
    with open("candidate_profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)
        
    init_db()
    listings = scout_hidden_gems()
    
    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()
    
    new_jobs = 0
    skipped_by_filter = 0
    quota_pause = False
    
    for job in listings:
        cursor.execute("SELECT id FROM jobs WHERE url=?", (job['url'],))
        if cursor.fetchone():
            continue
            
        # 1. Quota pre-filtering based on candidate relevance
        if not is_role_relevant(job):
            skipped_by_filter += 1
            continue
            
        # 2. Daily/Minute Free Quota Protection Cap
        if new_jobs >= 10:
            quota_pause = True
            cursor.execute('''
                INSERT OR IGNORE INTO jobs (
                    company, title, url, salary_culture_tier, match_score, status, 
                    interview_process, prep_plan, competition_level, growth_signals, 
                    compensation_signals, citations, unknown_fields, description
                )
                VALUES (?, ?, ?, 2, 60, 'Scouted', 'TBD', 'Review stack details', 'Medium', 'Medium', 'Tier 2', '[]', '[]', ?)
            ''', (job['company'], job['title'], job['url'], job.get('description', '')))
            conn.commit()
            continue
            
        analysis = evaluate_and_prioritize(job, profile)
        cursor.execute('''
            INSERT OR IGNORE INTO jobs (
                company, title, url, salary_culture_tier, match_score, status, 
                interview_process, prep_plan, competition_level, growth_signals, 
                compensation_signals, citations, unknown_fields, description
            )
            VALUES (?, ?, ?, ?, ?, 'Scouted', ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job['company'], 
            job['title'], 
            job['url'], 
            analysis.get('tier', 2), 
            analysis.get('match_score', 75), 
            analysis.get('interview_process', ''), 
            analysis.get('prep_plan', ''),
            analysis.get('competition_level', 'Medium'),
            analysis.get('growth_signals', 'Medium'),
            analysis.get('compensation_signals', 'Tier 2'),
            json.dumps(analysis.get('citations', [])),
            json.dumps(analysis.get('unknown_fields', [])),
            job.get('description', '')
        ))
        conn.commit()
        new_jobs += 1
        
        # 3. Rate-limiting sleep delay to prevent 429 minute-limit spikes
        time.sleep(3.5)
        
    conn.close()
    print(f"Cron finished. Added {new_jobs} new scored roles. Skipped {skipped_by_filter} unrelated roles. Quota pause status: {quota_pause}")

def cron_summary_mode():
    """Non-interactive daily summary newsletter compiler."""
    print("🤖 Cron trigger: compiling daily pipeline newsletter...")
    init_db()
    
    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status='Applied'")
    applied_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT company, title, match_score, prep_plan, url, description FROM jobs 
        WHERE match_score >= 80 AND status='Scouted' 
        ORDER BY match_score DESC LIMIT 5
    """)
    backlog_roles = cursor.fetchall()
    conn.close()
    
    # Load candidate profile
    profile = {}
    if os.path.exists("candidate_profile.json"):
        try:
            with open("candidate_profile.json", "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception:
            pass
            
    now_str = datetime.now().strftime("%A, %B %d, %Y")
    body = f"🚀 JOBCRAFT AI — AUTOMATED OPERATIONS SUMMARY 🚀\n"
    body += f"Sync Date: {now_str}\n"
    body += f"============================================================\n\n"
    body += f"📊 PIPELINE METRICS STATUS:\n"
    body += f"  • Total Scouted Positions : {total_count}\n"
    body += f"  • Applications Completed   : {applied_count}\n"
    body += f"  • Hot Lead Backlog (>=80%) : {len(backlog_roles)}\n\n"
    
    if backlog_roles:
        body += f"🔥 TOP HOT LEADS BACKLOG PLAYBOOK (NEEDS ACTION):\n"
        for idx, r in enumerate(backlog_roles):
            company_clean = re.sub(r'\W+', '', r[0]).capitalize()
            title_clean = re.sub(r'\W+', '', r[1]).capitalize()
            
            # Automatically tailor resume if not already generated!
            resume_path = os.path.join("tailored_resumes", f"{company_clean}_{title_clean}_Resume.tex")
            if profile and not os.path.exists(resume_path):
                print(f"📄 Background Action: Auto-tailoring LaTeX resume for {r[0]}...")
                try:
                    desc = r[5]
                    if not desc or len(desc.strip()) < 10:
                        # Fallback: Scrape description on-the-fly!
                        scraped = scrape_custom_job_page(r[4])
                        desc = scraped.get('description', '')
                    job_dict = {"company": r[0], "title": r[1], "url": r[4], "description": desc}
                    generate_tailored_resume(job_dict, profile)
                except Exception as e:
                    print(f"⚠️ Resume tailoring fail: {e}")
            
            body += f"  {idx + 1}. {r[0]} — {r[1]} ({r[2]}% match score)\n"
            body += f"     🔗 Direct Apply Link: {r[4]}\n"
            body += f"     📄 Auto-Tailored LaTeX Resume: tailored_resumes/{company_clean}_{title_clean}_Resume.tex\n"
            body += f"     📋 Alignment Audit Report: tailored_resumes/{company_clean}_{title_clean}_Alignment.md\n"
            body += f"     🎯 Target Prep Playbook:\n{r[3]}\n\n"
            
    body += f"\n============================================================\n"
    body += f"This is an automated background operational report from JobCraft AI.\n"
    
    send_email_update(body)
    print("Daily operational report emailed successfully.")

def main():
    init_db()
    
    # Setup argument parsing for background crons
    parser = argparse.ArgumentParser(description="JobCraft AI operational core.")
    parser.add_argument("--cron-check", action="store_true", help="Background role crawler trigger")
    parser.add_argument("--cron-summary", action="store_true", help="Daily operational briefing compiler")
    args = parser.parse_args()
    
    if args.cron_check:
        cron_scraping_mode()
        sys.exit(0)
    elif args.cron_summary:
        cron_summary_mode()
        sys.exit(0)
        
    while True:
        display_dashboard()
        display_menu()
        
        choice = input("👉 Select mode/action [0-8]: ").strip()
        
        if choice == "1":
            print(f"\n{BOLD}{YELLOW}🔄 Syncing profile and parsing resumes...{RESET}")
            ingest_profile(PORTFOLIO_URL, force_rebuild=True)
            input("\nHit ENTER to return to menu...")
        elif choice == "2":
            discovery_scout_mode()
        elif choice == "3":
            custom_discovery_mode()
        elif choice == "4":
            trigger_resume_generation()
        elif choice == "5":
            trigger_intel_brief()
        elif choice == "6":
            run_learning_loop()
        elif choice == "7":
            trigger_apply_node()
        elif choice == "8":
            send_daily_newsletter_summary()
        elif choice == "0":
            print(f"\n{BOLD}{GREEN}👋 Thank you for using JobCraft AI. Maximizing your hiring success rate!{RESET}\n")
            break
        else:
            print(f"{RED}❌ Invalid selection. Please choose 0 to 8.{RESET}")
            input("\nHit ENTER to try again...")

if __name__ == "__main__":
    main()
