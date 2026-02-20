#!/usr/bin/env python3
"""Quick test to trigger the competitor insights digest."""

from slack_competitor_bot import generate_and_send_digest

if __name__ == "__main__":
    print("Triggering competitor insights digest...")
    generate_and_send_digest()
    print("Done! Check your Slack DMs.")
