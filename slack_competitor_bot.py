#!/usr/bin/env python3
"""
Slack Competitor Insights Bot

Analyzes Gong calls from the past week to extract competitive intelligence
about MedScout, Definitive Healthcare, and RepSignal from external speakers.

Runs on a weekly schedule, DMs the digest for approval, then posts to #competitors.
"""

import os
import json
import logging
import requests
import uuid
from datetime import datetime, timedelta
from typing import Optional
import openai
from slack_bolt import App
from slack_bolt.adapter.socket_mode.websocket_client import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from market_intel import get_market_intel, MARKET_INTEL_COMPETITORS

# In-memory storage for pending digests (button values have 2000 char limit)
pending_digests = {}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION - Update these values
# =============================================================================

# Gong API credentials
GONG_ACCESS_KEY = os.environ.get("GONG_ACCESS_KEY", "")
GONG_SECRET_KEY = os.environ.get("GONG_SECRET_KEY", "")

# OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Slack credentials
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")  # Bot User OAuth Token
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")  # App-Level Token for Socket Mode

# Slack configuration
APPROVER_USER_IDS = [uid.strip() for uid in os.environ.get("APPROVER_USER_IDS", "U072X3EDC7Q").split(",")]
TARGET_CHANNEL = "#competitors"  # Channel to post approved digests
APPROVAL_CHANNEL = os.environ.get("APPROVAL_CHANNEL", "#competitor-digest")  # Channel for review/approval

# Schedule configuration (default: Monday 9:00 AM)
SCHEDULE_DAY = "mon"
SCHEDULE_HOUR = 9
SCHEDULE_MINUTE = 0

# =============================================================================
# Gong API and AI Analysis (reused from competitor_insights_bot.py)
# =============================================================================

GONG_BASE_URL = "https://api.gong.io/v2"
GONG_COMPETITORS = ["MedScout", "Definitive Healthcare", "RepSignal"]
COMPETITORS = GONG_COMPETITORS  # Keep backward compat for Gong filtering

# Combined display order: all competitors from both Gong and market intel
ALL_COMPETITORS_ORDER = [
    "Veeva Systems",
    "Definitive Healthcare",
    "IQVIA",
    "MedScout",
    "RepSignal",
    "Alpha Sophia",
]


def get_date_range() -> tuple[str, str]:
    """Get ISO format date strings for the previous calendar week (Monday-Sunday)."""
    now = datetime.utcnow()
    # Find the most recent Monday (start of current week)
    days_since_monday = now.weekday()  # Monday = 0
    current_week_monday = now - timedelta(days=days_since_monday)
    # Previous week is 7 days before that
    prev_week_monday = current_week_monday - timedelta(days=7)
    prev_week_sunday = current_week_monday - timedelta(seconds=1)  # End of Sunday
    # Set times to start/end of day
    from_date = prev_week_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    to_date = prev_week_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
    return from_date.isoformat() + "Z", to_date.isoformat() + "Z"


def fetch_calls_from_gong(from_date: str, to_date: str) -> list[dict]:
    """Fetch all calls from Gong within the date range."""
    url = f"{GONG_BASE_URL}/calls/extensive"
    
    all_calls = []
    cursor = None
    
    while True:
        payload = {
            "contentSelector": {
                "exposedFields": {
                    "parties": True,
                    "content": {
                        "trackers": True
                    }
                }
            },
            "filter": {
                "fromDateTime": from_date,
                "toDateTime": to_date
            }
        }
        
        if cursor:
            payload["cursor"] = cursor
        
        response = requests.post(
            url,
            auth=(GONG_ACCESS_KEY, GONG_SECRET_KEY),
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Error fetching calls: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        calls = data.get("calls", [])
        all_calls.extend(calls)
        
        records = data.get("records", {})
        cursor = records.get("cursor")
        if not cursor:
            break
    
    logger.info(f"Fetched {len(all_calls)} calls from the past week")
    return all_calls


def fetch_transcripts(call_ids: list[str]) -> dict[str, list]:
    """Fetch transcripts for given call IDs."""
    if not call_ids:
        return {}
    
    url = f"{GONG_BASE_URL}/calls/transcript"
    transcripts = {}
    
    batch_size = 50
    for i in range(0, len(call_ids), batch_size):
        batch_ids = call_ids[i:i + batch_size]
        
        payload = {
            "filter": {
                "callIds": batch_ids
            }
        }
        
        response = requests.post(
            url,
            auth=(GONG_ACCESS_KEY, GONG_SECRET_KEY),
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Error fetching transcripts: {response.status_code} - {response.text}")
            continue
        
        data = response.json()
        for call_transcript in data.get("callTranscripts", []):
            call_id = call_transcript.get("callId")
            transcript = call_transcript.get("transcript", [])
            transcripts[call_id] = transcript
    
    logger.info(f"Fetched transcripts for {len(transcripts)} calls")
    return transcripts


def build_call_context(calls: list[dict], transcripts: dict[str, list]) -> list[dict]:
    """Build context for each call with party info and transcript segments."""
    call_contexts = []
    
    for call in calls:
        call_id = call.get("metaData", {}).get("id")
        if not call_id or call_id not in transcripts:
            continue
        
        parties = call.get("parties", [])
        speaker_map = {}
        external_speaker_ids = set()
        
        for party in parties:
            speaker_id = party.get("speakerId")
            if speaker_id:
                speaker_map[speaker_id] = {
                    "name": party.get("name", "Unknown"),
                    "email": party.get("emailAddress", ""),
                    "affiliation": party.get("affiliation", "Unknown")
                }
                if party.get("affiliation") == "External":
                    external_speaker_ids.add(speaker_id)
        
        transcript = transcripts[call_id]
        relevant_segments = []
        
        for segment in transcript:
            speaker_id = segment.get("speakerId")
            text = segment.get("sentences", [])
            full_text = " ".join([s.get("text", "") for s in text]) if isinstance(text, list) else str(text)
            
            if speaker_id not in external_speaker_ids:
                continue
            
            text_lower = full_text.lower()
            mentioned_competitors = []
            for comp in COMPETITORS:
                if comp.lower() in text_lower:
                    mentioned_competitors.append(comp)
            
            if mentioned_competitors:
                speaker_info = speaker_map.get(speaker_id, {"name": "Unknown", "affiliation": "External"})
                relevant_segments.append({
                    "speaker": speaker_info["name"],
                    "affiliation": speaker_info["affiliation"],
                    "text": full_text,
                    "competitors_mentioned": mentioned_competitors
                })
        
        if relevant_segments:
            # Clean call_id - Gong sometimes includes title after a pipe character
            clean_call_id = str(call_id).split("|")[0].strip()
            call_contexts.append({
                "call_id": clean_call_id,
                "title": call.get("metaData", {}).get("title", "Untitled Call"),
                "date": call.get("metaData", {}).get("started", ""),
                "segments": relevant_segments
            })
    
    logger.info(f"Found {len(call_contexts)} calls with competitor mentions by external speakers")
    return call_contexts


def analyze_with_ai(call_contexts: list[dict]) -> list[dict]:
    """Use OpenAI to analyze the competitor mentions and extract insights."""
    if not call_contexts:
        return []
    
    context_text = ""
    for ctx in call_contexts:
        context_text += f"\n\n--- Call: {ctx['title']} (Date: {ctx['date']}, Call ID: {ctx['call_id']}) ---\n"
        for seg in ctx["segments"]:
            context_text += f"\n[{seg['speaker']} - External]: \"{seg['text']}\"\n"
            context_text += f"Competitors mentioned: {', '.join(seg['competitors_mentioned'])}\n"
    
    prompt = f"""You are a competitive intelligence analyst for AcuityMD. Analyze the following transcript excerpts from sales calls where external speakers (prospects/customers) mentioned competitors.

Competitors to track: MedScout, Definitive Healthcare, RepSignal

Extract 3-6 insights (only if they genuinely exist - don't force insights). Each insight should:
1. Compare competitor vs AcuityMD (favorably or unfavorably), OR
2. Describe a competitor's feature advantage, strength, weakness, or gap

Insight categories to focus on:
- Pricing
- Functionality  
- Usability/UX
- Support/Service
- Integrations
- Data Quality/Coverage
- Performance/Reliability/Speed

For each insight, provide:
1. Competitor name
2. Category (from the list above)
3. Summary (2-3 sentences summarizing what was said)
4. Direct quote (ONLY if the quote explicitly names the competitor - otherwise omit)
5. Sentiment: Favorable to AcuityMD, Unfavorable to AcuityMD, or Neutral
6. Call title, date, and call_id for reference (call_id is provided in each call header)

IMPORTANT: Only include insights where external speakers genuinely shared competitive intelligence. Don't manufacture insights if the mentions are vague or off-topic.

Transcript excerpts:
{context_text}

Return your analysis as a JSON array of insight objects with keys: competitor, category, summary, quote (optional), sentiment, call_title, call_date, call_id"""

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a competitive intelligence analyst. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    
    try:
        result = json.loads(response.choices[0].message.content)
        insights = result.get("insights", result) if isinstance(result, dict) else result
        if isinstance(insights, list):
            # Clean call_ids - Gong IDs sometimes include title after a pipe character
            for insight in insights:
                if insight.get("call_id"):
                    insight["call_id"] = str(insight["call_id"]).split("|")[0].strip()
            return insights[:6]
        return []
    except json.JSONDecodeError:
        logger.error("Failed to parse AI response as JSON")
        return []


# =============================================================================
# Slack Formatting
# =============================================================================

def format_slack_blocks(insights: list[dict], date_range: tuple[str, str], market_intel: dict = None) -> list[dict]:
    """Format insights as Slack Block Kit blocks, grouped by competitor.

    Combines Gong call insights and market intelligence under each competitor heading.
    """
    from_date = datetime.fromisoformat(date_range[0].replace("Z", "+00:00")).strftime("%B %d, %Y")
    to_date = datetime.fromisoformat(date_range[1].replace("Z", "+00:00")).strftime("%B %d, %Y")

    if market_intel is None:
        market_intel = {}

    # Build competitor lists for the context line
    source_parts = []
    if insights:
        source_parts.append(":headphones: Gong calls")
    if any(market_intel.get(c) for c in MARKET_INTEL_COMPETITORS):
        source_parts.append(":satellite: Market signals")
    sources_label = " + ".join(source_parts) if source_parts else "No data"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Competitor Intelligence Report",
                "emoji": True
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*Period:* {from_date} - {to_date} | *Sources:* {sources_label}"
                }
            ]
        },
        {"type": "divider"}
    ]

    sentiment_emoji = {
        "Favorable to AcuityMD": ":large_green_circle:",
        "Unfavorable to AcuityMD": ":red_circle:",
        "Neutral": ":white_circle:"
    }

    # Group Gong insights by competitor
    grouped_gong = {}
    for insight in insights:
        competitor = insight.get("competitor", "Unknown")
        grouped_gong.setdefault(competitor, []).append(insight)

    # Determine which competitors have any data
    active_competitors = []
    for comp in ALL_COMPETITORS_ORDER:
        has_gong = comp in grouped_gong
        has_market = bool(market_intel.get(comp))
        if has_gong or has_market:
            active_competitors.append(comp)

    # Also include any "Unknown" Gong competitors at the end
    if "Unknown" in grouped_gong:
        active_competitors.append("Unknown")

    if not active_competitors:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No competitor intelligence found this week — no Gong mentions or notable market signals._"
            }
        })
        return blocks

    # Display each competitor section
    for competitor in active_competitors:
        gong_insights = grouped_gong.get(competitor, [])
        intel_bullets = market_intel.get(competitor, [])

        # Competitor header
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{competitor}*"
            }
        })

        # --- Gong call insights ---
        for insight in gong_insights:
            sentiment = insight.get("sentiment", "Neutral")
            emoji = sentiment_emoji.get(sentiment, ":white_circle:")

            insight_text = f"{emoji} _{insight.get('category', 'General')}_\n\n"
            insight_text += f"{insight.get('summary', '')}\n\n"

            if insight.get("quote"):
                insight_text += f"> \"{insight['quote']}\"\n\n"

            call_title = insight.get('call_title', 'Unknown Call')
            call_date = insight.get('call_date', 'Unknown Date')
            call_id = insight.get('call_id')
            if call_id:
                call_id = str(call_id).split("|")[0].strip()

            if call_id:
                gong_url = f"https://app.gong.io/call?id={call_id}"
                insight_text += f"_Source: {call_title} ({call_date})_\n{gong_url}"
            else:
                insight_text += f"_Source: {call_title} ({call_date})_"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": insight_text
                }
            })

        # --- Market intel bullets ---
        for bullet_data in intel_bullets:
            bullet_text = f":satellite: {bullet_data.get('bullet', '')}"
            source_url = bullet_data.get("source_url")
            if source_url:
                bullet_text += f"\n_<{source_url}|Source>_"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": bullet_text
                }
            })

        blocks.append({"type": "divider"})

    # Remove trailing divider if present
    if blocks and blocks[-1].get("type") == "divider":
        blocks.pop()

    return blocks


def format_digest_as_text(insights: list[dict], date_range: tuple[str, str], market_intel: dict = None) -> str:
    """Format insights as editable text for a modal, grouped by competitor. Uses Slack mrkdwn formatting."""
    from_date = datetime.fromisoformat(date_range[0].replace("Z", "+00:00")).strftime("%B %d, %Y")
    to_date = datetime.fromisoformat(date_range[1].replace("Z", "+00:00")).strftime("%B %d, %Y")

    if market_intel is None:
        market_intel = {}

    lines = [
        "*COMPETITOR INTELLIGENCE REPORT*",
        f"_Period: {from_date} - {to_date}_",
        "",
    ]

    sentiment_emoji = {
        "Favorable to AcuityMD": ":large_green_circle:",
        "Unfavorable to AcuityMD": ":red_circle:",
        "Neutral": ":white_circle:"
    }

    # Group Gong insights by competitor
    grouped_gong = {}
    for insight in insights:
        competitor = insight.get("competitor", "Unknown")
        grouped_gong.setdefault(competitor, []).append(insight)

    # Determine which competitors have any data
    active_competitors = []
    for comp in ALL_COMPETITORS_ORDER:
        has_gong = comp in grouped_gong
        has_market = bool(market_intel.get(comp))
        if has_gong or has_market:
            active_competitors.append(comp)
    if "Unknown" in grouped_gong:
        active_competitors.append("Unknown")

    if not active_competitors:
        lines.append("No competitor intelligence found this week.")
        return "\n".join(lines)

    for competitor in active_competitors:
        gong_insights = grouped_gong.get(competitor, [])
        intel_bullets = market_intel.get(competitor, [])

        lines.append("---")
        lines.append(f"*{competitor}*")
        lines.append("")

        # Gong call insights
        for insight in gong_insights:
            sentiment = insight.get("sentiment", "Neutral")
            emoji = sentiment_emoji.get(sentiment, ":white_circle:")

            lines.append(f"{emoji} _{insight.get('category', 'General')}_")
            lines.append(f"Sentiment: {sentiment}")
            lines.append("")
            lines.append(insight.get('summary', ''))

            if insight.get("quote"):
                lines.append("")
                lines.append(f'> "{insight["quote"]}"')

            call_title = insight.get('call_title', 'Unknown Call')
            call_date = insight.get('call_date', 'Unknown Date')
            call_id = insight.get('call_id')
            if call_id:
                call_id = str(call_id).split("|")[0].strip()

            lines.append("")
            if call_id:
                gong_url = f"https://app.gong.io/call?id={call_id}"
                lines.append(f"_Source: {call_title} ({call_date})_")
                lines.append(gong_url)
            else:
                lines.append(f"_Source: {call_title} ({call_date})_")
            lines.append("")

        # Market intel bullets
        for bullet_data in intel_bullets:
            lines.append(f":satellite: {bullet_data.get('bullet', '')}")
            source_url = bullet_data.get("source_url")
            if source_url:
                lines.append(f"_Source: {source_url}_")
            lines.append("")

    return "\n".join(lines)


def format_approval_message(insights: list[dict], date_range: tuple[str, str], market_intel: dict = None) -> tuple[list[dict], str]:
    """Format the DM message with approval buttons. Returns (blocks, digest_id)."""
    if market_intel is None:
        market_intel = {}
    blocks = format_slack_blocks(insights, date_range, market_intel)

    # Store insights with a unique ID (Slack button values have 2000 char limit)
    # Pre-compute the editable text so it's ready instantly when Edit is clicked
    digest_id = str(uuid.uuid4())[:8]
    pending_digests[digest_id] = {
        "insights": insights,
        "date_range": date_range,
        "market_intel": market_intel,
        "editable_text": format_digest_as_text(insights, date_range, market_intel)
    }
    
    # Add approval buttons
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Ready to post this digest to #competitors?*"
        }
    })
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Approve & Post",
                    "emoji": True
                },
                "style": "primary",
                "action_id": "approve_digest",
                "value": digest_id
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Edit",
                    "emoji": True
                },
                "action_id": "edit_digest",
                "value": digest_id
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Dismiss",
                    "emoji": True
                },
                "style": "danger",
                "action_id": "dismiss_digest",
                "value": digest_id
            }
        ]
    })
    
    return blocks, digest_id


# =============================================================================
# Slack Bot Setup
# =============================================================================

# Initialize Slack app
app = App(token=SLACK_BOT_TOKEN)




def generate_and_send_digest():
    """Generate the competitor insights digest and send for approval."""
    logger.info("Starting weekly competitor insights generation...")

    # Get date range
    from_date, to_date = get_date_range()
    logger.info(f"Analyzing calls from {from_date} to {to_date}")

    # Fetch calls from Gong
    calls = fetch_calls_from_gong(from_date, to_date)

    if not calls:
        logger.info("No calls found in the past week")
        insights = []
    else:
        # Extract call IDs and fetch transcripts
        call_ids = [call.get("metaData", {}).get("id") for call in calls if call.get("metaData", {}).get("id")]
        transcripts = fetch_transcripts(call_ids)

        # Build context and analyze
        call_contexts = build_call_context(calls, transcripts)

        if call_contexts:
            insights = analyze_with_ai(call_contexts)
            logger.info(f"Extracted {len(insights)} insights")
        else:
            insights = []

    # Fetch market intelligence (web sources)
    logger.info("Fetching market intelligence...")
    try:
        market_intel = get_market_intel(OPENAI_API_KEY)
    except Exception as e:
        logger.error(f"Market intel collection failed: {e}")
        market_intel = {}

    # Format and send to approval channel
    blocks, digest_id = format_approval_message(insights, (from_date, to_date), market_intel)

    try:
        app.client.chat_postMessage(
            channel=APPROVAL_CHANNEL,
            text="Weekly Competitor Insights Digest - Ready for Review",
            blocks=blocks
        )
        logger.info(f"Sent digest to {APPROVAL_CHANNEL} for review (digest_id: {digest_id})")
    except Exception as e:
        logger.error(f"Error sending to approval channel: {e}")
        # Clean up the pending digest on error
        pending_digests.pop(digest_id, None)


@app.action("approve_digest")
def handle_approve(ack, body, client):
    """Handle the approve button click."""
    ack()
    
    # Look up the insights from our storage
    digest_id = body["actions"][0]["value"]
    data = pending_digests.get(digest_id)
    
    if not data:
        client.chat_postMessage(
            channel=body["channel"]["id"],
            text="Sorry, this digest has expired. Please generate a new one."
        )
        return
    
    try:
        # Check if we have edited text
        if "edited_text" in data:
            # Post edited text - split into multiple sections if needed (Slack has 3000 char limit per block)
            edited_text = data["edited_text"]
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Competitor Insights Report",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "This is our first attempt at an AI-generated competitor digest that peruses last week's gong calls for competitor mentions. Let us know what you think and if you have any suggestions to improve this!"
                    }
                },
                {"type": "divider"}
            ]

            # Split text into chunks if it's too long for a single block
            max_chars = 2900
            if len(edited_text) <= max_chars:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": edited_text
                    }
                })
            else:
                # Split by insight sections (marked by ---)
                sections = edited_text.split("---")
                current_chunk = ""
                
                for section in sections:
                    if len(current_chunk) + len(section) + 4 <= max_chars:
                        if current_chunk:
                            current_chunk += "\n---" + section
                        else:
                            current_chunk = section
                    else:
                        if current_chunk.strip():
                            blocks.append({
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": current_chunk.strip()
                                }
                            })
                        current_chunk = section
                
                if current_chunk.strip():
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": current_chunk.strip()
                        }
                    })
            
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "_This report was automatically generated from Gong call analysis and public market intelligence sources, then edited before posting._"
                    }
                ]
            })
        else:
            # Use original formatted blocks
            insights = data["insights"]
            date_range = tuple(data["date_range"])
            stored_market_intel = data.get("market_intel", {})
            blocks = format_slack_blocks(insights, date_range, stored_market_intel)

            # Add footer
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "_This report was automatically generated from Gong call analysis and public market intelligence sources._"
                    }
                ]
            })
        
        # Post to the target channel
        client.chat_postMessage(
            channel=TARGET_CHANNEL,
            text="Weekly Competitor Insights Report",
            blocks=blocks
        )
        
        # Update the original DM to show it was approved
        client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text="Digest approved and posted!",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: *Digest approved and posted to {TARGET_CHANNEL}!*"
                    }
                }
            ]
        )
        # Clean up the pending digest
        pending_digests.pop(digest_id, None)
        logger.info(f"Digest approved and posted to {TARGET_CHANNEL}")
    except Exception as e:
        logger.error(f"Error posting to channel: {e}")
        client.chat_postMessage(
            channel=body["channel"]["id"],
            text=f"Error posting to {TARGET_CHANNEL}: {str(e)}"
        )


@app.action("dismiss_digest")
def handle_dismiss(ack, body, client):
    """Handle the dismiss button click."""
    ack()
    
    # Clean up the pending digest
    digest_id = body["actions"][0]["value"]
    pending_digests.pop(digest_id, None)
    
    # Update the original DM to show it was dismissed
    client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        text="Digest dismissed",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":x: *Digest dismissed.* No action taken."
                }
            }
        ]
    )
    logger.info("Digest dismissed by user")


@app.action("edit_digest")
def handle_edit(ack, body, client):
    """Handle the edit button click - opens a modal for editing."""
    digest_id = body["actions"][0]["value"]
    trigger_id = body["trigger_id"]
    channel_id = body["channel"]["id"]
    message_ts = body["message"]["ts"]

    # Acknowledge immediately
    ack()

    data = pending_digests.get(digest_id)

    if not data:
        client.chat_postMessage(
            channel=channel_id,
            text="Sorry, this digest has expired. Please generate a new one."
        )
        return

    # Store the message info for later
    data["message_ts"] = message_ts
    data["channel_id"] = channel_id

    # Get the current text (either edited or pre-computed original)
    current_text = data.get("edited_text") or data.get("editable_text", "")

    # Open a modal for editing - must happen within 3 seconds of button click
    try:
        client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": "edit_digest_modal",
                "private_metadata": digest_id,
                "title": {
                    "type": "plain_text",
                    "text": "Edit Digest"
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Save Changes"
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel"
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "digest_content",
                        "label": {
                            "type": "plain_text",
                            "text": "Digest Content"
                        },
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "content_input",
                            "multiline": True,
                            "initial_value": current_text
                        }
                    }
                ]
            }
        )
        logger.info(f"Opened edit modal for digest {digest_id}")
    except Exception as e:
        logger.error(f"Failed to open modal: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text=f"Failed to open edit modal. Please try clicking Edit again."
        )


@app.view("edit_digest_modal")
def handle_edit_submission(ack, body, client, view):
    """Handle the modal submission - store edits and resend digest as a new DM."""
    ack()

    digest_id = view["private_metadata"]
    logger.info(f"Edit modal submitted for digest {digest_id}")
    data = pending_digests.get(digest_id)

    if not data:
        logger.error(f"Digest {digest_id} not found after edit")
        return

    # Get the edited text from the modal
    edited_text = view["state"]["values"]["digest_content"]["content_input"]["value"]

    # Store the edited text
    data["edited_text"] = edited_text

    # Resend the digest as a NEW DM (so Approve/Edit/Dismiss buttons work on a fresh message)
    channel_id = data.get("channel_id")

    if channel_id:
        # Build blocks for the edited digest - split if too long for one block
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Competitor Insights Report (Edited)",
                    "emoji": True
                }
            }
        ]

        max_chars = 2900
        if len(edited_text) <= max_chars:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": edited_text
                }
            })
        else:
            sections = edited_text.split("---")
            current_chunk = ""
            for section in sections:
                if len(current_chunk) + len(section) + 4 <= max_chars:
                    current_chunk = current_chunk + ("---" if current_chunk else "") + section
                else:
                    if current_chunk.strip():
                        blocks.append({
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": current_chunk.strip()}
                        })
                    current_chunk = section
            if current_chunk.strip():
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": current_chunk.strip()}
                })

        blocks.extend([
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Ready to post this edited digest to #competitors?*"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve & Post", "emoji": True},
                        "style": "primary",
                        "action_id": "approve_digest",
                        "value": digest_id
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Edit", "emoji": True},
                        "action_id": "edit_digest",
                        "value": digest_id
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Dismiss", "emoji": True},
                        "style": "danger",
                        "action_id": "dismiss_digest",
                        "value": digest_id
                    }
                ]
            }
        ])

        response = client.chat_postMessage(
            channel=channel_id,
            text="Competitor Insights Report (Edited)",
            blocks=blocks
        )

        # Store the new message's ts so Approve/Dismiss update the correct message
        data["message_ts"] = response["ts"]
        data["channel_id"] = channel_id

        logger.info(f"Resent digest with edits (digest_id: {digest_id})")
    else:
        logger.error(f"No channel_id found for digest {digest_id}")


@app.command("/competitor-insights")
def handle_manual_trigger(ack, command, client):
    """Handle manual trigger via slash command (optional)."""
    ack()
    
    # Only allow the approver to trigger manually
    if command["user_id"] not in APPROVER_USER_IDS:
        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=command["user_id"],
            text="Sorry, only the designated approver can trigger the competitor insights bot."
        )
        return
    
    client.chat_postEphemeral(
        channel=command["channel_id"],
        user=command["user_id"],
        text="Generating competitor insights... You'll receive a DM shortly for review."
    )
    
    # Generate and send digest
    generate_and_send_digest()


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    import sys
    
    logger.info("=" * 60)
    logger.info("Slack Competitor Insights Bot")
    logger.info("=" * 60)
    
    # Set up the scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        generate_and_send_digest,
        CronTrigger(day_of_week=SCHEDULE_DAY, hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        id="weekly_digest",
        name="Weekly Competitor Insights Digest"
    )
    scheduler.start()
    logger.info(f"Scheduled weekly digest for {SCHEDULE_DAY.upper()} at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}")
    
    # Check for --test flag to trigger immediate digest
    if "--test" in sys.argv:
        logger.info("Test mode: Triggering immediate digest...")
        generate_and_send_digest()
    
    # Start the Socket Mode handler
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    logger.info("Starting Slack bot in Socket Mode...")
    logger.info(f"Target channel: {TARGET_CHANNEL}")
    logger.info(f"Approver user IDs: {APPROVER_USER_IDS}")
    
    try:
        handler.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
