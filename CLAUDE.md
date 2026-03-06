# Claude Code Marketing Site

## What this is
A marketing landing page for Claude Code, targeting product managers and product marketing managers (PMs/PMMs) at Series B SaaS companies. The goal is to convince non-technical marketers that Claude Code is relevant to their workflow.

## Target persona
Defined in `persona.md`. Always reference this file when writing or editing any user-facing copy. Match her language (pipeline, battlecards, QBR, content velocity), address her skepticism ("I'm not a developer"), and sell speed and independence — not a coding tool.

## Stack
- Plain HTML + inline CSS + vanilla JavaScript
- Single file: `index.html`
- No frameworks, no build step, no dependencies
- Served locally with `python3 -m http.server`

## Key files
- `index.html` — The full landing page (hero, pain points, before/after, ROI calculator, objection handling, CTA)
- `persona.md` — Target buyer persona (read this before writing any copy)
- `prd.md` — PRD for the ROI calculator feature
- `.claude/skills/frontend-design.md` — Frontend design skill (aesthetic guidelines for UI work)

## Conventions
- All copy should speak directly to the persona — use "you" language, mirror her frustrations, reference her actual tasks
- Keep the site as a single HTML file with inline styles and a `<script>` block at the bottom
- No external dependencies or CDN imports, except Google Fonts for typography
