"""Real-time engagement listeners — webhook / firehose / streaming.

v0.11+: Bluesky firehose (free WebSocket from atproto sync).
v0.12+ planned: Mastodon streaming API, GitHub webhooks (already in workflows).

Why not X? Account Activity API requires Enterprise tier (~$42k/yr per Q1
2026). Indie founders can't justify it. Use polling via existing
EngagementTracker.fetch_x_metrics() instead — costs ~100 reads/month from
the X free tier.
"""
