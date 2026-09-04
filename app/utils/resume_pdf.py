"""Turns resume-builder form fields into an actual downloadable PDF.

Supports both simple legacy parameters and rich structured multi-section resumes
with selectable ATS-friendly templates (Modern, Professional, Minimal, Executive).
"""

import io
import json
import re
import html
from typing import Dict, List, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


# Color themes for ATS-friendly templates
TEMPLATE_THEMES = {
    "modern": {
        "primary": colors.HexColor("#4338CA"),    # Indigo
        "text": colors.HexColor("#0B0F19"),       # Ink
        "muted": colors.HexColor("#64748B"),      # Slate
        "divider": colors.HexColor("#E2E8F0"),    # Border
        "font_name": "Helvetica",
        "font_bold": "Helvetica-Bold",
    },
    "professional": {
        "primary": colors.HexColor("#1E293B"),    # Deep Navy
        "text": colors.HexColor("#0F172A"),       # Dark Slate
        "muted": colors.HexColor("#475569"),      # Medium Slate
        "divider": colors.HexColor("#CBD5E1"),    # Border
        "font_name": "Helvetica",
        "font_bold": "Helvetica-Bold",
    },
    "minimal": {
        "primary": colors.HexColor("#000000"),    # Monochrome
        "text": colors.HexColor("#111827"),       # Charcoal
        "muted": colors.HexColor("#4B5563"),      # Gray
        "divider": colors.HexColor("#E5E7EB"),    # Light Gray
        "font_name": "Helvetica",
        "font_bold": "Helvetica-Bold",
    },
    "executive": {
        "primary": colors.HexColor("#0F766E"),    # Deep Teal
        "text": colors.HexColor("#134E4A"),       # Dark Teal
        "muted": colors.HexColor("#475569"),      # Slate
        "divider": colors.HexColor("#99F6E4"),    # Mint Divider
        "font_name": "Helvetica",
        "font_bold": "Helvetica-Bold",
    },
}


def structured_resume_to_plain_text(data: Dict[str, Any]) -> str:
    """Convert a structured resume dictionary into clean plain text for ATS scoring."""
    parts = []

    personal = data.get("personal", {})
    name = personal.get("full_name") or ""
    title = personal.get("title") or ""
    if name or title:
        parts.append(f"{name} — {title}".strip(" —"))

    contact_parts = [p for p in [personal.get("email"), personal.get("phone"), personal.get("location")] if p]
    if contact_parts:
        parts.append(" · ".join(contact_parts))

    summary = data.get("summary", "").strip()
    if summary:
        parts.append("SUMMARY\n" + summary)

    exps = data.get("experience", [])
    if exps:
        exp_lines = ["EXPERIENCE"]
        for e in exps:
            t = e.get("title", "")
            c = e.get("company", "")
            s = e.get("start_date", "")
            end = "Present" if e.get("current") else e.get("end_date", "")
            exp_lines.append(f"{t} at {c} ({s} - {end})".strip())
            for b in e.get("bullets", []):
                if b and b.strip():
                    exp_lines.append(f"• {b.strip()}")
            if not e.get("bullets") and e.get("description"):
                for line in e["description"].split("\n"):
                    if line.strip():
                        exp_lines.append(f"• {line.strip(' •-*')}")
        parts.append("\n".join(exp_lines))

    edus = data.get("education", [])
    if edus:
        edu_lines = ["EDUCATION"]
        for ed in edus:
            deg = ed.get("degree", "")
            fld = ed.get("field", "")
            inst = ed.get("institution", "")
            yr = ed.get("year", "")
            edu_lines.append(f"{deg} in {fld} — {inst} ({yr})".strip(" —()"))
        parts.append("\n".join(edu_lines))

    skills = data.get("skills", {})
    if isinstance(skills, dict) and any(skills.values()):
        sk_lines = ["SKILLS"]
        for cat, items in skills.items():
            if items:
                items_str = ", ".join(items) if isinstance(items, list) else str(items)
                sk_lines.append(f"{cat.replace('_', ' ').title()}: {items_str}")
        parts.append("\n".join(sk_lines))
    elif isinstance(skills, list) and skills:
        parts.append("SKILLS\n" + ", ".join(skills))
    elif isinstance(skills, str) and skills.strip():
        parts.append("SKILLS\n" + skills.strip())

    projs = data.get("projects", [])
    if projs:
        p_lines = ["PROJECTS"]
        for p in projs:
            p_lines.append(f"{p.get('name', '')} ({p.get('role', '')})".strip(" ()"))
            techs = p.get("technologies", [])
            if techs:
                p_lines.append("Technologies: " + (", ".join(techs) if isinstance(techs, list) else str(techs)))
            for b in p.get("bullets", []):
                if b and b.strip():
                    p_lines.append(f"• {b.strip()}")
            if not p.get("bullets") and p.get("description"):
                for line in p["description"].split("\n"):
                    if line.strip():
                        p_lines.append(f"• {line.strip(' •-*')}")
        parts.append("\n".join(p_lines))

    certs = data.get("certifications", [])
    if certs:
        c_lines = ["CERTIFICATIONS"]
        for c in certs:
            c_lines.append(f"• {c.get('name', '')} — {c.get('issuer', '')} ({c.get('year', '')})".strip(" —()"))
        parts.append("\n".join(c_lines))

    return "\n\n".join(parts)


def _get_default_scaffold(default_name: str = "", default_role: str = "") -> Dict[str, Any]:
    """Return an empty structured resume dictionary scaffold."""
    return {
        "__structured__": True,
        "template": "modern",
        "personal": {
            "full_name": default_name or "",
            "title": default_role or "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
            "github": "",
            "portfolio": "",
            "links": [],
        },
        "summary": "",
        "experience": [],
        "education": [],
        "skills": {
            "languages": [],
            "frameworks": [],
            "databases": [],
            "tools": [],
            "cloud": [],
            "other": [],
        },
        "projects": [],
        "certifications": [],
        "achievements": [],
    }


def parse_plain_text_to_structured(raw_text: str, default_name: str = "", default_role: str = "") -> Dict[str, Any]:
    """Parse plain-text resume into structured dictionary for ReportLab ATS generation."""
    lines = [line.strip() for line in (raw_text or "").splitlines()]
    structured = _get_default_scaffold(default_name, default_role)

    if not lines or not any(lines):
        return structured

    # Standard section heading patterns
    section_patterns = {
        "summary": re.compile(r"^(?:#*\s*)(?:.*SUMMARY|.*OBJECTIVE|PROFILE|ABOUT\s+ME)\s*[:\-]*$", re.I),
        "skills": re.compile(r"^(?:#*\s*)(?:.*SKILLS|.*COMPETENCIES|TECHNOLOGIES|AREAS\s+OF\s+EXPERTISE)\s*[:\-]*$", re.I),
        "experience": re.compile(r"^(?:#*\s*)(?:.*EXPERIENCE|.*EMPLOYMENT|WORK\s+HISTORY)\s*[:\-]*$", re.I),
        "projects": re.compile(r"^(?:#*\s*)(?:.*PROJECTS|OPEN\s+SOURCE.*)\s*[:\-]*$", re.I),
        "education": re.compile(r"^(?:#*\s*)(?:EDUCATION.*|ACADEMIC.*|QUALIFICATIONS.*)\s*[:\-]*$", re.I),
        "certifications": re.compile(r"^(?:#*\s*)(?:CERTIFICATION.*|LICENSES.*|CERTIFICATES.*)\s*[:\-]*$", re.I),
        "achievements": re.compile(r"^(?:#*\s*)(?:ACHIEVEMENT.*|AWARDS.*|HONORS.*|PUBLICATIONS.*)\s*[:\-]*$", re.I),
    }

    # 1. Identify section boundary positions
    section_positions = []
    for idx, line in enumerate(lines):
        if not line:
            continue
        for sec_name, pattern in section_patterns.items():
            if pattern.match(line):
                section_positions.append((idx, sec_name, line))
                break

    # 2. Extract header / personal info (before the first section)
    first_sec_idx = section_positions[0][0] if section_positions else len(lines)
    header_lines = [l for l in lines[:first_sec_idx] if l]
    header_blob = " | ".join(header_lines)

    candidate_name = ""
    title = default_role or ""

    if header_lines:
        first_line = header_lines[0]
        # Avoid treating file extensions, URLs, or generic resume labels as candidate name
        if not re.search(r"(\.pdf|\.docx|resume|curriculum\s+vitae|@)", first_line, re.I):
            candidate_name = re.sub(r"[#*]", "", first_line).strip()

    if not candidate_name:
        clean_default = re.sub(r"(\.pdf|\.docx|_resume.*|\bpdf\b)", "", default_name, flags=re.I).replace("_", " ").strip()
        candidate_name = clean_default or "Candidate"

    if len(header_lines) > 1:
        for hl in header_lines[1:]:
            if not re.search(r"[@\+0-9]", hl) and len(hl) < 90 and not any(x in hl.lower() for x in ["linkedin", "github", "portfolio", "http", "www."]):
                title = re.sub(r"[#*]", "", hl).strip()
                break

    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", header_blob)
    email = email_match.group(0) if email_match else ""

    phone_match = re.search(r"(\+?\d{1,4}[-.\s]?)?\(?\d{2,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}", header_blob)
    phone = phone_match.group(0).strip() if phone_match else ""

    linkedin_match = re.search(r"(?:https?:\/\/)?(?:www\.)?(linkedin\.com\/in\/[a-zA-Z0-9_\-\.\%]+)", header_blob, re.I)
    linkedin = f"https://{linkedin_match.group(1)}" if linkedin_match else ""

    github_match = re.search(r"(?:https?:\/\/)?(?:www\.)?(github\.com\/[a-zA-Z0-9_\-\.\%]+)", header_blob, re.I)
    github = f"https://{github_match.group(1)}" if github_match else ""

    portfolio_match = re.search(r"(?:https?:\/\/)?(?:www\.)?([a-zA-Z0-9_\-]+\.(?:dev|me|io|portfolio|site)(?:\/[a-zA-Z0-9_\-\.\%]*)?)", header_blob, re.I)
    portfolio = f"https://{portfolio_match.group(1)}" if portfolio_match else ""

    location = ""
    for part in re.split(r"[\t\n|•]+", header_blob):
        part = part.strip()
        if not part or part in [candidate_name, title, email, phone]:
            continue
        if any(x in part.lower() for x in ["linkedin", "github", "http", "@", ".com", ".dev", ".io"]):
            continue
        if re.search(r"\d{3,}", part):
            continue
        if len(part) < 60 and any(c.isalpha() for c in part):
            location = part
            break

    structured["personal"] = {
        "full_name": candidate_name,
        "title": title,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "github": github,
        "portfolio": portfolio,
        "links": [l for l in [linkedin, github, portfolio] if l],
    }

    date_regex = re.compile(
        r"(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)?\s*\d{4}\s*(?:[-–—to]+\s*(?:Present|\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}))?\b)",
        re.I,
    )

    # 3. Process each section block
    for i, (start_idx, sec_name, heading_text) in enumerate(section_positions):
        end_idx = section_positions[i + 1][0] if i + 1 < len(section_positions) else len(lines)
        block_lines = [l for l in lines[start_idx + 1:end_idx] if l]
        block_text = "\n".join(block_lines).strip()

        if sec_name == "summary":
            structured["summary"] = block_text

        elif sec_name == "skills":
            skills_dict = {}
            flat_skills = []
            for line in block_lines:
                clean_l = line.strip(" •-*#")
                cat_match = re.match(r"^([^:\n]{2,35}):\s*(.*)$", clean_l)
                if cat_match:
                    cat_name = cat_match.group(1).strip()
                    items_str = cat_match.group(2).strip()
                    items = [it.strip(" •-*") for it in re.split(r"[,•|/]+", items_str) if it.strip()]
                    skills_dict[cat_name] = items
                else:
                    items = [it.strip(" •-*") for it in re.split(r"[,•|/]+", clean_l) if it.strip()]
                    flat_skills.extend(items)

            if skills_dict:
                if flat_skills:
                    skills_dict["Other Skills"] = flat_skills
                structured["skills"] = skills_dict
            elif flat_skills:
                structured["skills"] = {"Technical Skills": flat_skills}
            else:
                structured["skills"] = block_text

        elif sec_name == "experience":
            experiences = []
            current_exp = None

            for line in block_lines:
                is_bullet = bool(re.match(r"^[\s•\-\*\>]+|\s{2,}", line))
                clean_line = re.sub(r"^[\s•\-\*\>]+", "", line).strip()

                date_match = date_regex.search(clean_line)
                is_pure_date = date_match and (
                    len(clean_line) < 35 or
                    re.match(r"^(?:[A-Za-z]+\s*\d{4}|\d{4})\s*[-–—to]+\s*(?:Present|[A-Za-z]+\s*\d{4}|\d{4})$", clean_line, re.I)
                )

                if current_exp and is_pure_date and not current_exp.get("start_date") and not current_exp.get("bullets"):
                    date_parts = re.split(r"[-–—to]+", clean_line)
                    current_exp["start_date"] = date_parts[0].strip() if len(date_parts) > 0 else ""
                    current_exp["end_date"] = date_parts[1].strip() if len(date_parts) > 1 else ""
                    current_exp["current"] = "present" in current_exp["end_date"].lower()
                    continue

                if not is_bullet and (date_match or "|" in line or "–" in line or "-" in line or current_exp is None):
                    if current_exp:
                        experiences.append(current_exp)

                    parts = [p.strip() for p in re.split(r"[|•–—]+", clean_line) if p.strip()]
                    exp_title = parts[0] if len(parts) > 0 else "Role"
                    company = parts[1] if len(parts) > 1 else ""
                    exp_loc = ""
                    date_str = ""

                    for p in parts[2:]:
                        if re.search(r"\d{4}|present", p, re.I):
                            date_str = p
                        else:
                            exp_loc = p

                    start_date = ""
                    end_date = ""
                    is_current = False
                    if date_str:
                        date_parts = re.split(r"[-–—to]+", date_str)
                        start_date = date_parts[0].strip() if len(date_parts) > 0 else ""
                        end_date = date_parts[1].strip() if len(date_parts) > 1 else ""
                        is_current = "present" in end_date.lower()

                    current_exp = {
                        "title": exp_title,
                        "company": company,
                        "location": exp_loc,
                        "start_date": start_date,
                        "end_date": end_date,
                        "current": is_current,
                        "bullets": [],
                    }
                else:
                    if current_exp is not None:
                        current_exp["bullets"].append(clean_line)

            if current_exp:
                experiences.append(current_exp)
            structured["experience"] = experiences

        elif sec_name == "projects":
            projects = []
            curr_proj = None
            for line in block_lines:
                is_bullet = bool(re.match(r"^[\s•\-\*\>]+|\s{2,}", line))
                clean_line = re.sub(r"^[\s•\-\*\>]+", "", line).strip()

                if not is_bullet and ("–" in line or "|" in line or "-" in line or ":" in line or curr_proj is None):
                    if curr_proj:
                        projects.append(curr_proj)
                    parts = [p.strip() for p in re.split(r"[:|–—]+", clean_line, 1) if p.strip()]
                    p_name = parts[0] if parts else "Project"
                    desc_part = parts[1] if len(parts) > 1 else ""
                    curr_proj = {
                        "name": p_name,
                        "role": "",
                        "technologies": [],
                        "link": "",
                        "bullets": [desc_part] if desc_part else [],
                    }
                else:
                    if curr_proj is not None:
                        curr_proj["bullets"].append(clean_line)

            if curr_proj:
                projects.append(curr_proj)
            structured["projects"] = projects

        elif sec_name == "education":
            edu_list = []
            for line in block_lines:
                clean_l = re.sub(r"^[\s•\-\*\>]+", "", line).strip()
                parts = [p.strip() for p in re.split(r"[|–—]+", clean_l) if p.strip()]
                degree_part = parts[0] if parts else clean_l
                inst = parts[1] if len(parts) > 1 else ""
                year = ""
                for p in parts:
                    yr_match = re.search(r"(\b\d{4}(?:\s*[-–—]\s*\d{4})?\b)", p)
                    if yr_match:
                        year = yr_match.group(0)
                        break
                edu_list.append({
                    "degree": degree_part,
                    "field": "",
                    "institution": inst,
                    "year": year,
                    "gpa": "",
                })
            structured["education"] = edu_list

        elif sec_name == "certifications":
            cert_list = []
            for line in block_lines:
                clean_l = re.sub(r"^[\s•\-\*\>]+", "", line).strip()
                if not clean_l:
                    continue
                items = re.split(r"(?:[•\n]|\s{3,})", clean_l)
                for item in items:
                    item = item.strip(" •-*")
                    if not item:
                        continue
                    parts = [p.strip() for p in re.split(r"[–—\-]+", item) if p.strip()]
                    c_name = parts[0]
                    c_issuer = parts[1] if len(parts) > 1 else ""
                    cert_list.append({
                        "name": c_name,
                        "issuer": c_issuer,
                        "year": "",
                        "url": "",
                    })
            structured["certifications"] = cert_list

        elif sec_name == "achievements":
            ach_list = []
            for line in block_lines:
                clean_line = re.sub(r"^[\s•\-\*\>]+", "", line).strip()
                if clean_line:
                    ach_list.append(clean_line)
            structured["achievements"] = ach_list

    # Fallback: if no sections were parsed at all, preserve all text in summary
    if not section_positions and raw_text.strip():
        structured["summary"] = raw_text.strip()

    return structured


def parse_resume_to_structured_dict(raw_text: str, default_name: str = "", default_role: str = "") -> Dict[str, Any]:
    """Parse stored resume text back into structured dictionary.
    
    Handles both structured builder JSON payloads and uploaded / plain text resumes.
    """
    if not raw_text or not raw_text.strip():
        return _get_default_scaffold(default_name, default_role)

    if raw_text.strip().startswith('{"__structured__": true'):
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return parse_plain_text_to_structured(raw_text, default_name, default_role)


def build_structured_resume_pdf(resume_data: Dict[str, Any], template: str = "modern") -> io.BytesIO:
    """Build a comprehensive, multi-page aware ATS PDF from structured resume data."""
    theme = TEMPLATE_THEMES.get(template.lower(), TEMPLATE_THEMES["modern"])
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        "Name", parent=styles["Title"],
        fontName=theme["font_bold"],
        fontSize=20, leading=24,
        textColor=theme["text"],
        spaceAfter=2, alignment=0,
    )
    title_style = ParagraphStyle(
        "Role", parent=styles["Normal"],
        fontName=theme["font_bold"],
        fontSize=11, leading=14,
        textColor=theme["primary"],
        spaceAfter=4,
    )
    contact_style = ParagraphStyle(
        "Contact", parent=styles["Normal"],
        fontName=theme["font_name"],
        fontSize=9, leading=12,
        textColor=theme["muted"],
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"],
        fontName=theme["font_bold"],
        fontSize=11, leading=14,
        spaceBefore=12, spaceAfter=4,
        textColor=theme["primary"],
    )
    item_header_style = ParagraphStyle(
        "ItemHeader", parent=styles["Normal"],
        fontName=theme["font_bold"],
        fontSize=10, leading=13,
        textColor=theme["text"],
    )
    item_sub_style = ParagraphStyle(
        "ItemSub", parent=styles["Normal"],
        fontName=theme["font_name"],
        fontSize=9, leading=12,
        textColor=theme["muted"],
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontName=theme["font_name"],
        fontSize=9.5, leading=13.5,
        textColor=theme["text"],
    )
    bullet_style = ParagraphStyle(
        "Bullet", parent=styles["Normal"],
        fontName=theme["font_name"],
        fontSize=9.5, leading=13,
        textColor=theme["text"],
        leftIndent=12,
        spaceAfter=2,
    )

    story = []

    # 1. Header (Personal Info)
    personal = resume_data.get("personal", {})
    full_name = personal.get("full_name") or "Your Name"
    title = personal.get("title") or ""
    email = personal.get("email") or ""
    phone = personal.get("phone") or ""
    location = personal.get("location") or ""
    linkedin = personal.get("linkedin") or ""
    github = personal.get("github") or ""
    portfolio = personal.get("portfolio") or ""

    story.append(Paragraph(full_name, name_style))
    if title:
        story.append(Paragraph(title, title_style))

    contact_parts = [p for p in [email, phone, location] if p]
    links_list = personal.get("links") or []
    if isinstance(links_list, list) and links_list:
        contact_parts.extend([l.strip() for l in links_list if isinstance(l, str) and l.strip()])
    else:
        contact_parts.extend([p for p in [linkedin, github, portfolio] if p])
    if contact_parts:
        contact_line = "  ·  ".join(contact_parts)
        story.append(Paragraph(contact_line, contact_style))

    story.append(HRFlowable(width="100%", color=theme["divider"], thickness=0.75, spaceAfter=4))

    # 2. Professional Summary
    summary = resume_data.get("summary", "").strip()
    if summary:
        story.append(Paragraph("PROFESSIONAL SUMMARY", section_style))
        story.append(Paragraph(summary.replace("\n", "<br/>"), body_style))
        story.append(Spacer(1, 4))

    # 3. Experience
    experiences = resume_data.get("experience", [])
    if experiences:
        story.append(Paragraph("EXPERIENCE", section_style))
        for exp in experiences:
            job_title = exp.get("title", "")
            company = exp.get("company", "")
            exp_loc = exp.get("location", "")
            start = exp.get("start_date", "")
            end = "Present" if exp.get("current") else exp.get("end_date", "")

            date_str = f"{start} – {end}" if start or end else ""
            header_text = f"<b>{job_title}</b>"
            if company:
                header_text += f" | {company}"
            if exp_loc:
                header_text += f" ({exp_loc})"

            story.append(Paragraph(header_text, item_header_style))
            if date_str:
                story.append(Paragraph(date_str, item_sub_style))

            bullets = exp.get("bullets", [])
            if bullets:
                for b in bullets:
                    if b.strip():
                        story.append(Paragraph(f"• {b.strip()}", bullet_style))
            elif exp.get("description"):
                desc_lines = exp["description"].split("\n")
                for line in desc_lines:
                    if line.strip():
                        story.append(Paragraph(f"• {line.strip(' •-*')}", bullet_style))

            story.append(Spacer(1, 4))

    # 4. Education
    education_list = resume_data.get("education", [])
    if education_list:
        story.append(Paragraph("EDUCATION", section_style))
        for edu in education_list:
            degree = edu.get("degree", "")
            field = edu.get("field", "")
            inst = edu.get("institution", "")
            grad_year = edu.get("year", "")
            gpa = edu.get("gpa", "")

            edu_title = degree
            if field:
                edu_title += f" in {field}" if edu_title else field
            if inst:
                edu_title += f" | {inst}"

            story.append(Paragraph(f"<b>{edu_title}</b>", item_header_style))
            sub_parts = [p for p in [grad_year, f"GPA: {gpa}" if gpa else None] if p]
            if sub_parts:
                story.append(Paragraph("  ·  ".join(sub_parts), item_sub_style))
            story.append(Spacer(1, 3))

    # 5. Skills
    skills_data = resume_data.get("skills", {})
    if isinstance(skills_data, dict) and any(skills_data.values()):
        story.append(Paragraph("TECHNICAL SKILLS", section_style))
        for cat_name, skill_items in skills_data.items():
            if skill_items:
                if isinstance(skill_items, list):
                    skills_str = ", ".join(skill_items)
                else:
                    skills_str = str(skill_items)
                cat_label = cat_name.replace("_", " ").title()
                story.append(Paragraph(f"<b>{cat_label}:</b> {skills_str}", body_style))
        story.append(Spacer(1, 4))
    elif isinstance(skills_data, list) and skills_data:
        story.append(Paragraph("SKILLS", section_style))
        story.append(Paragraph(", ".join(skills_data), body_style))
        story.append(Spacer(1, 4))
    elif isinstance(skills_data, str) and skills_data.strip():
        story.append(Paragraph("SKILLS", section_style))
        story.append(Paragraph(skills_data.replace("\n", "<br/>"), body_style))
        story.append(Spacer(1, 4))

    # 6. Projects
    projects = resume_data.get("projects", [])
    if projects:
        story.append(Paragraph("PROJECTS", section_style))
        for proj in projects:
            p_name = proj.get("name", "")
            p_role = proj.get("role", "")
            p_tech = proj.get("technologies", [])
            p_link = proj.get("link", "")
            p_github = proj.get("github", "")

            p_title = f"<b>{p_name}</b>"
            if p_role:
                p_title += f" ({p_role})"
            story.append(Paragraph(p_title, item_header_style))

            tech_str = ", ".join(p_tech) if isinstance(p_tech, list) else str(p_tech or "")
            link_parts = [p for p in [f"Tech: {tech_str}" if tech_str else None, p_link, p_github] if p]
            if link_parts:
                story.append(Paragraph("  ·  ".join(link_parts), item_sub_style))

            p_bullets = proj.get("bullets", [])
            if p_bullets:
                for b in p_bullets:
                    if b.strip():
                        story.append(Paragraph(f"• {b.strip()}", bullet_style))
            elif proj.get("description"):
                for line in proj["description"].split("\n"):
                    if line.strip():
                        story.append(Paragraph(f"• {line.strip(' •-*')}", bullet_style))

            story.append(Spacer(1, 4))

    # 7. Certifications
    certs = resume_data.get("certifications", [])
    if certs:
        story.append(Paragraph("CERTIFICATIONS", section_style))
        for cert in certs:
            c_name = cert.get("name", "")
            c_issuer = cert.get("issuer", "")
            c_year = cert.get("year", "")
            c_url = cert.get("url", "")

            cert_text = f"<b>{c_name}</b>"
            if c_issuer:
                cert_text += f" — {c_issuer}"
            if c_year:
                cert_text += f" ({c_year})"
            if c_url:
                cert_text += f" | {c_url}"
            story.append(Paragraph(f"• {cert_text}", bullet_style))
        story.append(Spacer(1, 4))

    # 8. Achievements / Additional
    achievements = resume_data.get("achievements", [])
    if achievements:
        story.append(Paragraph("ACHIEVEMENTS & AWARDS", section_style))
        for ach in achievements:
            if isinstance(ach, str) and ach.strip():
                story.append(Paragraph(f"• {ach.strip()}", bullet_style))
            elif isinstance(ach, dict) and ach.get("title"):
                story.append(Paragraph(f"• <b>{ach.get('title')}</b>: {ach.get('description', '')}", bullet_style))
        story.append(Spacer(1, 4))

    doc.build(story)
    buffer.seek(0)
    return buffer


def build_resume_pdf(full_name, title, email, phone, summary, experience, education, skills):
    """Legacy backward-compatible PDF generator wrapper."""
    data = {
        "personal": {
            "full_name": full_name,
            "title": title,
            "email": email,
            "phone": phone,
        },
        "summary": summary,
        "experience": [{"title": "", "company": "", "description": experience}] if experience else [],
        "education": [{"degree": education, "institution": ""}] if education else [],
        "skills": skills,
    }
    return build_structured_resume_pdf(data, template="modern")
