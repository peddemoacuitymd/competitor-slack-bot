# PRD: Claude Code ROI Calculator

## Overview

A simple, interactive calculator embedded on the Claude Code landing page that shows PMs and PMMs how many hours per week they'd reclaim by using Claude Code. The goal is to make the value concrete and personal — not abstract.

This calculator is designed for the buyer described in `persona.md`: a PMM at a Series B SaaS company who is skeptical that a coding tool is relevant to her role. The calculator should feel like a mirror of her actual week, not a generic productivity pitch.

## Problem

Our target PMM doesn't believe Claude Code is for her. Telling her "it saves time" isn't enough. She needs to see her own workflow reflected back, with specific hours attached. The persona research (see `persona.md`) confirms that what changes her mind is a **clear before/after** — "This used to take a sprint, now it takes 30 minutes." An ROI calculator gives her that moment without asking her to install anything.

## Goals

1. **Convert skeptics** — Give the "I'm not a developer" PMM a reason to care by quantifying time saved on tasks she already does
2. **Create an aha moment** — The output should feel surprising ("I'd get back 8 hours a week?!")
3. **Drive to action** — The result should feed directly into a CTA to try Claude Code
4. **Be shareable** — A PMM should be able to screenshot or share her result with her manager to justify trying the tool

## Non-goals

- This is not a detailed TCO calculator or enterprise pricing tool
- No account creation, email capture, or gating
- No backend — everything runs client-side

## User flow

1. User lands on the calculator section (or standalone page)
2. User sees 5 pre-labeled sliders, each representing a weekly task
3. User adjusts sliders to match their typical week
4. Results update in real time — no "Calculate" button
5. User sees total hours saved per week, per month, and per year
6. A contextual CTA appears below the result

## Inputs

Five sliders, each mapped to a task from the persona's actual week. Default values reflect a realistic PMM workload.

| # | Input label | Description | Range | Default | Unit |
|---|---|---|---|---|---|
| 1 | Competitor research & battlecards | Tracking competitor pricing, features, and positioning; updating battlecards and win/loss docs | 0–10 | 4 | hrs/week |
| 2 | Landing pages & web content | Creating, updating, or waiting on launch pages, campaign microsites, and comparison pages | 0–10 | 3 | hrs/week |
| 3 | Data formatting & reporting | Pulling pipeline data, formatting charts for QBRs, and assembling board deck slides | 0–10 | 3 | hrs/week |
| 4 | Prototypes & demos | Building product demos, interactive walkthroughs, or clickable mockups for sales or the board | 0–10 | 2 | hrs/week |
| 5 | Writing PRDs & briefs | Drafting product requirements, launch briefs, messaging frameworks, or positioning docs | 0–8 | 3 | hrs/week |

### Why these five

Each input maps directly to a frustration or priority from `persona.md`:

- **Competitor research** → her competitive intelligence responsibility and the pain of manually scraping pricing pages
- **Landing pages** → her content velocity pressure and the pain of filing Jira tickets for one-line changes
- **Data formatting** → her pipeline contribution KPI and the pain of hours spent on QBR prep
- **Prototypes** → her desire for interactive demos vs. static slide decks
- **PRDs & briefs** → a universal PM/PMM time sink that Claude Code accelerates significantly

## Calculation logic

Each task category has an estimated **time reduction percentage** representing how much faster the task becomes with Claude Code. These are conservative estimates.

| Category | Time reduction | Rationale |
|---|---|---|
| Competitor research & battlecards | 60% | Claude Code can write scripts to pull and format competitor data automatically; refreshing takes minutes instead of hours |
| Landing pages & web content | 75% | A PMM can describe a page in plain English and have it built in minutes; eliminates the Jira-and-wait cycle entirely |
| Data formatting & reporting | 50% | Claude Code can write data transformation scripts, but the PMM still needs to interpret and present the data |
| Prototypes & demos | 70% | Interactive prototypes that would require a designer + engineer can be described and built in a single session |
| PRDs & briefs | 40% | Claude Code can generate structured drafts and fill in technical details, but the PMM still drives strategy and positioning |

**Formulas:**

```
hours_saved_per_category = input_hours × reduction_percentage
total_hours_saved_weekly = sum of all categories
total_hours_saved_monthly = weekly × 4.3
total_hours_saved_yearly = weekly × 50
```

## Output display

The results section should update live as the user moves sliders.

### Primary metric

**"You'd get back X hours every week."**

Large, bold, prominent. This is the number that creates the aha moment.

### Supporting metrics

- **X hours/month** — makes the weekly number feel more substantial
- **X hours/year** — the "whoa" number
- **"That's X full work weeks per year"** — divide yearly hours by 40 for emotional impact

### Breakdown

A small stacked bar or simple list showing hours saved per category, so the user can see where the biggest gains come from.

### Contextual CTA

Below the result, show a message that adapts to the output:

- If total weekly savings < 3 hours: "Even a few hours back means one more launch page or battlecard per week."
- If total weekly savings 3–6 hours: "That's almost a full day. Imagine what you'd ship with that time back."
- If total weekly savings > 6 hours: "That's like adding another PMM to your team — without the headcount."

Followed by a button: **"Try Claude Code free"** → links to install docs.

## Design requirements

- Inline on the landing page (new section between "Before/After" and "But I'm not a developer"), or available as a standalone page linked from the CTA
- Clean, minimal UI consistent with the existing site design (dark navy + white + subtle accents)
- Sliders should be styled, not browser-default range inputs
- Mobile-responsive: sliders stack vertically, results remain visible
- No JavaScript frameworks — vanilla JS to keep it simple and fast

## Edge cases

- All sliders at 0: Show "Adjust the sliders to see your results" instead of "0 hours saved"
- All sliders at max: Cap the yearly messaging at a reasonable number; don't let it say "You'd save 1,500 hours a year"
- Very small totals (< 1 hr/week): Still show the number; don't hide or round to zero

## Success metrics

- **Engagement:** % of page visitors who interact with at least one slider
- **Completion:** % of users who adjust 2+ sliders
- **Conversion:** Click-through rate on the CTA below the calculator result vs. the existing static CTA
- **Sharing:** (Stretch) Track if users screenshot or share via a "Share my results" link

## Open questions

1. Should this live inline on the main page or as a separate `/calculator` page?
2. Do we want a "Share my results" feature (generates a URL with slider values as query params)?
3. Should we A/B test the default slider values to optimize for the most compelling first impression?
