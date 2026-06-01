import os
import json
import re
import time
from dotenv import load_dotenv
from gemini_client import llm

load_dotenv()

TAILORED_RESUMES_DIR = os.path.join(os.path.dirname(__file__), "tailored_resumes")

def compile_tex_to_pdf(tex_path: str) -> str:
    """
    Attempts to compile a LaTeX file (.tex) to PDF (.pdf) using pdflatex.
    Runs twice to resolve cross-references. Cleans up aux files after.
    """
    import subprocess
    import shutil

    if not shutil.which("pdflatex"):
        print("⚠️ Warning: 'pdflatex' not found in PATH. Skipping PDF compilation.")
        print("💡 Tip: Install MiKTeX (Windows) or TeX Live (Linux/Mac) to enable local PDF generation.")
        return ""

    tex_dir = os.path.dirname(tex_path)
    tex_file = os.path.basename(tex_path)
    base_name = os.path.splitext(tex_file)[0]

    print(f"📄 Compiling LaTeX → PDF: {tex_file}...")
    try:
        for pass_num in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_file],
                cwd=tex_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                print(f"❌ pdflatex failed on pass {pass_num + 1}:")
                # Show last 30 lines of output for debugging
                output_lines = result.stdout.split('\n')
                print('\n'.join(output_lines[-30:]))
                return ""

        # Clean up LaTeX auxiliary files
        for ext in [".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk"]:
            aux_file = os.path.join(tex_dir, base_name + ext)
            if os.path.exists(aux_file):
                os.remove(aux_file)

        pdf_path = os.path.join(tex_dir, base_name + ".pdf")
        if os.path.exists(pdf_path):
            print(f"✅ PDF compiled successfully: {pdf_path}")
            return pdf_path
        else:
            print("⚠️ pdflatex returned success but no PDF found.")
            return ""

    except subprocess.TimeoutExpired:
        print("❌ pdflatex timed out (>120s). Check for infinite loops in LaTeX code.")
        return ""
    except Exception as e:
        print(f"❌ PDF compilation error: {e}")
        return ""


def extract_jd_keywords(job_description: str) -> list[str]:
    """
    Simple keyword extractor — pulls capitalized tech terms from the job description
    to give the LLM a pre-seeded list to mirror in the resume.
    """
    # Common tech keyword patterns
    tech_pattern = re.compile(
        r'\b(React|Next\.js|Node\.js|TypeScript|JavaScript|Python|PHP|Laravel|WordPress|'
        r'HubSpot|Shopify|PostgreSQL|MySQL|MongoDB|Redis|Docker|Kubernetes|AWS|GCP|Azure|'
        r'GraphQL|REST(?:ful)?|API|CI/CD|Git(?:Hub)?|Vercel|Netlify|Supabase|TailwindCSS|'
        r'Vue\.js|Angular|Svelte|Express|Prisma|tRPC|Stripe|Figma|Storybook|Jest|Cypress|'
        r'A/B testing|SEO|CMS|E-commerce|SaaS|B2B|B2C|microservice|serverless|'
        r'full.?stack|front.?end|back.?end|DevOps|Agile|Scrum|Jira|Linear)\b',
        re.IGNORECASE
    )
    keywords = list(set(tech_pattern.findall(job_description)))
    return keywords[:30]  # Cap at 30 to keep prompt manageable


def generate_tailored_resume(job: dict, profile: dict) -> tuple[str, str]:
    """
    Generates a tailored, ATS-optimized LaTeX resume AND a rich Alignment Audit Markdown
    report (including interview prep playbook) for the given job posting.

    Rules:
    1. NEVER fabricate skills, projects, or experiences not in the candidate profile.
    2. Every resume bullet MUST cite its source as a LaTeX comment.
    3. The LaTeX output must be ATS-safe: single-column, no tables, no graphics.
    4. Always OVERWRITE existing files — never serve stale cached resumes.
    """
    if not os.path.exists(TAILORED_RESUMES_DIR):
        os.makedirs(TAILORED_RESUMES_DIR)

    company = job.get('company', 'Company')
    title = job.get('title', 'Role')
    company_clean = re.sub(r'\W+', '', company).capitalize()
    title_clean = re.sub(r'\W+', '', title).capitalize()

    tex_path = os.path.join(TAILORED_RESUMES_DIR, f"{company_clean}_{title_clean}_Resume.tex")
    md_path = os.path.join(TAILORED_RESUMES_DIR, f"{company_clean}_{title_clean}_Alignment.md")
    pdf_path = os.path.join(TAILORED_RESUMES_DIR, f"{company_clean}_{title_clean}_Resume.pdf")

    # Always delete stale files to force fresh regeneration
    for stale_path in [tex_path, md_path, pdf_path]:
        if os.path.exists(stale_path):
            try:
                os.remove(stale_path)
            except Exception:
                pass

    job_description = job.get('description', '')
    profile_str = json.dumps(profile, indent=2)

    # Pre-extract JD keywords to help the LLM do proper ATS mirroring
    jd_keywords = extract_jd_keywords(job_description)
    jd_keywords_str = ", ".join(jd_keywords) if jd_keywords else "See job description above"

    prompt = rf"""
You are the Elite Resume Tailoring Engine of JobCraft AI.
Your SOLE objective is to produce a resume and alignment audit for Yogita Singla that makes her the PERFECT candidate for this specific role — maximizing both ATS score and human HR impression.

=== TARGET POSITION ===
Company: {company}
Role: {title}
Job Description:
{job_description}

=== CANDIDATE LIVING PROFILE ===
{profile_str}

=== PRE-EXTRACTED JD KEYWORDS (must appear naturally in resume) ===
{jd_keywords_str}

=== CRITICAL GENERATION RULES ===
1. ZERO FABRICATION: Every skill, project, metric, and achievement must exist VERBATIM or be directly inferrable from the candidate profile above. Do NOT invent numbers, companies, or technologies.
2. ATS KEYWORD MIRRORING: Every keyword from the JD keyword list above MUST appear in the resume exactly as written in the job description (case-sensitive where it matters, e.g. "Next.js" not "NextJS"). This is mandatory for ATS parsing.
3. CITATION COMMENTS: Insert a LaTeX comment `% Citation: [source]` above EVERY bullet point or section entry. Source must be one of: [candidate_profile.json], [Portfolio Website], [base_resume].
4. ATS-SAFE LATEX: Single column only. No `tabular`, `table`, or `multicol`. No `\includegraphics`. No custom fonts. Use only: geometry, hyperref, titlesec, enumitem, fontenc, inputenc.
5. QUANTIFY EVERYTHING: Use exact metrics from the profile (e.g. "reduced page load by 40%", "served 50k+ daily users"). Never write vague bullets like "worked on" or "helped with".
6. PROFESSIONAL SUMMARY: Write a 3-sentence tailored summary that uses the company's exact language from the JD. Include the role title naturally.
7. SKILLS SECTION ORDER: List skills in order of relevance to THIS specific job description — most relevant first.

=== OUTPUT FORMAT ===
Return EXACTLY two blocks separated by this delimiter on its own line:
JOBCRAFT_SPLIT_DELIMITER

Block 1 (BEFORE the delimiter): Raw LaTeX code starting immediately with \\documentclass. No markdown fences. No explanation.

Block 2 (AFTER the delimiter): Markdown alignment audit starting immediately with # Alignment Audit. No markdown fences. No explanation.

=== LATEX RESUME TEMPLATE TO FOLLOW ===
\\documentclass[10pt,letterpaper]{{article}}
\\usepackage[T1]{{fontenc}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[margin=0.65in]{{geometry}}
\\usepackage[hidelinks]{{hyperref}}
\\usepackage{{titlesec}}
\\usepackage{{enumitem}}

\\pagestyle{{empty}}

% ATS-optimized section headers
\\titleformat{{\\section}}{{\\large\\bfseries\\uppercase}}{{}}{{0em}}{{}}[\\titlerule]
\\titlespacing{{\\section}}{{0pt}}{{8pt}}{{4pt}}

\\setlist[itemize]{{leftmargin=*, noitemsep, topsep=2pt}}

\\begin{{document}}

\\begin{{center}}
    {{\\LARGE \\textbf{{Yogita Singla}}}} \\\\
    \\vspace{{3pt}}
    \\href{{mailto:yogitamittal.tech@gmail.com}}{{yogitamittal.tech@gmail.com}} $\\mid$
    \\href{{https://portfolio-three-sigma-mp0vvhcq3h.vercel.app/}}{{Portfolio}} $\\mid$
    \\href{{https://github.com/yogitamittal93}}{{GitHub}} $\\mid$
    Remote / India
\\end{{center}}

\\vspace{{-4pt}}

\\section{{Professional Summary}}
% Citation: [candidate_profile.json + tailored for {company} {title}]
[3-sentence tailored summary mirroring JD language. Must include role title and company's core mission.]

\\section{{Core Technical Skills}}
% Citation: [candidate_profile.json — skills section]
\\textbf{{Languages:}} [Ordered by JD relevance] \\\\
\\textbf{{Frameworks \\& Libraries:}} [Ordered by JD relevance] \\\\
\\textbf{{Databases:}} [From profile, relevant ones first] \\\\
\\textbf{{Tools \\& Platforms:}} [DevOps, CMS, APIs relevant to JD] \\\\
\\textbf{{Soft Skills:}} [From profile, relevant to JD]

\\section{{Professional Experience}}
[For EACH experience in profile, write 3-5 bullets. Use STAR format: Situation/Task + Action + Result with metric.
 Add % Citation: [CompanyName — source] above each company block AND each bullet.]

\\section{{Projects \\& Open Source}}
[List most relevant projects. Each entry: Project Name | Tech Stack | Outcome metric
 Add % Citation: [project source] above each entry.]

\\section{{Education}}
[From profile. Degree, Institution, Year.]

\\end{{document}}

=== ALIGNMENT AUDIT MARKDOWN TEMPLATE TO FOLLOW ===

# Alignment Audit — {company} ({title})

## ATS Keyword Coverage
| JD Keyword | Present in Resume | Source Citation |
|---|---|---|
[Fill one row per keyword from the JD keyword list. Mark ✅ if present, ❌ if genuinely not in profile]

**Estimated ATS Match Score: XX/100**
*(Based on keyword coverage, section structure, and format compliance)*

## Skill Alignment Summary
[Which of candidate's skills directly match the JD requirements. Be specific.]

## Genuine Skill Gaps
[Honestly list any JD requirements NOT present in the candidate profile. Do NOT fabricate. If no gaps, state "No material gaps detected."]

## Resume Tailoring Decisions
[Explain the 3-5 most important tailoring choices made and why.]

## Interview Preparation Playbook

### Stage 1: Recruiter / HR Screen (15-30 min)
- **Key questions to expect:** [3-4 specific questions for this company/role]
- **Your anchor stories:** [Which profile experience to cite for each]
- **Salary expectation anchor:** [Suggested range based on role tier]

### Stage 2: Technical Phone Screen (45-60 min)
- **Topics to review:** [Specific tech from JD, not generic]
- **Practice problems:** [2-3 targeted coding/architecture problems relevant to this role]
- **Expected format:** [Live coding / take-home / system design — based on company type]

### Stage 3: Technical Deep Dive / System Design Round
- **System design scenario:** [A realistic design problem relevant to this company's domain]
- **Architecture talking points:** [3 specific patterns from Yogita's profile to highlight]
- **Key technologies to demonstrate:** [From JD keyword list]

### Stage 4: Culture Fit / Behavioral Round
- **Company values to address:** [From JD/company description]
- **Suggested STAR stories from profile:** [Map specific experiences to STAR format]
- **Questions to ask the interviewer:** [2-3 smart questions showing domain knowledge]

### Stage 5: Final / Bar Raiser (if applicable)
- **What to expect:** [Based on company size/type]
- **Differentiator to emphasize:** [Yogita's strongest unique value proposition for this role]

## Application Cover Letter Hook
[Write a 2-3 sentence cold-pitch opening paragraph that could open a cover letter or cold email to the hiring manager. Tailored to this specific role.]

## Citations & Sources
- Candidate Profile: candidate_profile.json
- Portfolio: https://portfolio-three-sigma-mp0vvhcq3h.vercel.app/
- Job Description Source: {job.get('url', 'Provided')}
- Generated: Auto-tailored by JobCraft AI Resume Engine
"""

    print(f"🚀 Tailoring ATS-optimized resume for: {company} — {title}...")
    print(f"   📌 JD keywords to mirror: {len(jd_keywords)} extracted")

    max_retries = 3
    retry_delay = 65  # seconds — respects per-minute free tier limits

    for attempt in range(1, max_retries + 1):
        try:
            response = llm.invoke([prompt])
            content = response.content.strip()

            # Remove any outer markdown code fences the LLM might wrap around the whole output
            if content.startswith("```"):
                # Strip the first and last fence
                content = re.sub(r'^```[a-z]*\n', '', content)
                content = re.sub(r'\n```$', '', content)

            # Split on the exact delimiter — robust to surrounding whitespace/newlines
            parts = re.split(r'\s*JOBCRAFT_SPLIT_DELIMITER\s*', content, maxsplit=1)

            if len(parts) == 2:
                latex_code = parts[0].strip()
                alignment_audit = parts[1].strip()
            else:
                # Fallback: try to detect where LaTeX ends and Markdown begins
                latex_end_match = re.search(r'\\end\{document\}', content)
                if latex_end_match:
                    split_idx = latex_end_match.end()
                    latex_code = content[:split_idx].strip()
                    alignment_audit = content[split_idx:].strip()
                    if not alignment_audit.startswith("#"):
                        alignment_audit = "# Alignment Audit\n\nNote: Audit section could not be cleanly separated from LaTeX output. Please review the full response.\n\n" + alignment_audit
                else:
                    # Can't separate — save full content for debugging
                    latex_code = content
                    alignment_audit = "# Alignment Audit\n\n⚠️ The AI did not return the split delimiter. Full output saved in the .tex file for manual review."

            # Clean up any residual markdown fences inside each block
            latex_code = re.sub(r'^```latex\s*\n?', '', latex_code)
            latex_code = re.sub(r'\n?```\s*$', '', latex_code)
            alignment_audit = re.sub(r'^```markdown\s*\n?', '', alignment_audit)
            alignment_audit = re.sub(r'\n?```\s*$', '', alignment_audit)

            # Validate the LaTeX output looks real
            if '\\documentclass' not in latex_code:
                raise ValueError("LLM output does not contain valid LaTeX (missing \\documentclass). Retrying...")

            # Write files
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(latex_code)
            print(f"✅ ATS-optimized LaTeX resume written: {tex_path}")

            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(alignment_audit)
            print(f"📋 Alignment Audit + Interview Prep written: {md_path}")

            # Compile to PDF
            compile_tex_to_pdf(tex_path)

            return tex_path, md_path

        except ValueError as ve:
            # Structural issue with LLM output — retry
            print(f"⚠️ Attempt {attempt}/{max_retries} — Output validation failed: {ve}")
            if attempt < max_retries:
                print(f"   ⏳ Retrying in {retry_delay}s to respect rate limits...")
                time.sleep(retry_delay)
            continue

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                # Extract retry delay from error if available
                delay_match = re.search(r'retry[_\s]?delay[:\s]+[\'"]?(\d+)', err_str, re.IGNORECASE)
                suggested_delay = int(delay_match.group(1)) + 5 if delay_match else retry_delay
                print(f"⚠️ Attempt {attempt}/{max_retries} — Gemini quota hit (429). Waiting {suggested_delay}s before retry...")
                if attempt < max_retries:
                    time.sleep(suggested_delay)
                continue
            else:
                print(f"❌ Attempt {attempt}/{max_retries} — Unexpected error: {e}")
                if attempt < max_retries:
                    time.sleep(10)
                continue

    # All retries exhausted — write informative fallback files
    print(f"❌ All {max_retries} attempts failed. Writing diagnostic fallback files.")
    fallback_latex = f"""% JobCraft AI — Resume generation failed after {max_retries} retries
% Company: {company}
% Role: {title}
% Please re-run Mode 4 when API quota resets (usually after 24h for free tier).
\\documentclass[10pt]{{article}}
\\begin{{document}}
\\textbf{{Resume for Yogita Singla — {company} ({title})}}\\\\
Resume generation failed due to API quota limits. Please try again later.
\\end{{document}}"""

    fallback_md = f"""# Alignment Audit — {company} ({title})

> ⚠️ **Resume generation failed after {max_retries} retries.**

**Likely cause:** Gemini API free-tier daily quota exhausted (limit: 20 requests/day on gemini-2.5-flash).

**What to do:**
1. Wait 24 hours for quota to reset, then re-run Mode 4.
2. Or add a second `GOOGLE_API_KEY2` to your repository Secrets to enable key rotation.
3. Check your API quota dashboard: https://ai.dev/rate-limit

**Job Details Saved:**
- Company: {company}
- Role: {title}
- URL: {job.get('url', 'N/A')}
"""

    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(fallback_latex)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(fallback_md)

    return tex_path, md_path
