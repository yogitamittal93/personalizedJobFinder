import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urlparse


# ─────────────────────────────────────────────
# PORTFOLIO SCRAPER
# ─────────────────────────────────────────────
def scrape_portfolio(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "footer", "nav"]):
            element.extract()
        return " ".join(soup.get_text().split())
    except Exception as e:
        return f"Portfolio scraping failed: {str(e)}"


# ─────────────────────────────────────────────
# LOCATION ELIGIBILITY FILTER
# ─────────────────────────────────────────────
def is_location_eligible(location: str, company: str) -> bool:
    """
    Returns True if the role is accessible to a remote candidate based in India.
    Filters out hard on-site or region-locked roles.
    """
    loc = str(location).lower()
    comp = str(company).lower()

    # Indian-headquartered companies — always eligible
    indian_companies = [
        "razorpay", "freshworks", "browserstack", "chargebee",
        "cred", "zerodha", "groww", "hasura", "postman", "clevertap",
        "zepto", "meesho", "lenskart", "curefit", "bigbasket"
    ]
    if comp in indian_companies:
        return True

    # Hard geo-locks that exclude India (unless explicitly overridden)
    restricted_keywords = [
        "us only", "usa only", "united states only", "canada only",
        "north america only", "europe only", "emea only", "latam only",
        "americas only", "strictly us", "strictly usa",
        "uk only", "united kingdom only",
        # Specific cities without remote mention
        "london", "berlin", "munich", "san francisco", "new york",
        "boston", "austin", "seattle", "chicago", "los angeles", "denver",
        "toronto", "sydney", "amsterdam", "paris", "dublin"
    ]
    if any(rk in loc for rk in restricted_keywords):
        # Override: if the listing also mentions India/global/remote, allow it
        if not any(ok in loc for ok in ["india", "worldwide", "global", "anywhere", "remote"]):
            return False

    # Explicitly suitable — fast-pass
    suitable_keywords = [
        "india", "remote", "worldwide", "anywhere", "global", "apac", "asia",
        "bengaluru", "bangalore", "delhi", "mumbai", "pune",
        "hyderabad", "chennai", "noida", "gurgaon", "gurugram"
    ]
    if any(sk in loc for sk in suitable_keywords):
        return True

    # Blank/unstated location — most global-remote companies leave this empty
    return True


# ─────────────────────────────────────────────
# ATS BOARD SCRAPERS (Greenhouse / Lever / Ashby)
# ─────────────────────────────────────────────
def check_bulk_ats_boards() -> list:
    found_jobs = []

    # ── GREENHOUSE ──────────────────────────────────────────────────────────
    # Weighted toward your profile: martech, ecommerce, growth, generalist tools
    greenhouse_companies = [
        # MarTech & Email Automation — your strongest domain
        "hubspot", "klaviyo", "attentive", "iterable", "activecampaign",
        "customerio", "omnisend", "mailchimp", "braze", "sendgrid",
        "segment", "amplitude", "mixpanel",

        # eCommerce & DTC — deep Commercev3/WooCommerce background
        "shopify", "recharge", "gorgias", "yotpo", "nacelle",
        "bigcommerce", "elasticpath", "recart", "postscript",

        # Growth & Conversion tools — GTM, A/B, analytics
        "hotjar", "optimizely", "convertkit", "beehiiv",

        # Developer tools & infra — Next.js, Node, Postgres experience
        "vercel", "netlify", "supabase", "neon", "railway", "render",
        "postman", "hashicorp", "mongodb", "confluent",

        # Design & productivity — generalist-friendly
        "figma", "airtable", "notion", "loom", "coda", "miro",

        # Fintech & payments — Stripe integration experience
        "stripe", "brex", "ramp", "plaid", "mercury", "deel", "rippling",
        "patreon", "affirm",

        # AI & ML — MomDigital RAG pipeline background
        "huggingface", "anthropic", "cohere", "perplexity",

        # Cloud & DevOps
        "datadog", "newrelic", "grafana", "sentry",

        # Global remote-first
        "zapier", "buffer", "doist", "toggl", "papercup",

        # Indian & APAC
        "razorpay", "freshworks", "browserstack", "chargebee",
        "clevertap", "hasura", "groww", "cred",

        # CMS & headless — WordPress/headless experience
        "contentful", "sanity", "prismic", "storyblok",

        # General remote
        "calendly", "retool", "webflow", "framer", "ghost",
        "gitbook", "twilio", "intercom"
    ]

    # ── LEVER ───────────────────────────────────────────────────────────────
    lever_companies = [
        # MarTech / Growth
        "buffer", "zapier", "ghost", "close", "drift", "front",
        "typeform", "hotjar", "doist",

        # eCommerce adjacent
        "gorgias", "yotpo", "okendo", "stamped",

        # Developer tools
        "atlassian", "gitbook", "digitalocean", "canva",
        "liveblocks", "stytch", "clerk", "resend",

        # Email-first / newsletter tools
        "convertkit", "beehiiv", "substack",

        # Open source / indie
        "formbricks", "midday", "papermark", "documenso",
        "dub", "novu", "cal", "trigger", "inngest",

        # Indian / global remote
        "zerodha", "andela",

        # Misc high-quality remote
        "bunq", "mollie", "intercom", "turso"
    ]

    # ── ASHBY ───────────────────────────────────────────────────────────────
    ashby_companies = [
        "linear", "railway", "clerk", "resend", "dub", "liveblocks",
        "novu", "trigger", "cal", "mintlify", "unkey", "openstatus",
        "formbricks", "midday"
    ]

    print(f"📡 Querying {len(greenhouse_companies)} Greenhouse job boards...")
    for company in greenhouse_companies:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                jobs = res.json().get("jobs", [])
                for j in jobs:
                    loc_name = j.get("location", {}).get("name", "Remote")
                    if is_location_eligible(loc_name, company):
                        found_jobs.append({
                            "company": company.capitalize(),
                            "title": j["title"],
                            "url": j["absolute_url"],
                            "description": j.get("content", j["title"]),
                            "location": loc_name
                        })
        except Exception:
            continue

    print(f"📡 Querying {len(lever_companies)} Lever job boards...")
    for company in lever_companies:
        try:
            url = f"https://api.lever.co/v0/postings/{company}?mode=json"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                for j in res.json():
                    loc_name = j.get("categories", {}).get("location", "Remote")
                    if is_location_eligible(loc_name, company):
                        found_jobs.append({
                            "company": company.capitalize(),
                            "title": j["text"],
                            "url": j["hostedUrl"],
                            "description": j.get("description", ""),
                            "location": loc_name
                        })
        except Exception:
            continue

    print(f"📡 Querying {len(ashby_companies)} Ashby job boards...")
    for company in ashby_companies:
        try:
            url = "https://api.ashbyhq.com/gating/internal/job-board-api/v1/postings"
            res = requests.post(url, json={"organizationName": company}, timeout=5)
            if res.status_code == 200:
                jobs = res.json().get("results", [])
                for j in jobs:
                    loc_name = j.get("locationName", "Remote")
                    if is_location_eligible(loc_name, company):
                        found_jobs.append({
                            "company": company.capitalize(),
                            "title": j["title"],
                            "url": j["jobUrl"],
                            "description": j.get("descriptionHtml", ""),
                            "location": loc_name
                        })
        except Exception:
            continue

    return found_jobs


# ─────────────────────────────────────────────
# REMOTIVE — global remote startups
# ─────────────────────────────────────────────
def fetch_remotive_jobs() -> list:
    """
    Fetches global-remote startup listings from Remotive API.
    Targets categories relevant to your profile.
    """
    startup_jobs = []

    # Added 'marketing' category — picks up growth/martech roles too
    categories = [
        "software-dev", "frontend", "backend", "fullstack",
        "devops-sysadmin", "marketing"
    ]

    for category in categories:
        try:
            res = requests.get(
                f"https://remotive.com/api/remote-jobs?category={category}&limit=50",
                timeout=10
            )
            if res.status_code == 200:
                for j in res.json().get("jobs", []):
                    geo = j.get("candidate_required_location", "").lower()
                    is_eligible = (
                        not geo
                        or "worldwide" in geo
                        or "anywhere" in geo
                        or "global" in geo
                        or "india" in geo
                        or "apac" in geo
                        or "asia" in geo
                    )
                    if is_eligible:
                        startup_jobs.append({
                            "company": j.get("company_name", "Global Startup"),
                            "title": j.get("title", ""),
                            "url": j.get("url", ""),
                            "description": j.get("description", ""),
                            "location": j.get("candidate_required_location", "Worldwide")
                        })
        except Exception as e:
            print(f"Error checking Remotive ({category}): {e}")

    return startup_jobs


# ─────────────────────────────────────────────
# WE WORK REMOTELY — RSS feeds
# ─────────────────────────────────────────────
def fetch_weworkremotely_jobs() -> list:
    """
    Fetches remote jobs from WWR RSS feeds.
    Added marketing/growth feed alongside programming feeds.
    """
    wwr_jobs = []
    feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
        # Added: picks up growth engineer / martech hybrid roles
        "https://weworkremotely.com/categories/remote-marketing-jobs.rss",
    ]

    for feed_url in feeds:
        try:
            res = requests.get(
                feed_url, timeout=10,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                for item in root.findall(".//item"):
                    title_el = item.find("title")
                    link_el = item.find("link")
                    desc_el = item.find("description")

                    if title_el is None or link_el is None:
                        continue

                    raw_title = title_el.text or ""
                    if ":" in raw_title:
                        parts = raw_title.split(":", 1)
                        company = parts[0].strip()
                        role = parts[1].strip()
                    else:
                        company = "Remote Company"
                        role = raw_title.strip()

                    url = link_el.text or ""
                    description = ""
                    if desc_el is not None and desc_el.text:
                        description = re.sub(r'<[^>]+>', ' ', desc_el.text)
                        description = " ".join(description.split())

                    if url and role:
                        wwr_jobs.append({
                            "company": company,
                            "title": role,
                            "url": url,
                            "description": description,
                            "location": "Worldwide Remote"
                        })
        except Exception as e:
            print(f"Error fetching WWR feed {feed_url}: {e}")

    return wwr_jobs


# ─────────────────────────────────────────────
# HACKER NEWS — "Who Is Hiring?" (monthly thread)
# High signal: direct founder contact, no recruiters
# ─────────────────────────────────────────────
def fetch_hn_who_is_hiring() -> list:
    """
    Pulls the latest Hacker News 'Who is Hiring?' thread via Algolia API.
    These are direct posts from founders/CTOs — no recruiter noise.
    Filters for remote-eligible, relevant keywords.
    """
    hn_jobs = []

    # Keywords that match your profile
    relevant_keywords = [
        "wordpress", "woocommerce", "klaviyo", "hubspot", "email",
        "ecommerce", "e-commerce", "shopify", "martech", "growth",
        "full stack", "fullstack", "next.js", "node", "typescript",
        "php", "remote", "founding engineer", "generalist"
    ]

    try:
        # Find the most recent "Ask HN: Who is Hiring?" thread
        search_res = requests.get(
            "https://hn.algolia.com/api/v1/search?query=Ask+HN+Who+is+Hiring"
            "&tags=story&numericFilters=points>50",
            timeout=10
        )
        if search_res.status_code != 200:
            return hn_jobs

        hits = search_res.json().get("hits", [])
        # Find the most recent hiring thread
        hiring_threads = [
            h for h in hits
            if "who is hiring" in h.get("title", "").lower()
            and h.get("objectID")
        ]
        if not hiring_threads:
            return hn_jobs

        # Sort by date descending, take the most recent
        hiring_threads.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        thread_id = hiring_threads[0]["objectID"]

        # Fetch comments from the thread
        comments_res = requests.get(
            f"https://hn.algolia.com/api/v1/search?tags=comment,story_{thread_id}&hitsPerPage=200",
            timeout=10
        )
        if comments_res.status_code != 200:
            return hn_jobs

        comments = comments_res.json().get("hits", [])
        for comment in comments:
            text = comment.get("comment_text", "") or ""
            text_lower = text.lower()

            # Must mention remote and at least one relevant keyword
            if "remote" not in text_lower:
                continue
            if not any(kw in text_lower for kw in relevant_keywords):
                continue

            # Skip if clearly US/EU only
            if any(bad in text_lower for bad in [
                "us only", "usa only", "must be in", "authorized to work in the us"
            ]):
                continue

            # Extract a rough company/title from first line
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            first_line = lines[0] if lines else "HN Opportunity"

            # Strip HTML tags from description
            clean_text = re.sub(r'<[^>]+>', ' ', text)
            clean_text = " ".join(clean_text.split())[:800]  # cap description length

            hn_jobs.append({
                "company": f"HN: {first_line[:60]}",
                "title": "See description (HN post)",
                "url": f"https://news.ycombinator.com/item?id={comment.get('objectID', thread_id)}",
                "description": clean_text,
                "location": "Remote"
            })

    except Exception as e:
        print(f"Error fetching HN Who Is Hiring: {e}")

    print(f"📡 HN Who Is Hiring: {len(hn_jobs)} relevant remote posts found.")
    return hn_jobs


# ─────────────────────────────────────────────
# WORKATASTARTUP — YC companies hiring
# Direct access to YC-backed startups, high quality signal
# ─────────────────────────────────────────────
def fetch_workatastartup_jobs() -> list:
    """
    Fetches engineering roles from Work at a Startup (YC companies).
    These are founder-direct, high equity, high growth roles.
    """
    was_jobs = []

    try:
        # YC's job board API endpoint
        res = requests.get(
            "https://www.workatastartup.com/jobs.json?role=eng&remote=true",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if res.status_code == 200:
            jobs = res.json() if isinstance(res.json(), list) else res.json().get("jobs", [])
            for j in jobs:
                loc = str(j.get("location", "")).lower()
                # Only worldwide/remote eligible
                if any(bad in loc for bad in ["us only", "onsite", "in-person"]):
                    if "remote" not in loc and "worldwide" not in loc:
                        continue
                was_jobs.append({
                    "company": j.get("company", {}).get("name", "YC Startup") if isinstance(j.get("company"), dict) else str(j.get("company", "YC Startup")),
                    "title": j.get("title", "Engineer"),
                    "url": j.get("url", f"https://www.workatastartup.com/jobs/{j.get('id', '')}"),
                    "description": j.get("description", ""),
                    "location": j.get("location", "Remote")
                })
    except Exception as e:
        print(f"Error fetching WorkAtAStartup: {e}")

    print(f"📡 WorkAtAStartup (YC): {len(was_jobs)} remote engineering roles found.")
    return was_jobs


# ─────────────────────────────────────────────
# MASTER PIPELINE — combines all sources
# ─────────────────────────────────────────────
def scout_hidden_gems() -> list:
    """
    Combines all job sources into a single deduplicated pipeline.
    Order matters — higher signal sources go first so they
    win in case of URL collision.
    """
    all_found = []

    # Tier 1: Direct ATS boards — highest signal, founder-controlled
    all_found.extend(check_bulk_ats_boards())

    # Tier 2: YC companies — high growth, good equity
    all_found.extend(fetch_workatastartup_jobs())

    # Tier 3: HN Who Is Hiring — direct founder posts, low competition
    all_found.extend(fetch_hn_who_is_hiring())

    # Tier 4: Remotive — broad remote, some noise but good volume
    all_found.extend(fetch_remotive_jobs())

    # Tier 5: WWR — high competition but good for martech/growth feeds
    all_found.extend(fetch_weworkremotely_jobs())

    # Deduplicate by URL — first occurrence wins (higher tier preserved)
    seen_urls = set()
    deduped = []
    for job in all_found:
        url = job.get("url", "").strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(job)

    print(f"📦 Total unique listings sourced: {len(deduped)} across all channels.")
    return deduped


# ─────────────────────────────────────────────
# SINGLE PAGE SCRAPER (utility — used by other modules)
# ─────────────────────────────────────────────
def scrape_custom_job_page(url: str) -> dict:
    """
    Scrapes a single job page and returns structured job dict.
    Handles Lever, Greenhouse, Ashby, and generic pages.
    """
    try:
        response = requests.get(
            url, timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "nav", "footer"]):
            element.extract()

        text = " ".join(soup.get_text().split())

        parsed_url = urlparse(url)
        domain_parts = parsed_url.netloc.split('.')
        company = "Startup"
        if len(domain_parts) >= 2:
            company = domain_parts[-2].capitalize()
            if company in ["Lever", "Greenhouse", "Ashbyhq"] and len(domain_parts) >= 3:
                path_parts = parsed_url.path.strip('/').split('/')
                if path_parts:
                    company = path_parts[0].capitalize()

        h1 = soup.find('h1')
        title = h1.get_text().strip() if h1 else "Software Engineer"

        return {
            "company": company,
            "title": title,
            "url": url,
            "description": text
        }
    except Exception as e:
        print(f"⚠️ Failed to scrape custom job page: {e}")
        return {
            "company": "External Role",
            "title": "Software Engineer",
            "url": url,
            "description": "Scraping failed."
        }
