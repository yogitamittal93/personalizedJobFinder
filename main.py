import os
import json
import sqlite3
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
load_dotenv()

from scraper import scrape_portfolio, scout_hidden_gems
from evaluator import evaluate_and_prioritize
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────
# CANDIDATE CONFIGURATION
# ─────────────────────────────────────────────
PORTFOLIO_URL = "https://portfolio-three-sigma-mp0vvhcq3h.vercel.app/"
CANDIDATE_DATA = {
    "full_name": "Yogita Singla",
    "email": "yogitamittal.tech@gmail.com",
    "portfolio": PORTFOLIO_URL
}

# ─────────────────────────────────────────────
# SEARCH GOALS — drives AI scoring in evaluator
# Edit this to tune what kinds of roles you get
# ─────────────────────────────────────────────
SEARCH_GOALS = {
    "min_salary_usd": 60000,
    "target_roles": [
        "Growth Engineer",
        "Founding Engineer",
        "Full Stack Engineer",
        "Technical Lead",
        "Platform Engineer",
        "Integration Engineer",
        "eCommerce Engineer",
        "WordPress Engineer",
        "MarTech Engineer",
        "Developer Advocate",
        "Technical Co-Founder",
        "Software Engineer"
    ],
    "priorities": [
        "email marketing or lifecycle automation stack",
        "ecommerce or DTC brand",
        "martech or growth engineering",
        "early stage startup seed to series B",
        "generalist or founding engineer role",
        "WordPress WooCommerce or headless commerce",
        "HubSpot Klaviyo or marketing automation integration",
        "remote-first async culture",
        "AI or ML exposure is a bonus not a hard requirement"
    ],
    "strengths": [
        "PHP", "JavaScript", "WordPress", "WooCommerce", "Commercev3",
        "Klaviyo", "HubSpot", "email automation", "lifecycle marketing",
        "behavioral triggers", "segmentation", "GTM", "Google Tag Manager",
        "Next.js", "Node.js", "NestJS", "TypeScript", "PostgreSQL",
        "Prisma", "Python", "Flask", "RAG pipeline", "ChromaDB",
        "REST APIs", "OAuth", "Stripe integrations", "performance optimization",
        "digital marketing", "conversion optimization", "A/B testing",
        "13 years experience", "full stack", "freelance", "client delivery"
    ],
    "deal_breakers": [
        "requires CS degree mandatory",
        "pure ML research scientist",
        "on-site only no remote",
        "enterprise Java or .NET only",
        "C++ or Rust required",
        "US work authorization required"
    ],
    "avoid_companies": []  # add company names here as you get tired of seeing them
}


# ─────────────────────────────────────────────
# DB INITIALIZATION
# ─────────────────────────────────────────────
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
            prep_plan TEXT,
            emailed_at TEXT DEFAULT NULL,
            eval_status TEXT DEFAULT 'verified'
        )
    ''')

    # Safe migrations for existing DBs — each is idempotent
    for migration in [
        "ALTER TABLE jobs ADD COLUMN emailed_at TEXT DEFAULT NULL",
        "ALTER TABLE jobs ADD COLUMN eval_status TEXT DEFAULT 'verified'",
    ]:
        try:
            cursor.execute(migration)
        except Exception:
            pass  # Column already exists, skip

    # Below-threshold pool — query weekly to find hidden gems in the 70-79 band
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs_below_threshold (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            title TEXT,
            url TEXT UNIQUE,
            match_score INTEGER,
            logged_at TEXT
        )
    ''')

    # Feedback table — foundation for future learning loop
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            action TEXT,
            reason TEXT,
            created_at TEXT
        )
    ''')

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# HTML DIGEST EMAIL BUILDER
# ─────────────────────────────────────────────
def build_html_email(digest_jobs: list) -> tuple:
    """Returns (plain_text, html) tuple for the digest email."""

    # ── Plain text fallback ──────────────────
    lines = [f"Your Job Digest — {len(digest_jobs)} Fresh Opportunities\n"]
    for i, j in enumerate(digest_jobs, 1):
        flag = " [UNVERIFIED — Gemini failed to evaluate]" if j.get('eval_status') == 'unverified' else ""
        lines.append(
            f"{'='*50}\n"
            f"#{i}  {j['company']} — {j['title']}{flag}\n"
            f"Link: {j['url']}\n"
            f"Match Score: {j['score']}{flag}\n"
            f"Why it fits: {j.get('why_fit', '—')}\n"
            f"Interview Pattern:\n{j['interview_process']}\n"
            f"Prep Plan:\n{j['prep_plan']}\n"
        )
    plain = "\n".join(lines)

    # ── HTML version ────────────────────────
    rows = ""
    for i, j in enumerate(digest_jobs, 1):
        is_unverified = j.get('eval_status') == 'unverified'
        score = j['score']

        if is_unverified:
            score_badge = '<span style="background:#6b7280;color:white;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700">⚠️ ?</span>'
            row_bg = "#fffbeb"  # soft yellow background for unverified rows
            unverified_note = '<div style="font-size:11px;color:#b45309;margin-top:4px;font-weight:600">⚠️ Unverified — Gemini failed. Review manually.</div>'
        else:
            score_color = "#22c55e" if score >= 90 else "#f59e0b" if score >= 80 else "#ef4444"
            score_badge = f'<span style="background:{score_color};color:white;padding:3px 10px;border-radius:999px;font-size:13px;font-weight:700">{score}</span>'
            row_bg = "white"
            unverified_note = ""

        why_fit = j.get('why_fit') or '—'

        rows += f"""
        <tr style="border-bottom:1px solid #e5e7eb;background:{row_bg}">
          <td style="padding:14px 10px;font-weight:700;color:#6b7280;font-size:13px">#{i}</td>
          <td style="padding:14px 10px;">
            <div style="font-weight:700;font-size:15px;color:#111827">{j['company']}</div>
          </td>
          <td style="padding:14px 10px;">
            <div style="font-weight:600;font-size:14px;color:#1d4ed8">{j['title']}</div>
            <div style="font-size:12px;color:#6b7280;margin-top:3px">{why_fit}</div>
            {unverified_note}
          </td>
          <td style="padding:14px 10px;text-align:center">{score_badge}</td>
          <td style="padding:14px 10px;text-align:center">
            <a href="{j['url']}" style="background:#1d4ed8;color:white;padding:7px 16px;
               border-radius:6px;text-decoration:none;font-size:13px;font-weight:600">Apply →</a>
          </td>
        </tr>
        <tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb;">
          <td colspan="5" style="padding:10px 14px 14px;font-size:12px;color:#374151;line-height:1.6">
            <strong>Interview:</strong> {j['interview_process']}<br>
            <strong>Prep:</strong> {j['prep_plan']}
          </td>
        </tr>
        """

    unverified_count = sum(1 for j in digest_jobs if j.get('eval_status') == 'unverified')
    unverified_banner = ""
    if unverified_count > 0:
        unverified_banner = f"""
        <div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;
                    padding:12px 16px;margin-bottom:20px;font-size:13px;color:#92400e">
          ⚠️ <strong>{unverified_count} role(s) marked unverified</strong> — Gemini API failed during
          evaluation. These jobs matched your search criteria but their scores are estimates.
          Please review them manually before applying.
        </div>
        """

    html = f"""
    <html><body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,
        'Segoe UI',sans-serif;background:#f3f4f6">
    <div style="max-width:860px;margin:30px auto;background:white;border-radius:12px;
         overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

      <div style="background:linear-gradient(135deg,#1d4ed8,#7c3aed);padding:28px 32px">
        <h1 style="color:white;margin:0;font-size:22px">🚀 Your Job Digest</h1>
        <p style="color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:14px">
          {len(digest_jobs)} fresh opportunities matched to your profile •
          {datetime.utcnow().strftime('%b %d, %Y')}
        </p>
      </div>

      <div style="padding:24px 32px">
        {unverified_banner}
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb">
              <th style="padding:10px;text-align:left;font-size:12px;color:#6b7280;font-weight:600">#</th>
              <th style="padding:10px;text-align:left;font-size:12px;color:#6b7280;font-weight:600">COMPANY</th>
              <th style="padding:10px;text-align:left;font-size:12px;color:#6b7280;font-weight:600">ROLE & FIT</th>
              <th style="padding:10px;text-align:center;font-size:12px;color:#6b7280;font-weight:600">SCORE</th>
              <th style="padding:10px;text-align:center;font-size:12px;color:#6b7280;font-weight:600">LINK</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>

      <div style="padding:18px 32px;background:#f9fafb;border-top:1px solid #e5e7eb">
        <p style="margin:0;font-size:12px;color:#9ca3af">
          Sent by PersonalizedJobFinder • Scored for growth/martech/ecommerce profile •
          <a href="{PORTFOLIO_URL}" style="color:#1d4ed8">Your Portfolio</a>
        </p>
      </div>

    </div>
    </body></html>
    """
    return plain, html


# ─────────────────────────────────────────────
# EMAIL SENDER
# ─────────────────────────────────────────────
def send_email_update(subject: str, plain_body: str, html_body: str = None):
    """
    Sends email with HTML + plain text fallback.
    Rotates across sender accounts and ports for reliability.
    """
    sender_emails = [
        "yogitamittal.tech@gmail.com",
        "yogitasingla93@gmail.com",
        "yogitasinglamittal@gmail.com"
    ]
    receiver_emails = [
        "yogitamittal.tech@gmail.com",
        "yogitasingla93@gmail.com",
        "yogitasinglamittal@gmail.com"
    ]

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

    passwords = []
    for p in [os.getenv("EMAIL_APP_PASSWORD", ""), os.getenv("EMAIL_APP_PASSWORD2", "")]:
        if p:
            cleaned = p.replace(" ", "").replace('"', '').replace("'", "").strip()
            if cleaned and cleaned not in passwords:
                passwords.append(cleaned)
            raw = p.strip()
            if raw and raw not in passwords:
                passwords.append(raw)
    if not passwords:
        passwords = ["your_fallback_app_password"]

    if html_body:
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(plain_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
    else:
        msg = MIMEText(plain_body)

    msg['Subject'] = subject
    msg['To'] = ", ".join(receiver_emails)

    for sender in sender_emails:
        for pwd in passwords:
            # Port 465 SSL
            try:
                msg['From'] = sender
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(sender, pwd)
                    server.sendmail(sender, receiver_emails, msg.as_string())
                print(f"📧 Email sent via {sender} (Port 465 SSL)")
                return
            except smtplib.SMTPAuthenticationError:
                continue
            except Exception:
                pass

            # Port 587 STARTTLS fallback
            try:
                msg['From'] = sender
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(sender, pwd)
                server.sendmail(sender, receiver_emails, msg.as_string())
                server.quit()
                print(f"📧 Email sent via {sender} (Port 587 STARTTLS)")
                return
            except smtplib.SMTPAuthenticationError:
                continue
            except Exception:
                continue

    print("❌ All SMTP configurations failed. Check App Passwords in .env")


# ─────────────────────────────────────────────
# INTERACTIVE APPLY (manual mode — kept for future use)
# ─────────────────────────────────────────────
def interactive_apply_node(job_url: str):
    """Launches browser, auto-fills standard details, pauses for manual submit."""
    print(f"\n[Agent Action] Opening: {job_url}")
    print("🤖 Launching secure browser. Review and complete the form.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(job_url)
        try:
            page.locator("input[name*='name']").first.fill(CANDIDATE_DATA['full_name'])
            page.locator("input[type='email']").first.fill(CANDIDATE_DATA['email'])
            page.locator("input[name*='url'], input[name*='portfolio']").first.fill(CANDIDATE_DATA['portfolio'])
        except Exception:
            pass
        input("\n👉 Review, edit, click SUBMIT on the page, then press ENTER here to log it...")
        browser.close()
    return "Applied"


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────
def main():
    init_db()

    print("🔍 Scraping candidate portfolio...")
    portfolio_text = scrape_portfolio(PORTFOLIO_URL)

    print("🚀 Scouting remote listings across all channels...")
    listings = scout_hidden_gems()
    print(f"Found {len(listings)} unique listings.")

    conn = sqlite3.connect('job_tracker.db')
    cursor = conn.cursor()

    # ── Step 1: Evaluate & store new jobs ──────────────────────────────────
    avoid = [c.lower() for c in SEARCH_GOALS.get("avoid_companies", [])]
    new_evaluated = 0

    for job in listings:
        # Skip companies you've blocklisted
        if job['company'].lower() in avoid:
            continue

        # Skip if URL already in DB
        cursor.execute("SELECT id FROM jobs WHERE url=?", (job['url'],))
        if cursor.fetchone():
            continue

        print(f"\nEvaluating: {job['company']} — {job['title']}")
        analysis = evaluate_and_prioritize(job, portfolio_text, search_goals=SEARCH_GOALS)
        new_evaluated += 1

        eval_status = analysis.get('eval_status', 'verified')

        if analysis['match_score'] >= 80:
            cursor.execute('''
                INSERT OR IGNORE INTO jobs
                (company, title, url, salary_culture_tier, match_score,
                 interview_process, prep_plan, status, eval_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Scouted', ?)
            ''', (
                job['company'], job['title'], job['url'],
                analysis.get('tier', 2),
                analysis['match_score'],
                analysis.get('interview_process', ''),
                analysis.get('prep_plan', ''),
                eval_status
            ))
        else:
            # Log near-misses (70-79) for weekly manual review
            if analysis['match_score'] >= 70:
                cursor.execute('''
                    INSERT OR IGNORE INTO jobs_below_threshold
                    (company, title, url, match_score, logged_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    job['company'], job['title'], job['url'],
                    analysis['match_score'],
                    datetime.utcnow().isoformat()
                ))

        conn.commit()

    print(f"\n✅ Evaluated {new_evaluated} new listings.")

    # ── Step 2: Pick digest — 12 unsent, max 2 per company, no title dupes ─
    cursor.execute('''
        SELECT id, company, title, url, match_score,
               interview_process, prep_plan, eval_status
        FROM jobs
        WHERE emailed_at IS NULL
        ORDER BY
            CASE WHEN eval_status = 'verified' THEN 0 ELSE 1 END,
            match_score DESC
    ''')
    # ↑ verified jobs float to top; within each group, sorted by score
    candidates = cursor.fetchall()

    company_counts = {}
    seen_titles = set()
    digest_jobs = []

    for row in candidates:
        job_id, company, title, url, score, interview_process, prep_plan, eval_status = row
        company_key = company.lower().strip()
        title_key = f"{company_key}::{title.lower().strip()}"

        # Respect avoid list for jobs that were stored before you added a company
        if company_key in avoid:
            continue

        # Max 2 per company
        if company_counts.get(company_key, 0) >= 2:
            continue

        # No duplicate title+company (same role on two URLs)
        if title_key in seen_titles:
            continue

        company_counts[company_key] = company_counts.get(company_key, 0) + 1
        seen_titles.add(title_key)

        digest_jobs.append({
            'id': job_id,
            'company': company,
            'title': title,
            'url': url,
            'score': score,
            'interview_process': interview_process or '—',
            'prep_plan': prep_plan or '—',
            'eval_status': eval_status or 'verified',
            'why_fit': ''  # populated by evaluator if it returns why_fit key
        })

        if len(digest_jobs) >= 12:
            break

    # ── Step 3: Send digest or heartbeat ────────────────────────────────────
    if not digest_jobs:
        send_email_update(
            subject="✅ Job Agent Ran — No New Matches Today",
            plain_body=(
                f"PersonalizedJobFinder ran at {datetime.utcnow().strftime('%b %d %Y %H:%M')} UTC.\n\n"
                f"No new jobs above the 80-point threshold were found this cycle.\n\n"
                f"The pipeline is healthy — check back next run.\n\n"
                f"💡 Tip: To see near-miss roles (scored 70-79), query the\n"
                f"jobs_below_threshold table in job_tracker.db"
            )
        )
        print("✅ Heartbeat sent — no new matches this cycle.")
        conn.close()
        return

    plain, html = build_html_email(digest_jobs)
    verified = sum(1 for j in digest_jobs if j.get('eval_status') != 'unverified')
    unverified = len(digest_jobs) - verified

    subject = f"🚀 {len(digest_jobs)} Fresh Job Matches — {datetime.utcnow().strftime('%b %d')}"
    if unverified > 0:
        subject += f" ({unverified} ⚠️ unverified)"

    send_email_update(subject=subject, plain_body=plain, html_body=html)

    # ── Step 4: Mark all digested jobs as emailed so they never repeat ──────
    now = datetime.utcnow().isoformat()
    for j in digest_jobs:
        cursor.execute(
            "UPDATE jobs SET emailed_at=? WHERE id=?",
            (now, j['id'])
        )
    conn.commit()
    conn.close()

    print(f"\n🎉 Digest sent — {len(digest_jobs)} jobs ({verified} verified, {unverified} unverified).")


if __name__ == "__main__":
    main()
