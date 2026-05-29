import os
import json
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from gemini_client import llm

INTEL_DIR = os.path.join(os.path.dirname(__file__), "company_briefs")

def web_search_hiring_data(company: str, title: str) -> str:
    """
    Performs a lightweight, rate-limit-resistant search query on DuckDuckGo
    to gather live intelligence on the company's interview rounds and engineering culture.
    """
    query = f"{company} {title} interview process engineering culture"
    url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all('a', class_='result__snippet')
            snippets = []
            for r in results[:4]:
                snippets.append(r.get_text().strip())
            
            if snippets:
                print(f"📡 Web research successfully pulled {len(snippets)} insights for {company}.")
                return "\n".join(snippets)
    except Exception as e:
        print(f"⚠️ Web search bypass encountered error: {e}. Falling back to internal intelligence.")
        
    return ""

def compile_strategy_brief(job: dict, profile: dict) -> str:
    """
    Researches the target company and role, generating a comprehensive,
    premium Markdown Application Strategy Brief in INTEL_MODE.
    """
    if not os.path.exists(INTEL_DIR):
        os.makedirs(INTEL_DIR)
        
    company = job.get('company', 'Company')
    title = job.get('title', 'Role')
    
    company_clean = re.sub(r'\W+', '', company).capitalize()
    title_clean = re.sub(r'\W+', '', title).capitalize()
    brief_path = os.path.join(INTEL_DIR, f"{company_clean}_{title_clean}_Strategy.md")
    
    # 1. Fetch web intelligence
    search_context = web_search_hiring_data(company, title)
    
    profile_summary = {
        "name": profile.get("personal_info", {}).get("full_name"),
        "title": profile.get("personal_info", {}).get("title"),
        "key_companies": [exp.get("company") for exp in profile.get("experiences", [])],
        "top_skills": profile.get("skills", {}).get("languages", []) + profile.get("skills", {}).get("frameworks", [])
    }
    
    prompt = f"""
    You are the Application Strategy Director Core of JobCraft AI.
    Your mission is to compile an elite, detailed Application Strategy Brief for:
    
    Company: {company}
    Role: {title}
    Job URL: {job.get('url', 'Direct Link')}
    Job Description:
    {job.get('description', '')}
    
    Candidate High-Level Profile:
    {json.dumps(profile_summary, indent=2)}
    
    Web Scraped Search Context:
    {search_context if search_context else "No active web context available. Leverage your deep pre-trained knowledge of tech companies and engineering cultures."}
    
    Compile a complete, high-fidelity Markdown document containing the following structured sections:
    
    # Application Strategy Brief — {company} ({title})
    
    ## 1. Company Intelligence & Growth Signals
    - Brand Tier & Market Position (e.g. established leader, high-growth startup, seed stage).
    - Detected Growth Signals (recent product announcements, tech expansions, active hires, funding tier).
    - Mission & Cultural Anchors (what values do they put first?).
    
    ## 2. Competitive Landscape & Alignment Audit
    - Estimated Competition Level (High | Medium | Low) and explanation of why.
    - Candidate Core Strengths relative to this role (cite companies from their profile like Measured Inc., Spring Hill, etc.).
    - Skill Gaps or items in the job description not explicitly present in the profile (strictly avoid fabricating).
    
    ## 3. Targeted Application Narrative & Pitch
    - The hook: A professional, tailored cold-pitch or cover letter opening (incorporating Yogita's 13+ years experience and checkout stability/catalog automation achievements).
    - Alignment citations (how their profile experiences prove they can solve the role's primary pain point).
    
    ## 4. Predicted Interview Loop & Preparation Playbook
    - Detailed Stage-by-Stage predicted interview process (e.g., Round 1: Recruiter, Round 2: Tech Screening, Round 3: Take-home/Live architecture, Round 4: Bar raiser).
    - Targeted Prep Checklist: 3-5 specific advanced topics to study (e.g., WordPress plugin security, CRM webhooks, Next.js hydration optimizations).
    - Suggested system design or database schema questions related to their industry sector (e.g., industrial B2B sorting for Lakshmi Iron, or e-commerce scaling for Measured/Weeks).
    
    ## 5. Citations & References
    - State exactly which documents/sites were referenced (e.g., Portfolio Website, base_resumes, DuckDuckGo Search API).
    
    Produce ONLY the markdown content. Ensure it reads like a premium executive intelligence brief. Avoid any handwavy suggestions; provide precise, actionable guidance.
    """
    
    print(f"🧠 Synthesizing intelligence strategy brief for {company}...")
    try:
        response = llm.invoke([prompt])
        brief_md = response.content.strip()
        
        # Save to disk
        with open(brief_path, 'w', encoding='utf-8') as f:
            f.write(brief_md)
            
        print(f"✨ Strategy Brief written to: {brief_path}")
        return brief_path
    except Exception as e:
        print(f"❌ Failed to generate strategy brief: {e}")
        fallback_brief = f"""# Strategy Brief: {company} - {title}
Failed to generate brief due to error: {str(e)}
"""
        with open(brief_path, 'w') as f:
            f.write(fallback_brief)
        return brief_path
