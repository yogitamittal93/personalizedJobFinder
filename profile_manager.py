import os
import sys
import json
import glob
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass
from pypdf import PdfReader
from dotenv import load_dotenv
from gemini_client import llm
from scraper import scrape_portfolio

load_dotenv()

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "candidate_profile.json")
BASE_RESUMES_DIR = os.path.join(os.path.dirname(__file__), "base_resumes")

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts plain text from a PDF resume file."""
    try:
        reader = PdfReader(pdf_path)
        text_content = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text_content.append(text)
        return "\n".join(text_content)
    except Exception as e:
        print(f"⚠️ Warning: Could not parse PDF {pdf_path}: {e}")
        return ""

def load_base_resumes() -> dict:
    """Reads all PDF, TXT, or MD resume documents from the base_resumes directory."""
    raw_resumes = {}
    if not os.path.exists(BASE_RESUMES_DIR):
        os.makedirs(BASE_RESUMES_DIR)
        return raw_resumes

    # Scan for PDF files
    pdf_files = glob.glob(os.path.join(BASE_RESUMES_DIR, "*.pdf"))
    for file in pdf_files:
        basename = os.path.basename(file)
        print(f"📄 Found base PDF resume: {basename}")
        text = extract_text_from_pdf(file)
        if text.strip():
            raw_resumes[basename] = text

    # Scan for TXT/MD files
    txt_files = glob.glob(os.path.join(BASE_RESUMES_DIR, "*.txt")) + glob.glob(os.path.join(BASE_RESUMES_DIR, "*.md"))
    for file in txt_files:
        basename = os.path.basename(file)
        print(f"📄 Found base text resume: {basename}")
        try:
            with open(file, 'r', encoding='utf-8') as f:
                raw_resumes[basename] = f.read()
        except Exception as e:
            print(f"⚠️ Warning: Could not read text file {basename}: {e}")

    return raw_resumes

def ingest_profile(portfolio_url: str, force_rebuild: bool = False) -> dict:
    """
    Ingests PDF/text resumes and the candidate's portfolio.
    Builds a high-fidelity, living model candidate_profile.json if it doesn't exist,
    or merges any new findings into the existing one.
    """
    if os.path.exists(PROFILE_PATH) and not force_rebuild:
        print("💾 Living profile already exists. Loading candidate_profile.json...")
        try:
            with open(PROFILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            print("⚠️ Profile parsing failed. Rebuilding...")

    print("🔍 Ingesting raw materials to build fresh Living Profile...")
    
    # 1. Scrape Portfolio
    print(f"🌐 Scraping portfolio: {portfolio_url}")
    portfolio_text = scrape_portfolio(portfolio_url)
    
    # 2. Load Base Resumes
    resumes_data = load_base_resumes()
    
    # 3. Assemble Gemini Prompt
    resumes_input = ""
    for name, content in resumes_data.items():
        resumes_input += f"\n--- RESUME FILE: {name} ---\n{content}\n"
        
    prompt = f"""
    You are the Profile Ingestion Core of JobCraft AI.
    Your mission is to parse the candidate's raw profile data from their portfolio website and any attached resume documents, then assemble a living, structured JSON candidate profile.
    
    CRITICAL RULE:
    1. Never fabricate any skills, metrics, projects, or experiences.
    2. Every item in the final JSON MUST track a strict source citation stating exactly where it was pulled from (e.g. "portfolio_website" or "resume_v1.pdf" or "[Filename]").
    
    Candidate Portfolio Scraped Text:
    {portfolio_text}
    
    Candidate Resumes:
    {resumes_input if resumes_input else "No resumes provided in base_resumes/ folder."}
    
    Format the response as a valid, parsable JSON object with the following schema:
    {{
      "personal_info": {{
        "full_name": "...",
        "email": "...",
        "portfolio": "...",
        "location": "...",
        "title": "..."
      }},
      "career_narrative": {{
        "elevator_pitch": "...",
        "tone_guidelines": "..."
      }},
      "experiences": [
        {{
          "company": "...",
          "title": "...",
          "bullet_points": ["...", "..."],
          "citation": "..."
        }}
      ],
      "skills": {{
        "languages": ["..."],
        "frameworks": ["..."],
        "databases": ["..."],
        "tools_platforms": ["..."],
        "citations": {{
          "SkillName": "..."
        }}
      }},
      "projects": [
        {{
          "name": "...",
          "description": "...",
          "tech_stack": ["..."],
          "role": "...",
          "citation": "..."
        }}
      ],
      "custom_responses": {{}}
    }}
    
    Return ONLY a raw, parsable JSON block. Do not include markdown code wrappers (like ```json). Ensure keys are perfectly closed.
    """
    
    print("🧠 Ingesting through Gemini to model skills, stories, and experiences...")
    try:
        response = llm.invoke([prompt])
        clean_content = response.content.strip()
        if clean_content.startswith("```"):
            clean_content = clean_content.replace("```json", "").replace("```", "").strip()
            
        profile = json.loads(clean_content)
        
        # Ensure custom_responses block exists
        if "custom_responses" not in profile:
            profile["custom_responses"] = {}
            
        # Save to disk
        with open(PROFILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2)
            
        print(f"✨ Living Profile successfully generated and saved to: {PROFILE_PATH}")
        return profile
    except Exception as e:
        print(f"❌ Failed to parse or generate profile: {e}")
        # Return fallback dummy profile
        fallback = {
            "personal_info": {
                "full_name": "Yogita Singla",
                "email": "yogitamittal.tech@gmail.com",
                "portfolio": portfolio_url,
                "location": "India / Remote",
                "title": "Full-Stack Engineer & Architect"
            },
            "career_narrative": {
                "elevator_pitch": "13+ years of building e-commerce and marketing engineering pipelines.",
                "tone_guidelines": "Metric-driven, technical, high ownership."
            },
            "experiences": [],
            "skills": {
                "languages": ["PHP", "JavaScript", "TypeScript"],
                "frameworks": ["Next.js", "React Native"],
                "databases": ["Supabase", "MySQL"],
                "tools_platforms": ["HubSpot", "WordPress"],
                "citations": {}
            },
            "projects": [],
            "custom_responses": {}
        }
        with open(PROFILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(fallback, f, indent=2)
        return fallback

def update_learned_response(field_name: str, candidate_answer: str) -> dict:
    """Updates candidate_profile.json with a custom response (LEARNING_MODE)."""
    profile = ingest_profile(scrape_portfolio) # Loads or creates
    
    if "custom_responses" not in profile:
        profile["custom_responses"] = {}
        
    profile["custom_responses"][field_name] = candidate_answer
    
    with open(PROFILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2)
        
    print(f"💾 Learnt: Absorbed answer for '{field_name}' into Living Profile.")
    return profile
