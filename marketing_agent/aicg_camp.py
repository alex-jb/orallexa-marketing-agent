"""
aicg_camp.py — daily AICG NYC Camp recruitment draft generator.

Wires existing viral_patterns + luminaries into a 3-platform draft set
(小红书 / LinkedIn / X) for the AICG NYC Camp 2026-07 Phase 0 workshop
(see alex-brain projects/aicg-camp.md).

Funnel role: produces drafts → HITL queue at ~/.marketing_agent/queue/pending/
(matches existing pattern from 2026-05 launch). Alex审 → posts to platforms.

Daily rotation: 5 angle families × 3 platforms = 15 draft variants. Day-of-week
picks the angle so cron runs cleanly without dedup logic.

Usage:
    python -m marketing_agent.aicg_camp                # writes today's drafts
    python -m marketing_agent.aicg_camp --dry-run       # prints to stdout
    python -m marketing_agent.aicg_camp --angle wave    # force one angle

Cron (later, optional):
    launchd plist firing 9:00 AM NY weekdays → calls without args.

Honest constraints:
    - URL is vibexforge.com/aicg-camp (already shipped 2026-06-09)
    - Pricing: $249 early-bird (8 seats), $299 after
    - Audience: marketing/HR/ops 知识工作者 (NOT engineers — they go to Fullstack/GA)
    - 中文 受众: NYC Chinese diaspora (Google-zero competitor surface)
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Platform = Literal["xiaohongshu", "linkedin", "x"]
Angle = Literal["wave", "recruit", "negative", "honest", "anchor"]

# --- Static config -----------------------------------------------------------

LANDING_URL = "https://vibexforge.com/aicg-camp"
LEARN_URL = "https://vibexforge.com/learn"
COUNCIL_URL = "https://vibexforge.com/council"
EARLY_BIRD_PRICE = 249
RETAIL_PRICE = 299
SEATS = 8
COHORT_MONTH = "July 2026"


@dataclass(frozen=True)
class DraftSet:
    """One full daily draft set across 3 platforms."""

    date: dt.date
    angle: Angle
    xiaohongshu: str
    linkedin: str
    x: str


# --- 5 angle families --------------------------------------------------------

def _wave_borrow_xiaohongshu() -> str:
    """Karpathy Eureka Labs paused 5/19 → NYC keeps the lights on."""
    return f"""# Karpathy 5/19 暂停了 Eureka Labs。NYC 我们接上 🔥

📍 Manhattan / Brooklyn 可达
👤 marketing / HR / 运营 / PM,被 AI 焦虑追着的成年人
💰 早鸟 ${EARLY_BIRD_PRICE} · {SEATS} 席位 · 满后 ${RETAIL_PRICE}

Karpathy 上个月把 Eureka Labs(AI 教育实验)按了暂停键。
他的 nanochat($100 在家搭 ChatGPT clone)成了无人接的孤儿教材。

NYC,我们 7 月把这个 in-person 接住:
- 6 小时,1 个周六
- 3 个实战(召唤图 → prompt 工程 → 第一个 AI agent)
- 当场 Brier-audited 5-voice council 点评你的作品
- 作品发到 VibeXForge,简历可挂

Anthropic Academy / OpenAI Academy 免费课跟完想接下一步的:
{LEARN_URL}(3 关免费先玩)
{LANDING_URL}(报名)

#AI学习 #纽约 #vibecoding #karpathy #nyc中文
"""


def _wave_borrow_linkedin() -> str:
    return f"""When Andrej Karpathy paused Eureka Labs on May 19 to join Anthropic, his "nanochat" curriculum — $100 to build a ChatGPT clone from scratch — was left orphaned.

I'm running it as a NYC in-person weekend this July.

Six hours, one Saturday, $249 early-bird (8 seats).
Audience: marketing / HR / ops / PM professionals who feel the AI pressure but don't want a $10K engineering bootcamp.

What's different from Anthropic Academy + OpenAI Academy (both free, both excellent):
- In-person NYC, bilingual EN / 中文
- Three real artifacts shipped, not three videos watched
- 5-voice Brier-audited AI council critiques your project at the end
- Output publishes to VibeXForge with a permanent share link

Free preview: {LEARN_URL}
Reserve a seat: {LANDING_URL}

Karpathy paused. NYC keeps the lights on.
"""


def _wave_borrow_x() -> str:
    return f"""karpathy paused eureka labs in may.

nanochat ($100 chatgpt-clone curriculum) is orphaned.

running it as a NYC in-person weekend, july. 6h, $249 early-bird, 8 seats.

bilingual, ships to vibex, 5-voice council critiques your work.

→ {LANDING_URL}
"""


def _recruit_invite_xiaohongshu() -> str:
    return f"""# 6 小时 = 一个真实 AI 作品(NYC 7 月)

不是 50 节视频。
不是 $10K bootcamp。
不是听讲师 1 个人主观判断。

一个周六,纽约房间里 8 个人,带笔记本来。
出门的时候你有:
- 1 张发到 VibeXForge 的真实作品(可挂简历)
- 5-voice AI council 4 角度点评(印在卡背面)
- 完整代码 + 复盘模板

定价 ${EARLY_BIRD_PRICE} 早鸟(前 8 席),之后 ${RETAIL_PRICE}。
7 天前 100% 退款。开课后没产出 → 下期免费换一席。

适合谁:
✓ marketing / HR / 运营 / PM,在 AI 焦虑里
✓ 中文社群,想 in-person + 双语
✓ Anthropic/OpenAI Academy 跟完想接下一步

谁别报:
✗ 想要工程师全栈 bootcamp 的(Fullstack/GA 已经有)
✗ 13-17 岁青少年(我们暑期 Phase 2 才碰)

报名: {LANDING_URL}
先免费玩 3 关: {LEARN_URL}

#纽约 #AI #vibecoding #北美生活 #中文社群"""


def _recruit_invite_linkedin() -> str:
    return f"""I'm teaching a Saturday AI workshop in NYC, July 2026. $249 early-bird, 8 seats.

This is a deliberately narrow offer:
- For non-engineers in marketing / HR / ops / product who feel AI pressure but won't pay $10K for a bootcamp.
- Bilingual EN / 中文.
- Six hours, one room, three real builds, one VibeX-published artifact.

What I'm not doing:
- Not competing with Fullstack Academy or General Assembly for engineers.
- Not running a teen camp in Phase 0.
- Not charging for "AI 101" content — Anthropic Academy and OpenAI Academy already do that for free. I'm the step after.

Refund policy: 100% if cancelled 7+ days out. Free seat in the next cohort if you don't ship a real artifact.

Public first-cohort data lands at vibexforge.com/postmortems within 48 hours of running it. Whether good or bad.

Free preview: {LEARN_URL}
Reserve: {LANDING_URL}
"""


def _recruit_invite_x() -> str:
    return f"""NYC AI workshop, july, 6h, $249.

8 seats. marketing/HR/ops folks anxious about AI. not for engineers.

bilingual. ships a real vibex artifact. brier-audited 5-voice council critique.

i publish enrollment + p&l 48h after. honest.

→ {LANDING_URL}
"""


def _negative_space_xiaohongshu() -> str:
    return f"""# NYC 6-8 月 5 家 AI bootcamp 都在抢你 — 我们故意做最小的

BrainStation Crosby 4F · 整月开
Maven 在线 cohort · 已售罄
DesignLab $999 · 4 周
General Assembly · 免费引流
Noble Desktop $1495 · 入门

我们 AICG NYC:
- 1 个周六(不是 4 周)
- 8 席位(不是 50)
- ${EARLY_BIRD_PRICE} 早鸟(不是 $999)
- 双语(全场唯一一家)
- 你的作品当场发 VibeXForge(不是讲师 demo)

我们故意做最小。因为 marketing/HR/ops 那些焦虑的成年人需要的不是 4 周课程,是**一个周六之后能挂在 LinkedIn 上的东西**。

报名: {LANDING_URL}

#纽约 #AI #vibecoding"""


def _negative_space_linkedin() -> str:
    return f"""NYC's June-August 2026 AI workshop calendar is crowded: BrainStation (full month at 136 Crosby), Maven, DesignLab, General Assembly, Noble Desktop.

I'm running one Saturday workshop. ${EARLY_BIRD_PRICE} early-bird. 8 seats.

Why deliberately small:
- The audience that actually needs this — marketing / HR / ops professionals quietly anxious about AI — doesn't want 4 weeks. They want one Saturday and something to put on LinkedIn by Monday morning.
- Bilingual EN / 中文 — zero NYC competitor offers this in-person.
- Public first-cohort data within 48 hours at vibexforge.com/postmortems.

If you want the comprehensive bootcamp experience, go to Fullstack or GA — those are real schools and I won't pretend to replace them. If you want a real Saturday and a shippable artifact, that's what AICG is.

{LANDING_URL}
"""


def _negative_space_x() -> str:
    return f"""5 NYC AI bootcamps running june-aug. i'm running 1 saturday.

8 seats. ${EARLY_BIRD_PRICE} early-bird. bilingual EN/中文 (nobody else offers this in-person).

deliberately small. for marketing/HR/ops folks who want one saturday + 1 shippable thing, not 4 weeks.

→ {LANDING_URL}
"""


def _honest_xiaohongshu() -> str:
    return f"""# 我会公开首期数据(不论好坏)

NYC 培训班的招生页都写"6/8 人上岸 / 学员都满意"。
没人写"招了 4 人,3 人没完课,净亏 $500"。

我会。开课后 48 小时,真实人数 + 完课率 + 净利润全部贴到 vibexforge.com/postmortems。

这不是营销话术。这是因为我已经有 4 篇公开 postmortem 了(quant 交易系统 walkforward FAIL / SPCX IPO SKIP / paper P&L -$1015)。规则一致。

所以首期 $249 / 8 席 / 7 月某周六:
- 如果你信"诚实的失败比假的成功更有用",报名
- 如果你想要"100% 上岸保证",请去别家

报名: {LANDING_URL}
我之前的 postmortem: https://vibexforge.com/postmortems

#纽约 #AI #vibecoding #诚实"""


def _honest_linkedin() -> str:
    return f"""Most NYC AI bootcamp landing pages claim "6/8 students placed" or "all students satisfied." None publish "enrolled 4, 3 didn't finish, net loss $500."

I will. 48 hours after my first AICG NYC cohort wraps, the real enrollment, completion, and P&L numbers go to vibexforge.com/postmortems.

This isn't a marketing line. I already have four public postmortems there — Orallexa walkforward FAIL (mean OOS Sharpe -3.08), Markets paper P&L -$1,015, BKSY trade canceled, SPCX IPO skipped. Same rule applies to teaching.

First cohort: Saturday July 2026, NYC, ${EARLY_BIRD_PRICE} early-bird, 8 seats.

If you believe honest negative results are more useful than performative positives, reserve a seat. If you need a 100% placement guarantee, please pick a different provider.

{LANDING_URL}
"""


def _honest_x() -> str:
    return f"""no NYC AI bootcamp publishes "enrolled 4, 3 didn't finish, $500 loss." they all claim 6/8 placed.

i will. 48h after my first AICG cohort, enrollment + completion + P&L → /postmortems.

same discipline as my 4 quant postmortems. honest negative > performative positive.

${EARLY_BIRD_PRICE} early-bird, 8 seats, july saturday.

→ {LANDING_URL}
"""


def _anchor_xiaohongshu() -> str:
    return f"""# $249 → $1500 (4 周 cohort) → $10K bootcamp 的中间路线

NYC AI 教育的真实价格段:
- 免费 → Anthropic / OpenAI Academy(优秀但没人盯你交作业)
- $299 → Noble Desktop 单日(讲师讲你听)
- $999 → DesignLab 4 周(在线 cohort)
- $1495+ → Noble Desktop 多日
- $10K-16K → Fullstack / GA bootcamp(工程师向)

AICG ${EARLY_BIRD_PRICE} 是入口,7 月之后会涨到 ${RETAIL_PRICE}。
Phase 1 我们 ship 4 周 cohort($1200-1500),专为 Phase 0 早期学员保留早鸟优先。

但 Phase 0 这次只 8 席。
报名: {LANDING_URL}

先试 3 关免费课: {LEARN_URL}

#纽约 #AI #vibecoding"""


def _anchor_linkedin() -> str:
    return f"""NYC AI workshop pricing as of mid-2026:
- Free → Anthropic Academy / OpenAI Academy (excellent, self-paced)
- $299 → Noble Desktop single-day (lecture format)
- $999 → DesignLab 4-week online cohort
- $1,495+ → Noble Desktop multi-day
- $10K-$16K → Fullstack Academy / General Assembly bootcamps (engineer track)

AICG NYC sits at the entry: ${EARLY_BIRD_PRICE} early-bird, ${RETAIL_PRICE} retail, one Saturday, bilingual, 8 seats.

Phase 1 ships a 4-week cohort at the $1,200-$1,500 tier in fall. Phase 0 early-bird seats get priority enrollment + tuition credit toward Phase 1.

8 seats for Phase 0: {LANDING_URL}
Free preview: {LEARN_URL}
"""


def _anchor_x() -> str:
    return f"""NYC AI workshop pricing right now:

- free: anthropic academy / openai academy
- $299: noble desktop single-day
- $999: designlab 4-week
- $10-16K: fullstack / GA bootcamps

AICG ${EARLY_BIRD_PRICE} early-bird, july saturday, bilingual, 8 seats. ships a real artifact.

→ {LANDING_URL}
"""


# --- Angle dispatch ----------------------------------------------------------

ANGLE_BUILDERS: dict[Angle, dict[Platform, callable]] = {
    "wave": {
        "xiaohongshu": _wave_borrow_xiaohongshu,
        "linkedin": _wave_borrow_linkedin,
        "x": _wave_borrow_x,
    },
    "recruit": {
        "xiaohongshu": _recruit_invite_xiaohongshu,
        "linkedin": _recruit_invite_linkedin,
        "x": _recruit_invite_x,
    },
    "negative": {
        "xiaohongshu": _negative_space_xiaohongshu,
        "linkedin": _negative_space_linkedin,
        "x": _negative_space_x,
    },
    "honest": {
        "xiaohongshu": _honest_xiaohongshu,
        "linkedin": _honest_linkedin,
        "x": _honest_x,
    },
    "anchor": {
        "xiaohongshu": _anchor_xiaohongshu,
        "linkedin": _anchor_linkedin,
        "x": _anchor_x,
    },
}

ANGLES: tuple[Angle, ...] = ("wave", "recruit", "negative", "honest", "anchor")


def pick_angle(date: dt.date) -> Angle:
    """Day-of-week rotation: Mon=wave, Tue=recruit, Wed=negative, Thu=honest, Fri=anchor."""
    # weekday(): Monday=0, ..., Sunday=6
    return ANGLES[date.weekday() % len(ANGLES)]


def build(date: dt.date | None = None, angle: Angle | None = None) -> DraftSet:
    """Generate the full 3-platform draft set for a given date."""
    d = date or dt.date.today()
    a: Angle = angle or pick_angle(d)
    builders = ANGLE_BUILDERS[a]
    return DraftSet(
        date=d,
        angle=a,
        xiaohongshu=builders["xiaohongshu"](),
        linkedin=builders["linkedin"](),
        x=builders["x"](),
    )


def write_to_queue(
    drafts: DraftSet,
    queue_root: Path | None = None,
) -> Path:
    """Write one combined markdown file to ~/.marketing_agent/queue/pending/.

    Matches existing 2026-05 launch package convention (per memory:
    "15 launch drafts in ~/.marketing_agent/queue/pending/").
    """
    root = queue_root or (Path.home() / ".marketing_agent" / "queue" / "pending")
    root.mkdir(parents=True, exist_ok=True)
    fname = f"{drafts.date.isoformat()}-aicg-camp-{drafts.angle}.md"
    fpath = root / fname

    body = f"""# AICG NYC Camp · daily drafts · {drafts.date.isoformat()}

**Angle:** {drafts.angle}
**Cohort:** {COHORT_MONTH} · NYC
**Pricing:** ${EARLY_BIRD_PRICE} early-bird (first {SEATS}) → ${RETAIL_PRICE} retail
**Landing:** {LANDING_URL}
**Preview:** {LEARN_URL}
**Status:** HITL — Alex审 before posting

---

## 小红书 (xiaohongshu)

```
{drafts.xiaohongshu}
```

---

## LinkedIn

```
{drafts.linkedin}
```

---

## X / Twitter

```
{drafts.x}
```

---

*Generated by marketing_agent.aicg_camp — angle rotates by day-of-week.*
*To regen with a different angle: `python -m marketing_agent.aicg_camp --angle recruit`*
"""
    fpath.write_text(body, encoding="utf-8")
    return fpath


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate daily AICG NYC Camp recruitment drafts.")
    p.add_argument("--angle", choices=ANGLES, help="Force a specific angle (default: day-of-week)")
    p.add_argument("--date", help="ISO date override (default: today)")
    p.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing")
    args = p.parse_args(argv)

    target_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    drafts = build(target_date, args.angle)

    if args.dry_run:
        print(f"=== AICG drafts · {drafts.date} · angle={drafts.angle} ===\n")
        print(f"--- 小红书 ---\n{drafts.xiaohongshu}\n")
        print(f"--- LinkedIn ---\n{drafts.linkedin}\n")
        print(f"--- X ---\n{drafts.x}\n")
        return 0

    path = write_to_queue(drafts)
    print(f"✓ wrote {path}")
    print(f"  angle: {drafts.angle}")
    print(f"  next step: read the file, edit if needed, post manually (or wire cmd_post)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
