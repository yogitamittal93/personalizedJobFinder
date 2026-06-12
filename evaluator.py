import os
import json
from dotenv import load_dotenv
from gemini_client import llm

load_dotenv()


def evaluate_and_prioritize(job: dict, profile: dict, search_goals: dict = None) -> dict:
    """
    Evaluates a job listing against the candidate profile AND search goals using Gemini.

    Scoring is weighted toward what Yogita is actually looking for:
    - martech / email automation roles
    - ecommerce / DTC / WordPress
    - growth engineering / founding engineer
    - generalist senior roles at early-stage startups

    Returns a dict with match_score, eval_status, and all analysis fields.
    eval_status = 'verified'   → Gemini scored it successfully
    eval_status = 'unverified' → Gemini failed, fallback used, review manually
    """
    profile_str = json.dumps(profile, indent=2)

    # Build the search goals section for the prompt
    if search_goals:
        goals_str = f"""
=== CANDIDATE'S SEARCH GOALS (use these to weight the score) ===
Target Roles: {', '.join(search_goals.get('target_roles', []))}

Priority Signals (reward roles that match these):
{chr(10).join(f'  + {p}' for p in search_goals.get('priorities', []))}

Candidate Strengths to Match Against JD:
{', '.join(search_goals.get('strengths', []))}

Deal Breakers (heavily penalise or score 0 if present):
{chr(10).join(f'  - {d}' for d in search_goals.get('deal_breakers', []))}

SCORING GUIDANCE:
- A role that matches 3+ priority signals AND uses 4+ of her strengths = 85-100
- A standard full-stack role with some overlap = 70-84
- A role that conflicts with any deal breaker = score it 0-30 regardless of tech overlap
- Pure ML researcher / C++ systems / US work auth required = 0
- eCommerce + email automation + remote = strong bonus, push score up
- "Founding engineer" or "generalist" language in JD = strong bonus
"""
    else:
        goals_str = "No search goals provided — score purely on tech stack overlap."

    prompt = f"""
You are the Elite Evaluator Core of JobCraft AI.
Your mission is to perform a deep alignment audit for this position against
Yogita Singla's profile AND her specific search goals.

=== TARGET POSITION ===
Company: {job.get('company', 'Unknown')}
Title: {job.get('title', 'Unknown')}
URL: {job.get('url', 'Unknown')}
Description: {job.get('description', '')}

=== CANDIDATE LIVING PROFILE ===
{profile_str}

{goals_str}

=== EVALUATION TASKS ===

1. ALIGNMENT SCORE (0-100):
   Score based on:
   a) Tech stack overlap with candidate's strengths
   b) Role type match against target roles list
   c) Priority signal matches (each match = +5 to +10 points)
   d) Deal breaker penalties (any match = -40 to -100 points)
   Cite specific matches from profile (e.g. "[HubSpot at Measured Inc.]", "[WooCommerce — Gardens Alive]").

2. WHY IT FITS (1-2 sentences):
   A concise human-readable reason why this role suits Yogita specifically.
   Reference her actual background. E.g. "Klaviyo integration role matches her
   lifecycle automation work at Gardens Alive and Measured Inc."
   If it does NOT fit well, say so honestly.

3. COMPETITION LEVEL:
   High = FAANG / Stripe / well-known brand with 1000s of applicants
   Medium = Series B-D startup, recognisable name
   Low = early stage, niche tool, or indie company

4. GROWTH SIGNALS:
   High / Medium / Low — based on JD language, company stage, market tier.

5. COMPENSATION & TIERING:
   Extract explicit salary if mentioned. Otherwise estimate:
   Tier 1 = $120k+ USD equivalent
   Tier 2 = $80-120k USD equivalent
   Tier 3 = below $80k or unknown

6. INTERVIEW PROCESS PREDICTION:
   Based on company type and size, outline expected stages (1-2 lines each).
   If it is a known company, describe their actual process.

7. PREPARATION PLAN (3 bullets):
   Specific to THIS role and THIS company. Not generic advice.
   Reference Yogita's existing experience where relevant.

8. UNKNOWN FIELDS DETECTION:
   Scan the JD for application questions or requirements not in the profile
   (e.g. "salary expectation", "US work auth", "years with X framework").
   Flag anything that cannot be answered from existing profile data.

=== OUTPUT FORMAT ===
Return ONLY a raw valid JSON object. No markdown fences. No explanation outside JSON.

Keys required:
{{
  "match_score": <integer 0-100>,
  "why_fit": <string — 1-2 sentences, honest fit summary>,
  "competition_level": <"High" | "Medium" | "Low">,
  "growth_signals": <"High" | "Medium" | "Low">,
  "compensation_signals": <string>,
  "tier": <1 | 2 | 3>,
  "interview_process": <string — bulleted stages>,
  "prep_plan": <string — 3 specific bullets>,
  "citations": <list of strings>,
  "unknown_fields": <list of strings>
}}

Ensure all string values use escaped quotes where needed. Valid JSON only.
"""

    try:
        response = llm.invoke([prompt])
        clean_content = response.content.strip()

        # Strip markdown fences if Gemini wraps the response
        if clean_content.startswith("```"):
            clean_content = clean_content.replace("```json", "").replace("```", "").strip()

        result = json.loads(clean_content)

        # Enforce bounds — Gemini occasionally returns 101 or -5
        result['match_score'] = max(0, min(100, int(result.get('match_score', 0))))

        # Mark as verified — Gemini scored it successfully
        result['eval_status'] = 'verified'

        return result

    except Exception as e:
        print(f"⚠️ Gemini evaluation failed for {job.get('company')} — {job.get('title')}: {e}")

        # ── Fallback: store at 75 but mark as UNVERIFIED ─────────────────
        # The digest email will show ⚠️ next to this job so you know
        # to review it manually before applying.
        return {
            "match_score": 75,
            "why_fit": "⚠️ Unverified — Gemini failed. Review this role manually.",
            "competition_level": "Unknown",
            "growth_signals": "Unknown",
            "compensation_signals": "Unknown",
            "tier": 2,
            "interview_process": (
                "1. Resume Screening\n"
                "2. Technical Screening\n"
                "3. System Design & Code Review\n"
                "4. Culture Match"
            ),
            "prep_plan": (
                "• Review core Next.js / Node.js / NestJS patterns.\n"
                "• Practice WordPress / WooCommerce integration scenarios.\n"
                "• Review HubSpot / Klaviyo webhook and API integration patterns."
            ),
            "citations": ["Fallback — Gemini API unavailable"],
            "unknown_fields": [],
            "eval_status": "unverified"   # ← key flag — main.py reads this
        }
