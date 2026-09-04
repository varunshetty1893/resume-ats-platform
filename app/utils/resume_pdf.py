"""Turns resume-builder form fields into an actual downloadable PDF.

Supports both simple legacy parameters and rich structured multi-section resumes
with selectable ATS-friendly templates (Modern, Professional, Minimal, Executive).
"""

import io
import json
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


def parse_resume_to_structured_dict(raw_text: str, default_name: str = "", default_role: str = "") -> Dict[str, Any]:
    """Parse stored resume text back into structured dictionary."""
    if raw_text and raw_text.strip().startswith('{"__structured__": true'):
        try:
            return json.loads(raw_text)
        except Exception:
            pass

    # Default scaffold
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
