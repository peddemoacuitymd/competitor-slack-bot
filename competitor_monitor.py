#!/usr/bin/env python3
"""
Weekly competitor monitor for Claude Code.

Scans 5 competitors (Cursor, GitHub Copilot, Windsurf, Cline, Aider) for
pricing changes, feature launches, and announcements using Claude's web_search
tool, then synthesizes a brief and emails it via Resend.

Usage:
    .venv/bin/python3 competitor_monitor.py              # Full scan + email
    .venv/bin/python3 competitor_monitor.py --dry-run    # Scan + print report, skip email
    .venv/bin/python3 competitor_monitor.py --help       # Usage info

Setup:
    python3 -m venv .venv && .venv/bin/pip install anthropic
    Add CLAUDE_API_KEY and RESEND_API_KEY to .env
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
        "name": "Cursor",
        "description": "AI code editor (fork of VS Code) by Anysphere",
        "domains": "cursor.com, cursor.sh",
    },
    {
        "name": "GitHub Copilot",
        "description": "AI coding assistant by GitHub/Microsoft",
        "domains": "github.com/features/copilot, copilot.github.com",
    },
    {
        "name": "Windsurf",
        "description": "AI code editor by Codeium",
        "domains": "windsurf.com, codeium.com",
    },
    {
        "name": "Cline",
        "description": "Autonomous AI coding agent (VS Code extension)",
        "domains": "cline.bot, github.com/cline/cline",
    },
    {
        "name": "Aider",
        "description": "Open-source AI pair programming CLI tool",
        "domains": "aider.chat, github.com/paul-gauthier/aider",
    },
]

MODEL = "claude-sonnet-4-6"
EMAIL_TO = "gagan.bhatia@acuitymd.com"
EMAIL_FROM = "onboarding@resend.dev"


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
        f"- New feature launches or major updates\n"
        f"- Important announcements, partnerships, or funding\n"
        f"- Notable blog posts or changelog entries\n\n"
        f"Relevant domains: {competitor['domains']}\n\n"
        f"For each finding, include:\n"
        f"- What changed\n"
        f"- Why it matters competitively (especially vs Claude Code)\n"
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

    # Extract text from response (may include tool_use and text blocks)
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
        f"You are a competitive intelligence analyst for Claude Code (Anthropic's AI coding CLI).\n\n"
        f"Below are raw findings from scanning 5 competitors this week. "
        f"Synthesize them into a concise weekly competitor brief.\n\n"
        f"# Raw Findings\n{findings_block}\n\n"
        f"# Output Format\n"
        f"Write the brief in this exact structure:\n\n"
        f"# Competitor Brief — Week of {today}\n\n"
        f"## Top 3 Things to Know\n"
        f"(Numbered list — the 3 most important competitive developments this week. "
        f"If nothing major happened, say so.)\n\n"
        f"Then for each competitor:\n\n"
        f"## [Competitor Name]\n"
        f"**Changes**: (bullet list of updates, or 'No significant updates this week')\n"
        f"**Competitive Implications**: (what this means for Claude Code — positioning, "
        f"messaging, feature gaps)\n"
        f"**Sources**: (URLs)\n\n"
        f"Keep it sharp and actionable. Write for a PMM who has 2 minutes to scan this."
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

    # Simple markdown-to-HTML conversion
    html = brief

    # Headers
    html = re.sub(r"^# (.+)$", r"<h1 style='color:#1a1a1a;font-size:22px;border-bottom:2px solid #e5e5e5;padding-bottom:8px;'>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2 style='color:#2d2d2d;font-size:18px;margin-top:24px;'>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3 style='color:#444;font-size:15px;'>\1</h3>", html, flags=re.MULTILINE)

    # Bold
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)

    # Links
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" style="color:#6366f1;">\1</a>', html)

    # Bullet lists
    html = re.sub(r"^- (.+)$", r"<li style='margin-bottom:4px;'>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li.*?</li>\n?)+", r"<ul style='padding-left:20px;margin:8px 0;'>\g<0></ul>", html)

    # Numbered lists
    html = re.sub(r"^\d+\. (.+)$", r"<li style='margin-bottom:4px;'>\1</li>", html, flags=re.MULTILINE)

    # Paragraphs (blank lines)
    html = re.sub(r"\n\n", r"</p><p style='margin:12px 0;line-height:1.6;'>", html)

    body = (
        f"<div style='font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,sans-serif;"
        f"max-width:640px;margin:0 auto;padding:24px;color:#333;'>"
        f"<p style='margin:12px 0;line-height:1.6;'>{html}</p>"
        f"<hr style='border:none;border-top:1px solid #e5e5e5;margin:32px 0 16px;'>"
        f"<p style='font-size:12px;color:#999;'>Generated by competitor_monitor.py</p>"
        f"</div>"
    )

    return body


def lookup_mx(domain):
    """Look up MX records for a domain using dig."""
    import subprocess

    result = subprocess.run(
        ["dig", "+short", "MX", domain],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None

    # Parse "5 mail.example.com." lines, pick lowest priority
    records = []
    for line in result.stdout.strip().splitlines():
        parts = line.strip().split()
        if len(parts) == 2:
            priority, host = int(parts[0]), parts[1].rstrip(".")
            records.append((priority, host))

    if not records:
        return None

    records.sort()
    return records[0][1]


def send_email_smtp(to, subject, html_body, sender=None):
    """Send email directly via SMTP using MX lookup."""
    import smtplib
    import uuid
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formatdate

    if sender is None:
        sender = f"competitor-monitor@{os.uname().nodename or 'localhost'}"

    domain = to.split("@")[1]
    mx_host = lookup_mx(domain)
    if not mx_host:
        print(f"  Error: Could not resolve MX for {domain}")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"Competitor Monitor <{sender}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = f"<{uuid.uuid4()}@competitor-monitor>"
    msg.attach(MIMEText(html_body, "html"))

    try:
        import socket

        # Resolve MX to IPv4 to avoid IPv6 PTR issues
        ipv4_addr = socket.getaddrinfo(mx_host, 25, socket.AF_INET)[0][4][0]

        with smtplib.SMTP(ipv4_addr, 25, timeout=30) as smtp:
            smtp.ehlo()
            # Try STARTTLS if available
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPNotSupportedError:
                pass
            smtp.sendmail(sender, [to], msg.as_string())
        print(f"  Email sent via {mx_host} ({ipv4_addr})!")
        return True
    except Exception as e:
        print(f"  SMTP delivery failed ({mx_host}): {e}")
        return False


def send_email_resend(to, subject, html_body):
    """Send email via Resend API."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return False

    payload = json.dumps({
        "from": EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html_body,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"  Email sent via Resend! ID: {result.get('id', 'unknown')}")
            return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"  Resend failed ({e.code}): {error_body}")
        return False


def send_email_gmail(to, subject, html_body):
    """Send email via Gmail SMTP with app password."""
    import smtplib
    import uuid
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formatdate

    gmail_user = os.environ.get("GMAIL_USER", "gagan.bhatia@acuitymd.com")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_pass:
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"Competitor Monitor <{gmail_user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = f"<{uuid.uuid4()}@competitor-monitor>"
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, [to], msg.as_string())
        print(f"  Email sent via Gmail SMTP!")
        return True
    except Exception as e:
        print(f"  Gmail SMTP failed: {e}")
        return False


def send_email(to, subject, html_body):
    """Send email — tries Gmail SMTP, then Resend API."""
    print(f"  Trying Gmail SMTP...")
    if send_email_gmail(to, subject, html_body):
        return

    print(f"  Falling back to Resend API...")
    if send_email_resend(to, subject, html_body):
        return

    print("  Error: All email delivery methods failed.")
    sys.exit(1)


def save_report(brief, filepath):
    """Save the markdown brief to a local file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(brief)
    print(f"  Report saved: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Weekly competitor monitor — scans 5 AI coding competitors and emails a brief"
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

    # Load env and validate keys
    load_env()

    api_key = os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        print("Error: CLAUDE_API_KEY not found in .env or environment")
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Scan competitors
    print("\n🔍 Scanning competitors...")
    results = []
    for competitor in COMPETITORS:
        result = scan_competitor(client, competitor)
        results.append(result)

    # Synthesize brief
    print("\n📝 Synthesizing brief...")
    brief = synthesize_brief(client, results)

    # Save report
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = Path(__file__).parent / "reports" / f"competitor-brief-{today}.md"
    save_report(brief, report_path)

    # Print or email
    if args.dry_run:
        print("\n" + "=" * 60)
        print(brief)
        print("=" * 60)
        print("\n✅ Dry run complete — email not sent.")
    else:
        print("\n📧 Sending email...")
        subject = f"Competitor Brief — Week of {datetime.now().strftime('%B %d, %Y')}"
        html_body = generate_html_email(brief)
        send_email(args.to, subject, html_body)
        print(f"\n✅ Done! Brief emailed to {args.to}")


if __name__ == "__main__":
    main()
