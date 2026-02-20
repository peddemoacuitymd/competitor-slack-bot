#!/usr/bin/env python3
"""
Competitor Insights Bot

Analyzes Gong calls from the past week to extract competitive intelligence
about MedScout, Definitive Healthcare, and RepSignal from external speakers.
Emails a summary report with 3-6 insights.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional
import openai
import resend

# Configuration
GONG_ACCESS_KEY = os.environ.get("GONG_ACCESS_KEY", "")
GONG_SECRET_KEY = os.environ.get("GONG_SECRET_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RECIPIENT_EMAIL = "ljpeddemo@gmail.com"

GONG_BASE_URL = "https://api.gong.io/v2"
COMPETITORS = ["MedScout", "Definitive Healthcare", "RepSignal"]

# Initialize clients
openai.api_key = OPENAI_API_KEY
resend.api_key = RESEND_API_KEY


def get_date_range() -> tuple[str, str]:
    """Get ISO format date strings for the past week."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    return week_ago.isoformat() + "Z", now.isoformat() + "Z"


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
            print(f"Error fetching calls: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        calls = data.get("calls", [])
        all_calls.extend(calls)
        
        # Check for pagination
        records = data.get("records", {})
        cursor = records.get("cursor")
        if not cursor:
            break
    
    print(f"Fetched {len(all_calls)} calls from the past week")
    return all_calls


def fetch_transcripts(call_ids: list[str]) -> dict[str, list]:
    """Fetch transcripts for given call IDs."""
    if not call_ids:
        return {}
    
    url = f"{GONG_BASE_URL}/calls/transcript"
    transcripts = {}
    
    # Gong API allows batching, but let's chunk to avoid issues
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
            print(f"Error fetching transcripts: {response.status_code} - {response.text}")
            continue
        
        data = response.json()
        for call_transcript in data.get("callTranscripts", []):
            call_id = call_transcript.get("callId")
            transcript = call_transcript.get("transcript", [])
            transcripts[call_id] = transcript
    
    print(f"Fetched transcripts for {len(transcripts)} calls")
    return transcripts


def build_call_context(calls: list[dict], transcripts: dict[str, list]) -> list[dict]:
    """
    Build context for each call with party info and transcript segments.
    Filter for calls that have external speaker mentions of competitors.
    """
    call_contexts = []
    
    for call in calls:
        call_id = call.get("metaData", {}).get("id")
        if not call_id or call_id not in transcripts:
            continue
        
        # Get party information (mapping speaker ID to details)
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
        
        # Check transcript for competitor mentions by external speakers
        transcript = transcripts[call_id]
        relevant_segments = []
        
        for segment in transcript:
            speaker_id = segment.get("speakerId")
            text = segment.get("sentences", [])
            full_text = " ".join([s.get("text", "") for s in text]) if isinstance(text, list) else str(text)
            
            # Check if this is an external speaker
            if speaker_id not in external_speaker_ids:
                continue
            
            # Check if any competitor is mentioned
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
            call_contexts.append({
                "call_id": call_id,
                "title": call.get("metaData", {}).get("title", "Untitled Call"),
                "date": call.get("metaData", {}).get("started", ""),
                "segments": relevant_segments
            })
    
    print(f"Found {len(call_contexts)} calls with competitor mentions by external speakers")
    return call_contexts


def analyze_with_ai(call_contexts: list[dict]) -> list[dict]:
    """Use OpenAI to analyze the competitor mentions and extract insights."""
    if not call_contexts:
        return []
    
    # Prepare the context for the AI
    context_text = ""
    for ctx in call_contexts:
        context_text += f"\n\n--- Call: {ctx['title']} (Date: {ctx['date']}) ---\n"
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
6. Call title and date for reference

IMPORTANT: Only include insights where external speakers genuinely shared competitive intelligence. Don't manufacture insights if the mentions are vague or off-topic.

Transcript excerpts:
{context_text}

Return your analysis as a JSON array of insight objects with keys: competitor, category, summary, quote (optional), sentiment, call_title, call_date"""

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
            return insights[:6]  # Cap at 6 insights
        return []
    except json.JSONDecodeError:
        print("Failed to parse AI response as JSON")
        return []


def format_email_html(insights: list[dict], date_range: tuple[str, str]) -> str:
    """Format insights as an HTML email."""
    from_date = datetime.fromisoformat(date_range[0].replace("Z", "+00:00")).strftime("%B %d, %Y")
    to_date = datetime.fromisoformat(date_range[1].replace("Z", "+00:00")).strftime("%B %d, %Y")
    
    if not insights:
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2c3e50;">Competitor Insights Report</h1>
            <p style="color: #7f8c8d;">Period: {from_date} - {to_date}</p>
            <p>No competitor mentions by external speakers were found in the past week's Gong calls.</p>
        </body>
        </html>
        """
    
    sentiment_colors = {
        "Favorable to AcuityMD": "#27ae60",
        "Unfavorable to AcuityMD": "#e74c3c",
        "Neutral": "#95a5a6"
    }
    
    insights_html = ""
    for i, insight in enumerate(insights, 1):
        sentiment = insight.get("sentiment", "Neutral")
        color = sentiment_colors.get(sentiment, "#95a5a6")
        
        quote_html = ""
        if insight.get("quote"):
            quote_html = f"""
            <blockquote style="border-left: 3px solid #bdc3c7; padding-left: 15px; margin: 10px 0; color: #555; font-style: italic;">
                "{insight['quote']}"
            </blockquote>
            """
        
        insights_html += f"""
        <div style="background: #f9f9f9; border-radius: 8px; padding: 20px; margin-bottom: 20px; border-left: 4px solid {color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="background: #3498db; color: white; padding: 4px 12px; border-radius: 4px; font-size: 12px;">
                    {insight.get('competitor', 'Unknown')}
                </span>
                <span style="background: #ecf0f1; padding: 4px 12px; border-radius: 4px; font-size: 12px;">
                    {insight.get('category', 'General')}
                </span>
                <span style="background: {color}; color: white; padding: 4px 12px; border-radius: 4px; font-size: 12px;">
                    {sentiment}
                </span>
            </div>
            <p style="margin: 10px 0; color: #2c3e50; line-height: 1.6;">
                {insight.get('summary', '')}
            </p>
            {quote_html}
            <p style="font-size: 12px; color: #7f8c8d; margin-top: 10px;">
                Source: {insight.get('call_title', 'Unknown Call')} ({insight.get('call_date', 'Unknown Date')})
            </p>
        </div>
        """
    
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #fff;">
        <h1 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
            Competitor Insights Report
        </h1>
        <p style="color: #7f8c8d; margin-bottom: 30px;">
            Period: {from_date} - {to_date} | Competitors tracked: MedScout, Definitive Healthcare, RepSignal
        </p>
        
        <h2 style="color: #34495e;">Key Insights ({len(insights)} found)</h2>
        
        {insights_html}
        
        <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;">
        <p style="font-size: 12px; color: #95a5a6; text-align: center;">
            This report was automatically generated by the Competitor Insights Bot.<br>
            Insights are extracted from external speaker mentions in Gong calls.
        </p>
    </body>
    </html>
    """


def send_email(html_content: str, recipient: str, date_range: tuple[str, str]) -> bool:
    """Send the email report via Resend."""
    from_date = datetime.fromisoformat(date_range[0].replace("Z", "+00:00")).strftime("%b %d")
    to_date = datetime.fromisoformat(date_range[1].replace("Z", "+00:00")).strftime("%b %d, %Y")
    
    try:
        params = {
            "from": "Competitor Insights Bot <onboarding@resend.dev>",
            "to": [recipient],
            "subject": f"Weekly Competitor Insights Report ({from_date} - {to_date})",
            "html": html_content
        }
        
        response = resend.Emails.send(params)
        print(f"Email sent successfully! ID: {response.get('id', 'unknown')}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def main():
    print("=" * 60)
    print("Competitor Insights Bot")
    print("=" * 60)
    
    # Get date range for past week
    from_date, to_date = get_date_range()
    print(f"\nAnalyzing calls from {from_date} to {to_date}")
    
    # Fetch calls from Gong
    print("\n1. Fetching calls from Gong...")
    calls = fetch_calls_from_gong(from_date, to_date)
    
    if not calls:
        print("No calls found in the past week.")
        # Still send an email indicating no calls
        html = format_email_html([], (from_date, to_date))
        send_email(html, RECIPIENT_EMAIL, (from_date, to_date))
        return
    
    # Extract call IDs
    call_ids = [call.get("metaData", {}).get("id") for call in calls if call.get("metaData", {}).get("id")]
    
    # Fetch transcripts
    print("\n2. Fetching transcripts...")
    transcripts = fetch_transcripts(call_ids)
    
    # Build context with external speaker competitor mentions
    print("\n3. Analyzing competitor mentions by external speakers...")
    call_contexts = build_call_context(calls, transcripts)
    
    if not call_contexts:
        print("No competitor mentions by external speakers found.")
        html = format_email_html([], (from_date, to_date))
        send_email(html, RECIPIENT_EMAIL, (from_date, to_date))
        return
    
    # Analyze with AI
    print("\n4. Extracting insights with AI...")
    insights = analyze_with_ai(call_contexts)
    print(f"Extracted {len(insights)} insights")
    
    # Format and send email
    print("\n5. Sending email report...")
    html = format_email_html(insights, (from_date, to_date))
    send_email(html, RECIPIENT_EMAIL, (from_date, to_date))
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
