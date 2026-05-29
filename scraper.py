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

def check_bulk_ats_boards() -> list[dict]:
    """
    Queries public ATS API channels for all target companies simultaneously.
    Maps company names to their exact system subdomains.
    """
    found_jobs = []
    
    # 1. GREENHOUSE TARGETS
    greenhouse_companies = [
        "duckduckgo", "vercel", "postman", "hashicorp", "hubspot", "figma", "stripe", 
        "airbnb", "spotify", "coinbase", "mongodb", "pinterest", "confluent", "affirm", 
        "twilio", "reddit", "crowdstrike", "ramp", "plaid", "brex", "deel", "mercury", 
        "airtable", "linear", "netlify", "supabase", "planetscale", "neon", "huggingface", 
        "anthropic", "cohere", "scaleai", "adept", "runway", "stabilityai", "getyourguide", 
        "deliveryhero", "zalando", "soundcloud", "booking", "unity3d", "celonis", "personio", 
        "razorpay", "freshworks", "browserstack", "chargebee", "calendly", "loom", "retool"
    ]
    
    # 2. LEVER TARGETS
    lever_companies = [
        "buffer", "zapier", "ghost", "atlassian", "gitbook", "notion", "slack", "close", 
        "digitalocean", "miro", "canva", "coda", "render", "railway", "turso", "character", 
        "bunq", "mollie", "cred", "zerodha", "groww", "hasura", "andela", "grist"
    ]
    
    # 3. ASHBY TARGETS
    ashby_companies = [
        "linear", "railway", "clerk", "resend", "dub"
    ]
 
    print(f"📡 Querying {len(greenhouse_companies)} Greenhouse job boards...")
    for company in greenhouse_companies:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                jobs = res.json().get("jobs", [])
                for j in jobs:
                    found_jobs.append({
                        "company": company.capitalize(),
                        "title": j["title"],
                        "url": j["absolute_url"],
                        "description": j.get("content", j["title"])
                    })
        except Exception:
            continue # Silently bypass rate limits or offline profiles

    print(f"📡 Querying {len(lever_companies)} Lever job boards...")
    for company in lever_companies:
        try:
            url = f"https://api.lever.co/v0/postings/{company}?mode=json"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                for j in res.json():
                    found_jobs.append({
                        "company": company.capitalize(),
                        "title": j["text"],
                        "url": j["hostedUrl"],
                        "description": j.get("description", "")
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
                    found_jobs.append({
                        "company": company.capitalize(),
                        "title": j["title"],
                        "url": j["jobUrl"],
                        "description": j.get("descriptionHtml", "")
                    })
        except Exception:
            continue

    return found_jobs

def fetch_us_germany_startups() -> list[dict]:
    """Fetches high-paying US/Europe startups explicitly hiring globally."""
    startup_jobs = []
    remotive_url = "https://remotive.com/api/remote-jobs?category=software-dev"
    
    try:
        res = requests.get(remotive_url, timeout=10)
        if res.status_code == 200:
            all_jobs = res.json().get("jobs", [])
            for j in all_jobs:
                geo = j.get("candidate_required_location", "").lower()
                is_worldwide = "worldwide" in geo or "anywhere" in geo or "global" in geo
                
                if is_worldwide:
                    startup_jobs.append({
                        "company": j.get("company_name", "Global Startup"),
                        "title": j.get("title", ""),
                        "url": j.get("url", ""),
                        "description": j.get("description", "")
                    })
    except Exception as e:
        print(f"Error checking startup API: {e}")
        
    return startup_jobs

def scout_hidden_gems() -> list[dict]:
    """Combines all target macro filters into a single pipeline output."""
    all_found = []
    
    all_found.extend(check_bulk_ats_boards())
    all_found.extend(fetch_us_germany_startups())
    
    # Deduplicate matching positions running across multiple aggregators
    seen_urls = set()
    deduped_jobs = []
    for job in all_found:
        if job["url"] not in seen_urls:
            seen_urls.add(job["url"])
            deduped_jobs.append(job)
            
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