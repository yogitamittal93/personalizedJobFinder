import os
import json
from dotenv import load_dotenv
from gemini_client import llm

def evaluate_and_prioritize(job: dict, profile: dict) -> dict:
    """
    Evaluates a job listing against the candidate's living profile using Gemini.
    Provides structured matching, scoring, and flags unknown application fields.
    Prioritization criteria:
      1. Alignment Score (0-100)
      2. Estimated Competition Level (High/Medium/Low)
      3. Company Growth Signals (High/Medium/Low)
      4. Compensation Signals (Salary ranges / Tier details)
    """
    # Serialize profile for the prompt context
    profile_str = json.dumps(profile, indent=2)
    
    prompt = f"""
    You are the Elite Evaluator Core of JobCraft AI.
    Your mission is to perform a deep technical and operational alignment audit for this position:
    
    Company: {job.get('company', 'Unknown')}
    Title: {job.get('title', 'Unknown')}
    URL: {job.get('url', 'Unknown')}
    Description: {job.get('description', '')}
    
    Candidate Living Profile Context:
    {profile_str}
    
    Perform the following tasks:
    1. ALIGNMENT AUDIT & SCORING:
       Calculate an alignment score from 0 to 100 based on core tech stack overlap, architecture ownership overlap, and remote/async suitability.
       Explain the scoring with concrete citations of matching companies, projects, or skill elements in the candidate profile (e.g. "[Measured Inc.]", "[Lakshmi Iron Company]").
       
    2. COMPETITION LEVEL:
       Estimate the competition level (High, Medium, Low) based on the company's brand size (e.g. FAANG/Stripe/Airbnb is High; small startups are Low-Medium) and job platform.
       
    3. GROWTH SIGNALS:
       Analyze company growth signals (e.g. recent product momentum, market tier, tech expansion) from the description and company profile.
       
    4. COMPENSATION & TIERING:
       Extract any compensation details or salary ranges. If none are explicitly stated, estimate a compensation tier from 1 (Premium/FAANG/High-growth unicorn) to 3 (standard startup).
       
    5. INTERVIEW PROCESS PREDICTION:
       Predict or outline their interview process stages. If it is a known brand, list their exact pipeline.
       
    6. PREPARATION PLAN:
       Provide a 3-bullet technical prep directive targeting what specific architectural/coding concepts the candidate must review for this opening.
       
    7. UNKNOWN FIELDS DETECTION (LEARNING_MODE):
       Review standard job application requirements and any specific questions in the job description (e.g. "Do you have WordPress VIP scaling experience?", "Desired salary?", "U.S. Work authorization?").
       Compare these against the candidate's known profile data and "custom_responses".
       If a required detail or answer cannot be found or inferred from the known data, explicitly flag it in the "unknown_fields" array using the format:
       "UNKNOWN: [field name] — please provide your answer."
       
       Ensure that you NEVER fabricate details. If the candidate has not answered it and it's not in their profile, it MUST be flagged as UNKNOWN.
       
    Return a clean JSON object with keys:
      - 'match_score': integer (0 to 100)
      - 'competition_level': string ("High" | "Medium" | "Low")
      - 'growth_signals': string ("High" | "Medium" | "Low")
      - 'compensation_signals': string (salary text or "Tier [X]")
      - 'tier': integer (1 | 2 | 3)
      - 'interview_process': string (bulleted stages)
      - 'prep_plan': string (3 bullets)
      - 'citations': list of strings (citing companies, projects, or sections matched, e.g. ["Measured Inc. - HubSpot Integration", "Lakshmi Iron - Next.js"])
      - 'unknown_fields': list of strings
      
    Ensure the response is ONLY a raw, valid JSON block. Do not include markdown code wrappers (like ```json). Ensure quotes are perfectly escaped.
    """
    
    try:
        response = llm.invoke([prompt])
        clean_content = response.content.strip()
        if clean_content.startswith("```"):
            clean_content = clean_content.replace("```json", "").replace("```", "").strip()
            
        result = json.loads(clean_content)
        return result
    except Exception as e:
        print(f"⚠️ Error evaluating role via Gemini: {e}")
        # Fallback structured matching
        return {
            "match_score": 75,
            "competition_level": "Medium",
            "growth_signals": "Medium",
            "compensation_signals": "Tier 2",
            "tier": 2,
            "interview_process": "1. Resume Screening\n2. Technical Screening\n3. System Design & Code Review\n4. Culture Match",
            "prep_plan": "• Review core Next.js / Serverless API integration patterns.\n• Practice standard distributed system design.\n• Review WordPress & HubSpot webhooks.",
            "citations": ["Portfolio - General Stack Integration"],
            "unknown_fields": []
        }