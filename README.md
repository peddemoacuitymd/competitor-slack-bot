# Competitor Slack Bot

Slack bot that pulls competitor mentions from Gong calls, scrapes public market intelligence, and posts weekly digests to a Slack channel for approval.

## Setup

1. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Create a `.env` file with your credentials:

```
OPENAI_API_KEY=your-openai-key
GONG_ACCESS_KEY=your-gong-access-key
GONG_SECRET_KEY=your-gong-secret-key
RESEND_API_KEY=your-resend-key
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
APPROVER_USER_IDS=U072X3EDC7Q,U0XXXXXXXX
```

`APPROVER_USER_IDS` is a comma-separated list of Slack user IDs that can approve/edit digests and trigger the `/competitor-insights` command. To find a user's ID, click their profile in Slack and select **Copy member ID**.

## Running the Bot

```bash
# Start the bot (runs in background, logs to bot.log)
./run_bot.sh

# Start the bot and send a digest immediately
./run_bot.sh --test

# View logs
tail -f bot.log
```
