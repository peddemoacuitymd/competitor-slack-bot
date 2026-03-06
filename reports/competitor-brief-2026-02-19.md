# Competitor Brief — Week of February 19, 2026

## Top 3 Things to Know

1. **The CLI space just got more crowded.** Cline CLI 2.0 launched as a direct Claude Code competitor — terminal-native, parallel agents, CI/CD headless mode, and ACP protocol support. Their core attack: "Claude Code locks you into one vendor." This is the most direct competitive threat this week.
2. **Cursor is pulling away on enterprise governance.** "Cursor Blame" — AI attribution at the line level, broken down by model vs. human — is a compliance and auditability feature Claude Code has no answer to. Combined with long-running agents now in GA for paid tiers, Cursor is solidifying its enterprise narrative.
3. **GitHub is simultaneously a partner and a threat.** GitHub Agentic Workflows (technical preview) supports Claude Code as an underlying agent — but GitHub Copilot is the native default. The Copilot SDK further embeds GitHub's engine into third-party products. Don't mistake integration for alignment.

---

## Cursor
**Changes:**
- Long-running agents launched (GA for Ultra, Teams, Enterprise) at cursor.com/agents — handles complex, multi-step tasks autonomously with planning phase
- Parallel subagents: independent agents with isolated context, custom prompts, and configurable model/tool access running in parallel
- **Cursor Blame** (Enterprise): line-level attribution of code to Tab completions, agent runs (by model), or human edits — with team-level usage tracking
- Agents can ask clarifying questions mid-task while continuing to work in parallel
- Usage limits permanently expanded (2x pools: Auto+Composer and API); 6x limited-time promo closed Feb 16

**Competitive Implications:**
- Long-running agents directly mirrors Claude Code's background agent push — but Cursor wraps it in a visual IDE harness, making it more accessible to non-CLI users
- Cursor Blame is a genuine gap for Claude Code. Enterprise buyers increasingly need auditability ("what did the AI write?"). This is a compliance wedge worth tracking closely — consider whether Claude Code can surface attribution data via git hooks or session logs
- Messaging opportunity: Claude Code's CLI-native approach enables deeper CI/CD integration, which Cursor's IDE model can't easily replicate. Lean into that for DevOps-oriented buyers

**Sources:**
- https://releasebot.io/updates/cursor

---

## GitHub Copilot
**Changes:**
- **GitHub Agentic Workflows** (technical preview, Feb 17): Describe desired outcomes in Markdown → runs as coding agent in GitHub Actions. Isolated containers, read-only repo access by default, firewall-restricted network. Supports Copilot, Claude Code, and OpenAI Codex as underlying agents
- **GitHub Copilot SDK** (technical preview): Embeds Copilot's agentic engine into third-party apps. Supports Node.js, Python, Go, .NET. Includes filesystem, Git ops, and web request tools out of the box with extensible custom agents/skills

**Competitive Implications:**
- The Agentic Workflows integration is a double-edged sword: Claude Code gains distribution inside GitHub's platform, but Copilot is the default/native agent with tightest integration. "Supported" is not the same as "preferred"
- The Copilot SDK is a platform play that could pull developer mindshare — if teams embed Copilot into internal tooling, Claude Code becomes a harder sell. Monitor SDK adoption closely
- Opportunity: GitHub's security model (read-only by default, Safe Outputs subsystem) creates friction for power users who want full agentic autonomy. Claude Code's more permissive-by-default model is a differentiator for sophisticated engineering teams

**Sources:**
- https://winbuzzer.com/2026/02/17/github-agentic-workflows-technical-preview-continuous-ai-xcxwbn/
- https://www.theregister.com/2026/02/17/github_previews_agentic_workflows/
- https://www.infoq.com/news/2026/02/github-copilot-sdk/

---

## Windsurf
**Changes:**
- **Arena Mode leaderboard launched** (Feb 12): Public, crowdsourced real-world model rankings from actual dev tasks. Top frontier models: Opus 4.6, Opus 4.5, Sonnet 4.5. Top fast models: SWE-1.5, Haiku 4.5, Gemini 3 Flash Low. Plans to add per-language and per-task-type breakdowns
- Claude Sonnet 4.6 added with limited-time promotional pricing (2x credits without thinking, 3x with thinking)
- GLM-5 and Minimax M2.5 added to model roster (Feb 17)

**Competitive Implications:**
- Arena Mode is a clever marketing and data play — Windsurf is building its own "real-world benchmark" from production usage, then publishing it. Claude Code can't replicate this (CLI tools don't have a natural head-to-head comparison surface). Watch for Windsurf using this data in sales conversations to argue model-agnosticism as a feature
- Windsurf adopting Sonnet 4.6 on day one undercuts Claude Code's model-recency advantage — users can get the latest Claude through Windsurf with a better IDE experience
- Key message to reinforce: Claude Code users get model updates first, native tool integration that third-party wrappers can't match, and direct Anthropic support. Windsurf's "any model" pitch is also a "no model commitment" story

**Sources:**
- https://windsurf.com/blog/windsurf-arena-mode-leaderboard
- https://windsurf.com/blog/sonnet-4.6
- https://www.infoq.com/news/2026/02/windsurf-arena-mode/

---

## Cline
**Changes:**
- **Cline CLI 2.0 launched** (Feb 13): Full-featured terminal agent rebuilt from scratch as a CLI-first tool (not a port of the VS Code extension)
  - Parallel isolated agents with independent state, model config, and conversation context
  - Headless CI/CD mode (`-y` flag) with full stdin/stdout support — chainable as a Unix tool, pipeable into GitHub Actions/GitLab CI
  - ACP (Agent Client Protocol) support — works across JetBrains, Zed, Neovim, Emacs
  - Free trial models at launch (Kimi K2.5, MiniMax M2.5)
- Apache 2.0 open source, 5M+ developer install base
- MiniMax M2.5 integrated (Feb 12)
- Supply chain security incident (details limited — monitor for fallout)

**Competitive Implications:**
- This is the most direct competitive threat this week. Cline CLI 2.0 is explicitly positioned against Claude Code, with "vendor lock-in" as the attack vector. Their framing ("Claude Code only uses Anthropic models, which aren't always SOTA") will resonate with cost-sensitive and model-curious developers
- The headless CI/CD mode with Unix pipe support matches Claude Code's core DevOps use case — this is no longer a feature gap Cline has; it's now competitive parity
- ACP support is a forward-looking moat play — if ACP becomes the LSP of AI agents, Cline being an early adopter matters
- Counter-messaging: Claude Code's single-model approach is also a quality guarantee — users know exactly what they're getting. Anthropic's safety, reliability, and model consistency are things multi-model tools can't promise uniformly. The supply chain incident (however minor) is worth watching as a trust signal contrast

**Sources:**
- https://cline.bot/blog/introducing-cline-cli-2-0
- https://devops.com/cline-cli-2-0-turns-your-terminal-into-an-ai-agent-control-plane/

---

## Aider
**Changes:**
- No major feature launches, pricing changes, or strategic announcements this week
- Active GitHub commit cadence through Feb 19 (specific changes not indexed)
- PyPI release on Feb 12 (changelog details not surfaced publicly)
- Claude 3.7 Sonnet now top-listed recommended model on homepage
- Recent (pre-window) notable features: `/think-tokens` command for reasoning budget control, expanded language support via tree-sitter-language-pack

**Competitive Implications:**
- Aider continues to use Claude Code's own model as its headline feature — "best with Claude 3.