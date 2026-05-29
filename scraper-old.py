import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

def scrape_portfolio(url: str) -> str:
    """Extracts text content and custom tech stacks from your portfolio website."""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(["script", "style", "footer", "nav"]):
            element.extract()
        return " ".join(soup.get_text().split())
    except Exception as e:
        return f"Portfolio scraping failed: {str(e)}"

def scout_hidden_gems() -> list[dict]:
    """Fetches high-paying, low-competition remote jobs hiring Worldwide."""
    scouted_jobs = []
    # Targeted global-first brand list
   target_companies = ["GitLab", "Automattic", "Buffer", "Zapier", "DuckDuckGo", "Ghost", "Atlassian", "Shopify", "GitHub", "GitBook", "Notion", "Figma", "Discord", "Stripe", "Airbnb", "Spotify", "Block", "Coinbase", "HashiCorp", "MongoDB", "Slack", "Pinterest", "HubSpot", "Confluent", "Affirm", "Allstate", "Reddit", "CrowdStrike", "Twilio", "Gladly", "Close", "Alma", "Remote.com", "Superside", "Quantum Metric", "Toptal", "Crossover", "InVision", "Doist", "Basecamp", "Prevently", "Looker", "Datadog", "DigitalOcean", "Linode", "Rocket Company", "Toggl", "Time Doctor", "Weatherstack", "AnswerThePublic", "Ramp", "Plaid", "Brex", "Arc", "Deel", "Mercury", "N26", "Wise", "Revolut", "Klarna", "Adyen", "Miro", "Canva", "Airtable", "Coda", "Linear", "Vercel", "Netlify", "Render", "Railway", "Supabase", "PlanetScale", "Neon", "Turso", "Hugging Face", "Anthropic", "Cohere", "Scale AI", "Adept AI", "Character.ai", "Runway", "Midjourney", "Stability AI", "Cerebras", "SambaNova", "Lambda Labs", "GetYourGuide", "Delivery Hero", "Zalando", "SoundCloud", "Booking.com", "Philips", "ASML", "King", "iZettle", "Scania", "Ericsson", "IKEA", "Unity", "Novo Nordisk", "Maersk", "Siemens", "SAP", "TeamViewer", "Celonis", "Personio", "Bunq", "Mollie", "Razorpay", "Cred", "Zerodha", "Groww", "Pickrr", "Postman", "Freshworks", "Zoho", "BrowserStack", "Chargebee", "Dream11", "Unacademy", "UpGrad", "Hasura", "Turing", "Andela", "Calendly", "Loom", "Retool", "Grist", "Superfluid", "Snapshot", "Gitcoin"]
    # We Work Remotely RSS Feed
    url = "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss"
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, features="xml")
        
        for item in soup.find_all('item'):
            description = item.description.text if item.description else ""
            title = item.title.text if item.title else ""
            link = item.link.text if item.link else ""
            
            is_worldwide = "worldwide" in title.lower() or "anywhere" in title.lower()
            is_high_tier = any(comp.lower() in title.lower() for comp in target_companies) or "usd" in description.lower() or "€" in description.lower()
            
            if is_worldwide and is_high_tier:
                scouted_jobs.append({
                    "company": title.split(":")[0] if ":" in title else "Startup/High-Paying",
                    "title": title,
                    "url": link,
                    "description": description
                })
    except Exception as e:
        print(f"Error fetching jobs: {e}")
        
    return scouted_jobs