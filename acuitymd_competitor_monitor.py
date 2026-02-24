#!/usr/bin/env python3
"""
Weekly competitor monitor for AcuityMD.

Scans 5 competitors (Veeva Systems, Definitive Healthcare, Alpha Sophia,
IQVIA MedTech, Carevoyance) for pricing changes, feature launches, and
announcements using Claude's web_search tool, then synthesizes a brief
and emails it via Gmail SMTP.

Usage:
    .venv/bin/python3 acuitymd_competitor_monitor.py              # Full scan + email
    .venv/bin/python3 acuitymd_competitor_monitor.py --dry-run    # Scan + print, skip email
    .venv/bin/python3 acuitymd_competitor_monitor.py --help       # Usage info

Setup:
    python3 -m venv .venv && .venv/bin/pip install anthropic
    Add CLAUDE_API_KEY and GMAIL_APP_PASSWORD to .env

Weekly cron:
    0 8 * * 1 cd /path/to/claude_site && .venv/bin/python3 acuitymd_competitor_monitor.py
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

COMPETITORS = [
    {
        "name": "Veeva Systems (MedTech Cloud)",
        "description": "Enterprise cloud platform for life sciences — CRM, content, quality, regulatory. Customers include Medtronic, BD, Philips.",
        "domains": "veeva.com",
        "context": "AcuityMD competes on being purpose-built for medtech sales vs Veeva's pharma-first approach. Veeva is heavyweight enterprise; AcuityMD is faster to deploy.",
    },
    {
        "name": "Definitive Healthcare",
        "description": "Broad healthcare data and analytics platform — hospital profiles, physician data, claims records. 9,000+ hospital profiles, 3M+ HCPs.",
        "domains": "definitivehc.com",
        "context": "AcuityMD competes on medtech-specific workflows vs Definitive's horizontal data platform. Definitive has broader data but no built-in sales tools for device reps.",
    },
    {
        "name": "Alpha Sophia",
        "description": "Affordable MedTech commercial intelligence platform targeting startups and SMBs. Claims ~80% of US medical claims data.",
        "domains": "alphasophia.com",
        "context": "Alpha Sophia positions as the cheaper alternative to AcuityMD. Competes on price and speed of deployment for smaller teams.",
    },
    {
        "name": "IQVIA MedTech",
        "description": "Global healthcare data and technology company — largest healthcare dataset, OCE CRM, real-world evidence, consulting.",
        "domains": "iqvia.com",
        "context": "IQVIA is primarily pharma-oriented with medtech as a secondary vertical. Competes on data scale and global footprint vs AcuityMD's medtech focus.",
    },
    {
        "name": "Carevoyance (by Definitive Healthcare)",
        "description": "Procedure-level commercial intelligence for medical device sales — CPT code volume by physician and facility, territory planning.",
        "domains": "definitivehc.com, carevoyance.com",
        "context": "Carevoyance is the most directly comparable competitor — same procedure-level targeting as AcuityMD. Acquired by Definitive Healthcare.",
    },
    {
        "name": "MedScout",
        "description": "Revenue acceleration platform for medtech — 310M+ patients, 34B+ claims translated into actionable sales insights. Founded 2020, Austin TX. $20.8M raised.",
        "domains": "medscout.io, medscout.cloud",
        "context": "MedScout is a direct competitor with very similar positioning — claims-based physician targeting for medtech sales reps. Competes on data freshness and rep-friendly UX, similar to AcuityMD.",
    },
    {
        "name": "RepSignal (S2N Health)",
        "description": "AI-powered commercial intelligence for medical device companies — 1.2M physicians, 50K+ facilities. Natively built on Salesforce. Pricing from $1,500/user.",
        "domains": "s2nhealth.com, repsignal.com",
        "context": "RepSignal competes on Salesforce-native integration — appeals to teams already on SFDC. AcuityMD differentiates on deeper medtech-specific workflows and standalone UX.",
    },
]

MODEL = "claude-sonnet-4-6"
EMAIL_TO = "gagan.bhatia@acuitymd.com"


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def api_call_with_retry(fn, label="API call"):
    """Call fn() with retry + backoff on rate limits. Returns response or None."""
    import anthropic as _anthropic

    for attempt in range(5):
        try:
            return fn()
        except _anthropic.RateLimitError:
            wait = 30 * (attempt + 1)
            print(f"    Rate limited on {label}, waiting {wait}s...")
            time.sleep(wait)
    print(f"    Failed {label} after retries.")
    return None


def scan_competitor(client, competitor):
    """Use Claude with web_search to find recent updates for a competitor."""
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    prompt = (
        f"Search for any recent news, updates, or changes about {competitor['name']} "
        f"({competitor['description']}) from the past 7 days ({week_ago} to {today}).\n\n"
        f"Look specifically for:\n"
        f"- Pricing changes or new plan tiers\n"
        f"- New product features or platform updates\n"
        f"- Major announcements, partnerships, acquisitions, or funding\n"
        f"- Earnings reports or significant business updates\n"
        f"- Notable blog posts, press releases, or industry event appearances\n\n"
        f"Relevant domains: {competitor['domains']}\n\n"
        f"Competitive context: {competitor['context']}\n\n"
        f"For each finding, include:\n"
        f"- What changed\n"
        f"- Why it matters competitively for AcuityMD\n"
        f"- Source URL\n\n"
        f"If there are no significant updates in the past 7 days, say so clearly."
    )

    print(f"  Scanning {competitor['name']}...")

    response = api_call_with_retry(
        lambda: client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": prompt}],
        ),
        label=competitor["name"],
    )

    if response is None:
        return {"name": competitor["name"], "findings": "Skipped — rate limit exceeded after retries."}

    text_parts = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)

    return {
        "name": competitor["name"],
        "findings": "\n".join(text_parts) if text_parts else "No findings returned.",
    }


def synthesize_brief(client, results):
    """Synthesize individual competitor scans into a single brief."""
    today = datetime.now().strftime("%B %d, %Y")

    findings_block = ""
    for r in results:
        findings_block += f"\n## {r['name']}\n{r['findings']}\n"

    prompt = (
        f"You are a competitive intelligence analyst for AcuityMD, a MedTech intelligence "
        f"platform that helps medical device companies commercialize faster.\n\n"
        f"AcuityMD's key differentiators:\n"
        f"- Purpose-built for medtech (not pharma-adapted)\n"
        f"- Procedure-level targeting and physician intelligence\n"
        f"- Speed to value ('3x faster sales process')\n"
        f"- UI that reps actually use\n\n"
        f"Below are raw findings from scanning 5 competitors this week. "
        f"Synthesize them into a concise weekly competitor brief.\n\n"
        f"# Raw Findings\n{findings_block}\n\n"
        f"# Output Format\n"
        f"Write the brief in this exact structure:\n\n"
        f"# AcuityMD Competitor Brief — Week of {today}\n\n"
        f"## Top 3 Things to Know\n"
        f"(Numbered list — the 3 most important competitive developments this week. "
        f"If nothing major happened, say so.)\n\n"
        f"Then for each competitor:\n\n"
        f"## [Competitor Name]\n"
        f"**Changes**: (bullet list of updates, or 'No significant updates this week')\n"
        f"**Competitive Implications**: (what this means for AcuityMD — positioning, "
        f"messaging, feature gaps, sales objections)\n"
        f"**Sources**: (URLs)\n\n"
        f"Keep it sharp and actionable. Write for a PMM at AcuityMD who has 2 minutes to scan this."
    )

    print("  Synthesizing brief...")

    response = api_call_with_retry(
        lambda: client.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        ),
        label="synthesis",
    )

    if response is None:
        return "Error: Could not synthesize brief due to rate limits. Raw findings saved."

    text_parts = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)

    return "\n".join(text_parts)


def generate_html_email(brief):
    """Convert the markdown brief into a styled HTML email."""
    import re

    html = brief

    html = re.sub(r"^# (.+)$", r"<h1 style='color:#1a1a1a;font-size:22px;border-bottom:2px solid #e5e5e5;padding-bottom:8px;'>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2 style='color:#2d2d2d;font-size:18px;margin-top:24px;'>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3 style='color:#444;font-size:15px;'>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" style="color:#6366f1;">\1</a>', html)
    html = re.sub(r"^- (.+)$", r"<li style='margin-bottom:4px;'>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li.*?</li>\n?)+", r"<ul style='padding-left:20px;margin:8px 0;'>\g<0></ul>", html)
    html = re.sub(r"^\d+\. (.+)$", r"<li style='margin-bottom:4px;'>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"\n\n", r"</p><p style='margin:12px 0;line-height:1.6;'>", html)

    body = (
        f"<div style='font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,sans-serif;"
        f"max-width:640px;margin:0 auto;padding:24px;color:#333;'>"
        f"<p style='margin:12px 0;line-height:1.6;'>{html}</p>"
        f"<hr style='border:none;border-top:1px solid #e5e5e5;margin:32px 0 16px;'>"
        f"<p style='font-size:12px;color:#999;'>Generated by acuitymd_competitor_monitor.py</p>"
        f"</div>"
    )

    return body


def send_email(to, subject, html_body):
    """Send email via Gmail SMTP with app password."""
    import smtplib
    import uuid
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formatdate

    gmail_user = os.environ.get("GMAIL_USER", "gagan.bhatia@acuitymd.com")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_pass:
        print("Error: GMAIL_APP_PASSWORD not found in .env or environment")
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["From"] = f"AcuityMD Competitor Monitor <{gmail_user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = f"<{uuid.uuid4()}@acuitymd-competitor-monitor>"
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, [to], msg.as_string())
        print(f"  Email sent via Gmail SMTP!")
    except Exception as e:
        print(f"  Email failed: {e}")
        sys.exit(1)


def save_report(brief, filepath):
    """Save the markdown brief to a local file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(brief)
    print(f"  Report saved: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Weekly AcuityMD competitor monitor — scans 5 MedTech competitors and emails a brief"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and print the report without emailing",
    )
    parser.add_argument(
        "--to",
        default=EMAIL_TO,
        help=f"Email recipient (default: {EMAIL_TO})",
    )
    args = parser.parse_args()

    load_env()

    api_key = os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        print("Error: CLAUDE_API_KEY not found in .env or environment")
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed. Run: .venv/bin/pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Scan competitors
    print("\n🔍 Scanning AcuityMD competitors...")
    results = []
    for competitor in COMPETITORS:
        result = scan_competitor(client, competitor)
        results.append(result)

    # Synthesize brief
    print("\n📝 Synthesizing brief...")
    brief = synthesize_brief(client, results)

    # Save report
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = Path(__file__).parent / "reports" / f"acuitymd-competitor-brief-{today}.md"
    save_report(brief, report_path)

    # Print or email
    if args.dry_run:
        print("\n" + "=" * 60)
        print(brief)
        print("=" * 60)
        print("\n✅ Dry run complete — email not sent.")
    else:
        print("\n📧 Sending email...")
        subject = f"AcuityMD Competitor Brief — Week of {datetime.now().strftime('%B %d, %Y')}"
        html_body = generate_html_email(brief)
        send_email(args.to, subject, html_body)
        print(f"\n✅ Done! Brief emailed to {args.to}")


if __name__ == "__main__":
    main()
