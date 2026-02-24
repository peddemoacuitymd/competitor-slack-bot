#!/usr/bin/env python3
"""
Market Intelligence Module

Uses OpenAI Responses API with web_search to find recent competitor updates
(pricing, features, announcements) and synthesize actionable intelligence.

Tracks: Veeva Systems, Definitive Healthcare, Alpha Sophia, IQVIA, MedScout, RepSignal
Outputs: Max 3 bullets per competitor with source URLs.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta

import openai

logger = logging.getLogger(__name__)

MARKET_INTEL_COMPETITORS = [
    "Veeva Systems",
    "Definitive Healthcare",
    "Alpha Sophia",
    "IQVIA",
    "MedScout",
    "RepSignal",
]

# Context for each competitor to guide web search
COMPETITOR_CONTEXT = {
    "Veeva Systems": {
        "description": "Enterprise cloud platform for life sciences — CRM, content, quality, regulatory. Customers include Medtronic, BD, Philips.",
        "domains": "veeva.com",
        "context": "AcuityMD competes on being purpose-built for medtech sales vs Veeva's pharma-first approach.",
    },
    "Definitive Healthcare": {
        "description": "Broad healthcare data and analytics platform — hospital profiles, physician data, claims records. 9,000+ hospital profiles, 3M+ HCPs.",
        "domains": "definitivehc.com",
        "context": "AcuityMD competes on medtech-specific workflows vs Definitive's horizontal data platform.",
    },
    "Alpha Sophia": {
        "description": "Affordable MedTech commercial intelligence platform targeting startups and SMBs. Claims ~80% of US medical claims data.",
        "domains": "alphasophia.com",
        "context": "Alpha Sophia positions as the cheaper alternative to AcuityMD for smaller teams.",
    },
    "IQVIA": {
        "description": "Global healthcare data and technology company — largest healthcare dataset, OCE CRM, real-world evidence, consulting.",
        "domains": "iqvia.com",
        "context": "IQVIA is primarily pharma-oriented with medtech as a secondary vertical.",
    },
    "MedScout": {
        "description": "Revenue acceleration platform for medtech — 310M+ patients, 34B+ claims translated into actionable sales insights. Founded 2020, Austin TX. $20.8M raised.",
        "domains": "medscout.io, medscout.cloud",
        "context": "MedScout is a direct competitor with very similar positioning — claims-based physician targeting for medtech sales reps.",
    },
    "RepSignal": {
        "description": "AI-powered commercial intelligence for medical device companies by S2N Health — 1.2M physicians, 50K+ facilities. Natively built on Salesforce.",
        "domains": "s2nhealth.com, repsignal.com",
        "context": "RepSignal competes on Salesforce-native integration — appeals to teams already on SFDC.",
    },
}


def _api_call_with_retry(fn, label="API call"):
    """Call fn() with retry + backoff on rate limits."""
    for attempt in range(5):
        try:
            return fn()
        except (openai.RateLimitError, openai.APIStatusError) as e:
            if hasattr(e, 'status_code') and e.status_code != 429:
                raise
            wait = 30 * (attempt + 1)
            logger.info(f"Rate limited on {label}, waiting {wait}s...")
            time.sleep(wait)
    logger.error(f"Failed {label} after retries.")
    return None


def _scan_competitor(client, name: str, info: dict) -> dict:
    """Use OpenAI Responses API with web_search to find recent updates."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    prompt = (
        f"Search for any recent news, updates, or changes about {name} "
        f"({info['description']}) from the past 7 days ({week_ago} to {today}).\n\n"
        f"Look specifically for:\n"
        f"- Pricing changes or new plan tiers\n"
        f"- New product features or platform updates\n"
        f"- Major announcements, partnerships, acquisitions, or funding\n"
        f"- Earnings reports or significant business updates\n"
        f"- Notable blog posts, press releases, or industry event appearances\n\n"
        f"Relevant domains: {info['domains']}\n\n"
        f"Competitive context: {info['context']}\n\n"
        f"For each finding, provide:\n"
        f"- A **bold lead-in phrase** followed by 1-2 sentences of context\n"
        f"- Why it matters competitively for AcuityMD\n"
        f"- The source URL\n\n"
        f"Return UP TO 3 findings as a JSON array:\n"
        f'[{{"bullet": "**Bold lead-in.** Context and competitive implication.", "source_url": "https://..."}}]\n\n'
        f"If there are no significant updates in the past 7 days, return an empty array: []\n"
        f"Return ONLY valid JSON, no other text."
    )

    logger.info(f"Scanning {name} via web search...")

    response = _api_call_with_retry(
        lambda: client.responses.create(
            model="gpt-4o",
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        ),
        label=name,
    )

    if response is None:
        return {"name": name, "bullets": []}

    # Extract text from response
    raw_text = response.output_text.strip()

    # Parse JSON from response
    try:
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if json_match:
            bullets = json.loads(json_match.group())
            if isinstance(bullets, list):
                return {"name": name, "bullets": bullets[:3]}
        return {"name": name, "bullets": []}
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to parse JSON for {name}: {e}")
        if raw_text and "no significant" not in raw_text.lower():
            return {"name": name, "bullets": [{"bullet": raw_text[:500], "source_url": ""}]}
        return {"name": name, "bullets": []}


def get_market_intel(openai_api_key: str = None) -> dict[str, list[dict]]:
    """Main entry point: scan competitors via OpenAI web_search.

    Uses the same OpenAI API key already configured for the bot.

    Returns: {competitor_name: [{"bullet": "...", "source_url": "..."}]}
    """
    api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found. Skipping market intel.")
        return {comp: [] for comp in MARKET_INTEL_COMPETITORS}

    client = openai.OpenAI(api_key=api_key)

    logger.info("Starting market intelligence collection via OpenAI web_search...")
    intel = {}

    for name in MARKET_INTEL_COMPETITORS:
        info = COMPETITOR_CONTEXT[name]
        result = _scan_competitor(client, name, info)
        intel[name] = result["bullets"]
        logger.info(f"  {name}: {len(result['bullets'])} bullets")

    total_bullets = sum(len(b) for b in intel.values())
    active = len([c for c, b in intel.items() if b])
    logger.info(f"Market intel complete: {total_bullets} bullets across {active} competitors")

    return intel
