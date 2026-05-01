# MCP listing demo — recording script

**Goal:** 60-second screen-record showing Claude Desktop calling marketing-agent MCP tools end-to-end. Captures what the marketplace card promises in one take.

**Tools needed:** Claude Desktop, screen recorder (QuickTime: `Cmd+Shift+5`), microphone optional (no narration needed — just text overlay if you want).

## Pre-roll setup (do this once, off-camera)

1. Install the MCP locally:
   ```bash
   pip install -e ".[mcp]"   # from repo root
   ```
2. Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "marketing-agent": {
         "command": "marketing-agent-mcp"
       }
     }
   }
   ```
3. Restart Claude Desktop. Verify the MCP shows up under tools (🔌 icon, lower-left).

## Recording — 60 seconds, three beats

### Beat 1 (0:00 – 0:15) — show the tools menu

Open a new Claude conversation. Click the 🔌 icon in lower-left. Pause for 1-2 seconds so viewer sees `marketing-agent` listed with its 7 tools (draft_posts, submit_to_queue, list_queue, engagement_top, optimal_time, bandit_stats, launch_plan).

Caption overlay: **"7 tools, 1 install"**

### Beat 2 (0:15 – 0:40) — natural-language draft

In the chat, type and send (verbatim — short, copyable):

```
Use marketing-agent to draft today's X and LinkedIn posts for my repo
alex-jb/orallexa-marketing-agent. The latest commit shipped v0.18 — VibeX
top-of-feed source. Use template mode (no LLM key needed).
```

Claude invokes `draft_posts`. Wait for the 2 drafts to render. Don't read them aloud — let viewer skim.

Caption overlay: **"Drafts pulled from your real commits"**

### Beat 3 (0:40 – 0:60) — show the queue + launch plan

Send:

```
Now show my approval queue, then make a 30-day launch plan with PH on day 14.
```

Claude calls `list_queue` (shows pending/approved/posted/rejected counts) then `launch_plan`. Pause on the launch plan output for 3 seconds.

Caption overlay: **"HITL queue + 30/60/90-day plan, all from inside Claude"**

## Final 5 seconds — outro

Cut to a static slide:

> **Marketing Agent · MCP server**
> github.com/alex-jb/orallexa-marketing-agent
> `pip install "orallexa-marketing-agent[mcp]"`

## Post-production

- Cut dead time aggressively (any pause > 1 sec)
- 1080p minimum
- Mute or no audio (overlays carry the message; lets viewer scrub on mute)
- Export as `.mp4` H.264, target ≤ 8 MB so it inlines on the marketplace listing
- Filename: `marketing-agent-mcp-demo-2026-05.mp4`

## Recording checklist

- [ ] Quit unrelated apps (no Slack notifications mid-take)
- [ ] Set screen resolution to 1920×1080 before recording (zoom UI text up if needed)
- [ ] Keep Claude Desktop window in the same position throughout
- [ ] One clean take is enough — don't perfect, ship
