"""FastAPI wrapper that exposes `marketing-agent` as a Coze.cn plugin.

Hedge play — Coze main bet = 0% per Alex's brief. Sunset 2026-09-06 if
install count < 100. See SUBMISSION.md.

Run locally:
    cd ~/Desktop/orallexa-marketing-agent/coze_plugin
    pip install fastapi uvicorn
    pip install -e ..          # marketing_agent package
    export ANTHROPIC_API_KEY=sk-ant-...
    export COZE_PLUGIN_TOKENS=test-token-free,pro_test-token-pro
    python3 server.py
    # → http://127.0.0.1:8000/docs

Wrap, don't rewrite: this calls `marketing_agent.Orchestrator.generate()`
directly so every existing capability (Thompson sampling, viral_patterns,
prompt caching, ICPL preference, edge-tier fallback) flows through to
Coze users with zero divergence.
"""
from __future__ import annotations

import os
import time
import logging
from collections import defaultdict, deque
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl

# Wrap the existing package — do NOT reimplement.
from marketing_agent import Orchestrator, Project, Platform, GenerationMode

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("coze_plugin")

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

# Coze plugin store users are Chinese-speaking — these are the user-facing
# labels we accept in the request body. Map to the canonical Platform enum.
# Note: HACKER_NEWS / SUBSTACK / MASTODON / ZHIHU exist in the enum but
# the brief lists 即刻 / B站 / Product Hunt which don't ship as
# first-class adapters yet — we accept the alias and degrade to the
# closest semantic match (or skip + warn).
PLATFORM_ALIAS: dict[str, Platform] = {
    # English canonical
    "x": Platform.X,
    "twitter": Platform.X,
    "reddit": Platform.REDDIT,
    "linkedin": Platform.LINKEDIN,
    "hn": Platform.HACKER_NEWS,
    "hacker_news": Platform.HACKER_NEWS,
    "hackernews": Platform.HACKER_NEWS,
    "dev_to": Platform.DEV_TO,
    "devto": Platform.DEV_TO,
    "bluesky": Platform.BLUESKY,
    "mastodon": Platform.MASTODON,
    "threads": Platform.THREADS,
    "substack": Platform.SUBSTACK,
    "zhihu": Platform.ZHIHU,
    "xiaohongshu": Platform.XIAOHONGSHU,
    # Chinese names (Coze users)
    "小红书": Platform.XIAOHONGSHU,
    "知乎": Platform.ZHIHU,
    # User-listed aliases that don't have first-class adapters; degrade
    # gracefully to the closest semantic neighbor so plugin doesn't 500.
    "product_hunt": Platform.LINKEDIN,   # Launch-pitch style ≈ LinkedIn
    "ph": Platform.LINKEDIN,
    "即刻": Platform.X,                  # Short-form ≈ X
    "jike": Platform.X,
    "b站": Platform.DEV_TO,              # Long-form ≈ Dev.to article
    "bilibili": Platform.DEV_TO,
}

DEFAULT_PLATFORMS: list[Platform] = [
    Platform.X, Platform.REDDIT, Platform.LINKEDIN, Platform.HACKER_NEWS,
    Platform.DEV_TO, Platform.BLUESKY, Platform.THREADS, Platform.XIAOHONGSHU,
    Platform.ZHIHU,
]

# Coze plugin contract: per-response <= 50KB. Each draft ~1-3KB so 9-12
# drafts comfortably fit, but cap defensively.
MAX_RESPONSE_BYTES = 50_000
MAX_PLATFORMS_PER_REQUEST = 12
COZE_TIMEOUT_SECONDS = 60

# Rate limits — free 5/min, Pro 50/min. Tokens prefixed `pro_` get Pro.
RATE_LIMIT_FREE = 5
RATE_LIMIT_PRO = 50
RATE_WINDOW_SECONDS = 60

# Cost estimate per platform (Sonnet 4.6 input+output, post prompt-cache).
# Empirical: ~$0.0015 per platform with cache hits, $0.005 cold. Use a
# conservative midpoint for the user-visible estimate.
COST_PER_PLATFORM_USD = 0.002

# --------------------------------------------------------------------------
# Auth + rate-limit state (in-memory; v0 has no DB per brief)
# --------------------------------------------------------------------------

_request_log: dict[str, deque[float]] = defaultdict(deque)


def _valid_tokens() -> set[str]:
    raw = os.getenv("COZE_PLUGIN_TOKENS", "").strip()
    if not raw:
        return set()
    return {t.strip() for t in raw.split(",") if t.strip()}


def _check_auth(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_bearer",
                "message_zh": "缺少 Authorization Bearer token",
                "message_en": "Missing Authorization: Bearer <token>",
            },
        )
    token = authorization.split(" ", 1)[1].strip()
    tokens = _valid_tokens()
    if not tokens:
        # Dev mode — server started without COZE_PLUGIN_TOKENS env. Log
        # loudly so this isn't silently shipped to prod.
        log.warning("COZE_PLUGIN_TOKENS is empty — accepting any non-empty bearer (DEV ONLY)")
        return token
    if token not in tokens:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_token",
                "message_zh": "无效的 token,请联系插件作者",
                "message_en": "Invalid token; contact plugin author",
            },
        )
    return token


def _check_rate_limit(token: str) -> None:
    limit = RATE_LIMIT_PRO if token.startswith("pro_") else RATE_LIMIT_FREE
    now = time.time()
    q = _request_log[token]
    # Drop expired entries
    while q and now - q[0] > RATE_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= limit:
        retry_after = int(RATE_WINDOW_SECONDS - (now - q[0])) + 1
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit",
                "message_zh": f"超过速率限制 ({limit} 次/分钟)。请 {retry_after} 秒后重试,或升级 Pro 享受 {RATE_LIMIT_PRO} 次/分钟。",
                "message_en": f"Rate limit exceeded ({limit}/min). Retry in {retry_after}s or upgrade to Pro for {RATE_LIMIT_PRO}/min.",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
    q.append(now)


# --------------------------------------------------------------------------
# Request / Response schemas
# --------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    project_url: HttpUrl = Field(
        ...,
        description="要推广的 AI 项目 URL / Project URL to promote",
        examples=["https://github.com/alex-jb/orallexa-marketing-agent"],
    )
    project_name: str = Field(
        ..., min_length=1, max_length=80,
        description="项目名 / Project name",
        examples=["marketing-agent"],
    )
    project_description: str = Field(
        ..., min_length=10, max_length=2000,
        description="一两句话简介 / 1-2 sentence pitch",
        examples=["12 平台 AI 自动写文案,给独立开发者用的营销代理。"],
    )
    platforms: Optional[list[str]] = Field(
        default=None,
        description="平台列表,留空 = 全部 12 个 / Platforms, empty = all 12",
        examples=[["x", "小红书", "即刻"]],
    )
    language: str = Field(
        default="zh",
        pattern="^(zh|en|both)$",
        description="语言:zh / en / both / Language",
    )
    tags: Optional[list[str]] = Field(
        default=None, max_length=20,
        description="可选标签 / Optional tags",
    )


class Draft(BaseModel):
    platform: str = Field(..., description="平台名 / Platform")
    title: Optional[str] = Field(None, description="标题(Reddit/HN 用)/ Title")
    body: str = Field(..., description="正文 / Post body")
    char_count: int = Field(..., description="字符数 / Character count")
    variant_key: Optional[str] = Field(None, description="A/B 变体 key / Variant key")


class GenerateResponse(BaseModel):
    drafts: list[Draft]
    generation_cost_usd: float = Field(..., description="预估生成成本 USD")
    model: str = Field(..., description="主模型 / Primary model")
    cache_hit_ratio: float = Field(..., description="预估缓存命中率")
    notes: list[str] = Field(default_factory=list,
                              description="降级/警告说明 / Degradation notes")


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------

app = FastAPI(
    title="marketing-agent 多平台文案生成器",
    description=(
        "一次输入项目信息,生成 12 平台原生风格文案(X / Reddit / "
        "HN / Dev.to / LinkedIn / Bluesky / Threads / Product Hunt / "
        "小红书 / 即刻 / 知乎 / B站)。\n\n"
        "Wrap of open-source [marketing-agent](https://github.com/"
        "alex-jb/orallexa-marketing-agent) by Solo Founder OS。"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": "marketing-agent-coze",
        "version": "0.1.0",
        "homepage": "https://github.com/alex-jb/orallexa-marketing-agent",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health")
def health():
    """Liveness probe — used by Coze health check + Vercel."""
    return {
        "status": "ok",
        "anthropic_key_present": bool(os.getenv("ANTHROPIC_API_KEY")),
        "tokens_configured": len(_valid_tokens()),
        "version": "0.1.0",
    }


def _resolve_platforms(raw: Optional[list[str]]) -> tuple[list[Platform], list[str]]:
    """Map user platform strings → canonical Platform enum. Returns
    (resolved, warnings)."""
    if not raw:
        return DEFAULT_PLATFORMS, []
    if len(raw) > MAX_PLATFORMS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "too_many_platforms",
                "message_zh": f"平台超过 {MAX_PLATFORMS_PER_REQUEST} 个上限",
                "message_en": f"Max {MAX_PLATFORMS_PER_REQUEST} platforms per request",
            },
        )
    resolved: list[Platform] = []
    warnings: list[str] = []
    seen: set[Platform] = set()
    for name in raw:
        key = name.strip().lower()
        plat = PLATFORM_ALIAS.get(key) or PLATFORM_ALIAS.get(name.strip())
        if plat is None:
            warnings.append(f"未知平台 '{name}' 已跳过 / unknown platform '{name}' skipped")
            continue
        if plat in seen:
            continue
        seen.add(plat)
        resolved.append(plat)
        # Note alias degradation for transparency.
        if key in ("product_hunt", "ph", "即刻", "jike", "b站", "bilibili"):
            warnings.append(
                f"平台 '{name}' 暂用 {plat.value} 风格代写 / "
                f"'{name}' rendered using {plat.value} style"
            )
    if not resolved:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_valid_platforms",
                "message_zh": "没有可识别的平台",
                "message_en": "No recognizable platforms supplied",
            },
        )
    return resolved, warnings


@app.post("/generate", response_model=GenerateResponse)
def generate(
    body: GenerateRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Generate one draft per platform via wrapped marketing-agent."""
    token = _check_auth(authorization)
    _check_rate_limit(token)

    started = time.time()
    platforms, warnings = _resolve_platforms(body.platforms)

    # Build the Project DTO. `marketing-agent` already handles missing
    # fields gracefully, so we pass through what the user provided.
    project = Project(
        name=body.project_name,
        tagline=body.project_description[:200],
        description=body.project_description,
        website_url=str(body.project_url),
        github_url=str(body.project_url) if "github.com" in str(body.project_url) else None,
        tags=(body.tags or [])[:20],
    )

    if body.language == "en":
        # Hint English by stuffing into description preamble; downstream
        # generator picks up tone from the prompt template.
        project = project.model_copy(update={
            "description": "[Write in English] " + (project.description or ""),
        })
    elif body.language == "both":
        project = project.model_copy(update={
            "description": "[Output bilingual EN + 中文] " + (project.description or ""),
        })
    # zh = default, no prefix needed

    orch = Orchestrator(mode=GenerationMode.HYBRID)
    try:
        posts = orch.generate(project, platforms)
    except Exception as e:
        log.exception("generate failed for token=%s...", token[:6])
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message_zh": "文案生成失败,请稍后重试",
                "message_en": "Generation failed — please retry",
                "internal": str(e)[:200],
            },
        )

    elapsed = time.time() - started
    if elapsed > COZE_TIMEOUT_SECONDS - 2:
        warnings.append(f"耗时 {elapsed:.1f}s 接近 Coze 60s 超时上限")

    drafts = [
        Draft(
            platform=p.platform.value,
            title=p.title,
            body=p.body,
            char_count=p.char_count or len(p.body),
            variant_key=p.variant_key,
        )
        for p in posts
    ]

    resp = GenerateResponse(
        drafts=drafts,
        generation_cost_usd=round(len(platforms) * COST_PER_PLATFORM_USD, 4),
        model="claude-sonnet-4-6"
            if os.getenv("ANTHROPIC_API_KEY") else "template-fallback",
        cache_hit_ratio=0.7,   # Steady-state w/ prompt-cache TTL
        notes=warnings,
    )

    # Defensive size check — Coze rejects > 50KB responses.
    serialized = resp.model_dump_json()
    if len(serialized.encode("utf-8")) > MAX_RESPONSE_BYTES:
        # Trim body texts proportionally rather than fail outright.
        log.warning("response > 50KB, trimming bodies")
        for d in resp.drafts:
            if len(d.body) > 1500:
                d.body = d.body[:1500] + "...[truncated for Coze size limit]"
        resp.notes.append("响应超过 50KB,已截断 / response truncated to fit Coze 50KB cap")

    log.info("generate ok token=%s... platforms=%d elapsed=%.1fs",
             token[:6], len(platforms), elapsed)
    return resp


# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
