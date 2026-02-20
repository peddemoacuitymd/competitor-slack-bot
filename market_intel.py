#!/usr/bin/env python3
"""
Market Intelligence Module

Scrapes public web sources (IR pages, press releases, financial data, competitor blogs)
to generate competitive market intelligence for AcuityMD.

Tracks: Veeva Systems, Definitive Healthcare, Alpha Sophia, IQVIA
Outputs: Max 3 bullets per competitor with source URLs.
"""

from __future__ import annotations

import re
import json
import logging
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import openai

logger = logging.getLogger(__name__)

MARKET_INTEL_COMPETITORS = ["Veeva Systems", "Definitive Healthcare", "Alpha Sophia", "IQVIA"]

COMPETITOR_SOURCES = {
    "Veeva Systems": [
        {"name": "Veeva Newsroom", "url": "https://www.veeva.com/resources/newsroom/"},
        {"name": "Finviz - VEEV", "url": "https://finviz.com/quote.ashx?t=VEEV"},
    ],
    "Definitive Healthcare": [
        {"name": "DH Investor Relations", "url": "https://ir.definitivehc.com/news-and-events/news-releases"},
        {"name": "DH Blog", "url": "https://www.definitivehc.com/blog"},
        {"name": "Finviz - DH", "url": "https://finviz.com/quote.ashx?t=DH"},
    ],
    "Alpha Sophia": [
        {"name": "Alpha Sophia Blog", "url": "https://www.alphasophia.com/blog"},
    ],
    "IQVIA": [
        {"name": "IQVIA Newsroom", "url": "https://www.iqvia.com/newsroom"},
        {"name": "Finviz - IQV", "url": "https://finviz.com/quote.ashx?t=IQV"},
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_page(url: str, timeout: int = 15) -> str | None:
    """Fetch a web page with error handling."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def extract_page_content(html: str, max_chars: int = 6000) -> str:
    """Extract clean text content from HTML, preserving basic structure."""
    soup = BeautifulSoup(html, "lxml")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


def fetch_competitor_updates() -> dict[str, list[dict]]:
    """Fetch raw content from all competitor sources.

    Returns: {competitor_name: [{"source_name": ..., "source_url": ..., "content": ...}]}
    """
    all_updates = {}

    for competitor, sources in COMPETITOR_SOURCES.items():
        updates = []
        for source in sources:
            logger.info(f"Fetching {source['name']} for {competitor}...")
            html = fetch_page(source["url"])
            if not html:
                continue

            content = extract_page_content(html)
            if content and len(content.strip()) > 100:
                updates.append({
                    "source_name": source["name"],
                    "source_url": source["url"],
                    "content": content,
                })

        all_updates[competitor] = updates
        logger.info(f"Collected {len(updates)} sources for {competitor}")

    return all_updates


def synthesize_intel(raw_updates: dict[str, list[dict]], openai_api_key: str) -> dict[str, list[dict]]:
    """Use GPT-4O to synthesize raw web content into max 3 bullets per competitor.

    Returns: {competitor_name: [{"bullet": "...", "source_url": "..."}]}
    """
    context_parts = []
    for competitor, updates in raw_updates.items():
        if not updates:
            context_parts.append(f"\n=== {competitor} ===\nNo data collected this week.\n")
            continue

        context_parts.append(f"\n=== {competitor} ===")
        for update in updates:
            context_parts.append(f"\n--- Source: {update['source_name']} ({update['source_url']}) ---")
            context_parts.append(update["content"])

    context_text = "\n".join(context_parts)

    today = datetime.utcnow()
    week_ago = today - timedelta(days=7)

    prompt = f"""You are a competitive intelligence analyst for AcuityMD, a medtech commercial intelligence platform.

Analyze the following scraped web content from competitor sources. For each competitor, produce UP TO 3 concise bullets summarizing the most important recent developments and their competitive implications for AcuityMD.

Competitors: Veeva Systems, Definitive Healthcare, Alpha Sophia, IQVIA

Today's date: {today.strftime('%B %d, %Y')}
Focus window: Past 7 days ({week_ago.strftime('%B %d')} - {today.strftime('%B %d, %Y')})

Guidelines:
- Each bullet should have a **bold lead-in phrase** followed by 1-2 sentences of context/implication
- Focus on: product announcements, earnings/financial signals, partnerships, strategic moves, content shifts, and anything that affects AcuityMD's competitive position
- If a competitor has no meaningful recent news, return an empty array for them — don't force bullets
- Prioritize actionable intelligence over general observations
- Include the source URL for each bullet (use the source URL provided, not a fabricated one)
- Maximum 3 bullets per competitor, fewer is fine

Scraped content:
{context_text}

Return your analysis as a JSON object with this structure:
{{
  "Veeva Systems": [{{"bullet": "**Bold lead-in.** Context sentence.", "source_url": "https://..."}}],
  "Definitive Healthcare": [...],
  "Alpha Sophia": [...],
  "IQVIA": [...]
}}

Only return valid JSON. If no meaningful intelligence exists for a competitor, use an empty array."""

    client = openai.OpenAI(api_key=openai_api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a competitive intelligence analyst. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # Validate and cap at 3 bullets per competitor
        validated = {}
        for competitor in MARKET_INTEL_COMPETITORS:
            bullets = result.get(competitor, [])
            if isinstance(bullets, list):
                validated[competitor] = bullets[:3]
            else:
                validated[competitor] = []

        return validated

    except Exception as e:
        logger.error(f"Failed to synthesize market intel: {e}")
        return {comp: [] for comp in MARKET_INTEL_COMPETITORS}


def get_market_intel(openai_api_key: str) -> dict[str, list[dict]]:
    """Main entry point: fetch and synthesize market intelligence.

    Returns: {competitor_name: [{"bullet": "...", "source_url": "..."}]}
    """
    logger.info("Starting market intelligence collection...")
    raw_updates = fetch_competitor_updates()

    total_sources = sum(len(updates) for updates in raw_updates.values())
    if total_sources == 0:
        logger.warning("No web sources could be fetched. Skipping market intel synthesis.")
        return {comp: [] for comp in MARKET_INTEL_COMPETITORS}

    logger.info(f"Collected content from {total_sources} sources. Synthesizing...")
    intel = synthesize_intel(raw_updates, openai_api_key)

    total_bullets = sum(len(bullets) for bullets in intel.values())
    logger.info(f"Market intel complete: {total_bullets} bullets across {len([c for c, b in intel.items() if b])} competitors")

    return intel
