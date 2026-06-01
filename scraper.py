import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urlparse

def scrape_portfolio(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "footer", "nav"]):
            element.extract()
        return " ".join(soup.get_text().split())
    except Exception as e:
        return f"Portfolio scraping failed: {str(e)}"

def is_location_eligible(location: str, company: str) -> bool:
    """
    Checks if a job location is suitable for a candidate remote in India.
    Filters out strictly local/on-site roles in other countries (e.g. US-only, UK-only).
    """
    loc = str(location).lower()
    comp = str(company).lower()
    
    # 1. Indian companies (always eligible for remote or local in India)
    indian_companies = [
        "razorpay", "freshworks", "browserstack", "chargebee", 
        "cred", "zerodha", "groww", "hasura"
    ]
    if comp in indian_companies:
        return True
        
    # 2. Explicitly restricted locations (not suitable for India)
    # Filter out US-only, Europe-only, Americas-only, EMEA-only, LATAM-only, etc.
    restricted_keywords = [
        "us only", "usa only", "united states", "canada", "north america", "europe only", 
        "emea", "latam", "americas only", "strictly us", "strictly usa", "germany strictly",
        "uk only", "united kingdom", "london", "berlin", "munich", "san francisco", "new york",
        "boston", "austin", "seattle", "chicago", "los angeles", "denver"
    ]
    if any(rk in loc for rk in restricted_keywords):
        # Unless it also explicitly mentions "India" or "Worldwide" or "Global"
        if not ("india" in loc or "worldwide" in loc or "global" in loc or "anywhere" in loc):
            return False
            
    # 3. Explicitly suitable locations
    suitable_keywords = [
        "india", "remote", "worldwide", "anywhere", "global", "apac", "asia", "bengaluru",
        "bangalore", "delhi", "mumbai", "pune", "hyderabad", "chennai", "noida", "gurgaon"
    ]
    if any(sk in loc for sk in suitable_keywords):
        return True
        
    # Default to True to avoid false negatives on blank/unstated locations for global remote companies
    return True

def check_bulk_ats_boards() -> list[dict]:
    """
    Queries public ATS API channels for all target companies simultaneously.
    Maps company names to their exact system subdomains, filtering for India/Global Remote eligibility.
    """
    found_jobs = []
    
    # 1. GREENHOUSE TARGETS — expanded company list
    greenhouse_companies = [
        # Developer tools & infrastructure
        "vercel", "netlify", "supabase", "planetscale", "neon", "railway", "render",
        "duckduckgo", "postman", "hashicorp", "mongodb", "confluent", "cockroachlabs",
        # Design & productivity
        "figma", "airtable", "notion", "linear", "loom", "coda", "miro",
        # Fintech & payments
        "stripe", "brex", "ramp", "plaid", "mercury", "deel", "rippling", "patreon",
        "affirm", "coinbase", "kraken", "robinhood",
        # Marketing & CRM
        "hubspot", "klaviyo", "attentive", "iterable", "amplitude", "mixpanel",
        # E-commerce
        "shopify", "klaviyo", "recharge", "gorgias", "yotpo", "nacelle",
        # AI & ML
        "huggingface", "anthropic", "cohere", "scaleai", "adept", "runway",
        "stabilityai", "mistral", "perplexity", "together",
        # Media & social
        "reddit", "pinterest", "soundcloud", "discord", "twitch",
        # Cloud & DevOps
        "crowdstrike", "datadog", "newrelic", "grafana", "sentry",
        # Global remote-first
        "zapier", "buffer", "doist", "toggl", "hotjar", "papercup",
        # Indian & APAC
        "razorpay", "freshworks", "browserstack", "chargebee", "clevertap",
        "postman", "hasura", "zepto", "groww", "cred",
        # General remote
        "calendly", "retool", "webflow", "framer", "ghost", "gitbook",
        "twilio", "sendgrid", "segment", "contentful", "sanity"
    ]
    
    # 2. LEVER TARGETS — expanded company list
    lever_companies = [
        "buffer", "zapier", "ghost", "atlassian", "gitbook", "close",
        "digitalocean", "canva", "turso", "character", "bunq", "mollie",
        "zerodha", "andela", "grist", "doist", "hotjar", "typeform",
        "intercom", "drift", "front", "liveblocks", "stytch", "clerk",
        "resend", "dub", "novu", "trigger", "inngest", "cal",
        "formbricks", "midday", "papermark", "documenso"
    ]
    
    # 3. ASHBY TARGETS — expanded list
    ashby_companies = [
        "linear", "railway", "clerk", "resend", "dub", "liveblocks",
        "novu", "trigger", "cal", "mintlify", "unkey", "openstatus"
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

    print(f"📡 Querying Ashby job boards...")
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

def fetch_us_germany_startups() -> list[dict]:
    """Fetches high-paying global-remote startup listings from Remotive API."""
    startup_jobs = []
    
    # Multiple categories to widen the net
    categories = ["software-dev", "frontend", "backend", "fullstack", "devops-sysadmin"]
    
    for category in categories:
        try:
            remotive_url = f"https://remotive.com/api/remote-jobs?category={category}&limit=50"
            res = requests.get(remotive_url, timeout=10)
            if res.status_code == 200:
                all_jobs = res.json().get("jobs", [])
                for j in all_jobs:
                    geo = j.get("candidate_required_location", "").lower()
                    is_eligible = (
                        not geo or  # No location restriction = worldwide
                        "worldwide" in geo or
                        "anywhere" in geo or
                        "global" in geo or
                        "india" in geo or
                        "apac" in geo or
                        "asia" in geo
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


def fetch_weworkremotely_jobs() -> list[dict]:
    """Fetches remote programming jobs from We Work Remotely RSS feed."""
    wwr_jobs = []
    feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    ]
    
    for feed_url in feeds:
        try:
            res = requests.get(feed_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                for item in root.findall(".//item"):
                    title_el = item.find("title")
                    link_el = item.find("link")
                    desc_el = item.find("description")
                    
                    if title_el is None or link_el is None:
                        continue
                    
                    raw_title = title_el.text or ""
                    # WWR titles are usually "Company: Role Title"
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
                        # Strip CDATA HTML tags for plain text
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

def scout_hidden_gems() -> list[dict]:
    """Combines all target macro filters into a single deduplicated pipeline output."""
    all_found = []
    
    all_found.extend(check_bulk_ats_boards())
    all_found.extend(fetch_us_germany_startups())
    all_found.extend(fetch_weworkremotely_jobs())
    
    # Deduplicate by URL
    seen_urls = set()
    deduped_jobs = []
    for job in all_found:
        if job["url"] and job["url"] not in seen_urls:
            seen_urls.add(job["url"])
            deduped_jobs.append(job)
            
    print(f"📦 Total unique listings sourced: {len(deduped_jobs)} across all channels.")
    return deduped_jobs

def scrape_custom_job_page(url: str) -> dict:
    """
    Scrapes a specific single job application page (lever, greenhouse, or generic).
    Parses title, company, and description.
    """
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strip script/style tags
        for element in soup(["script", "style", "nav", "footer"]):
            element.extract()
            
        text = " ".join(soup.get_text().split())
        
        parsed_url = urlparse(url)
        domain_parts = parsed_url.netloc.split('.')
        company = "Startup"
        if len(domain_parts) >= 2:
            company = domain_parts[-2].capitalize()
            if company in ["Lever", "Greenhouse", "Ashbyhq"] and len(domain_parts) >= 3:
                # E.g. jobs.lever.co/company -> use URL path
                path_parts = parsed_url.path.strip('/').split('/')
                if path_parts:
                    company = path_parts[0].capitalize()
                    
        # Guess title from header tags
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