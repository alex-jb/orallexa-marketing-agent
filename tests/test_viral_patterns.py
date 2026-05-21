"""Tests for marketing_agent.content.viral_patterns."""
from __future__ import annotations

import pytest

from marketing_agent.content.viral_patterns import (
    MEME_TEMPLATES,
    casual_humanizer_zh,
    lint_draft,
    negative_space_positioning,
    render_meme_borrow,
    render_recruit_invite,
    render_wave_borrow_post,
)
from marketing_agent.types import Platform, Project


# ────────────────────────────────────────────────────────────────────
# Negative-space positioning
# ────────────────────────────────────────────────────────────────────

class TestNegativeSpacePositioning:
    def test_zh_two_not_categories(self):
        result = negative_space_positioning(
            "念念",
            ["日记 app", "聊天 bot"],
            "你说一句话,世界长出来一点东西",
        )
        assert result == "念念 — 不是日记 app,不是聊天 bot,是你说一句话,世界长出来一点东西。"

    def test_zh_three_not_categories(self):
        result = negative_space_positioning(
            "VibeXForge",
            ["ProductHunt", "GitHub trending", "技术博客"],
            "给中国独立 AI 创作者一个真能炸的舞台",
        )
        assert "不是ProductHunt" in result
        assert "不是GitHub trending" in result
        assert "不是技术博客" in result
        assert result.endswith("。")

    def test_en_two_not_categories(self):
        result = negative_space_positioning(
            "BuzzPlay",
            ["a video app", "a meme generator"],
            "a way to ship playable AI ideas in 60 seconds",
            language="en",
        )
        assert result == (
            "BuzzPlay — not a video app, not a meme generator — "
            "a way to ship playable AI ideas in 60 seconds."
        )

    def test_rejects_single_not_category(self):
        with pytest.raises(ValueError, match="at least 2"):
            negative_space_positioning("X", ["only one"], "something")


# ────────────────────────────────────────────────────────────────────
# Recruit-invite
# ────────────────────────────────────────────────────────────────────

def _project() -> Project:
    return Project(
        name="念念",
        tagline="你说一句话,世界长出来一点东西",
        tags=["voice", "journal", "ai"],
    )


class TestRecruitInvite:
    def test_xiaohongshu_5_parts(self):
        p = _project()
        post = render_recruit_invite(
            p,
            user_action_verbs=["按住麦", "听见", "种下"],
            validation_hook="昨天试了一下发朋友圈 评论区炸了哈哈哈",
        )
        body = post.body
        # [1] problem framing — verbs joined with、
        assert "按住麦、听见、种下" in body
        # [2] validation hook present verbatim
        assert "评论区炸了哈哈哈" in body
        # [3] stage honesty
        assert "早期阶段" in body
        # [4] CTA double-track
        assert "评论区扣" in body and "聊聊" in body
        # [5] hashtag chain — brand + lifecycle tags
        assert "#念念" in body
        assert "#独立开发" in body
        assert "#产品内测" in body
        assert "#创业" in body
        # Platform routing
        assert post.platform == Platform.XIAOHONGSHU
        assert post.title == "念念 · 招内测"
        assert post.target == "xiaohongshu"

    def test_twitter_cta_voice(self):
        post = render_recruit_invite(
            _project(),
            user_action_verbs=["say it", "see it bloom"],
            validation_hook="A friend tried it last night.",
            target="twitter",
        )
        assert "DM me" in post.body
        assert post.platform == Platform.X
        # Twitter defaults language=en — body should NOT contain Chinese
        # stage-honesty boilerplate
        assert "目前产品还在早期阶段" not in post.body
        assert "Product is still very early" in post.body

    def test_showhn_cta_voice(self):
        post = render_recruit_invite(
            _project(),
            user_action_verbs=["press the mic", "watch the scene grow"],
            validation_hook="First test build runs locally.",
            target="showhn",
        )
        assert "Feedback would mean a lot" in post.body
        assert post.platform == Platform.HACKER_NEWS

    def test_en_uses_english_tags_by_default(self):
        post = render_recruit_invite(
            _project(),
            user_action_verbs=["say it", "see it bloom"],
            validation_hook="Test.",
            target="twitter",
        )
        # Default tags switch to indiehackers / buildinpublic / showhn /
        # earlyaccess (vs zh 独立开发 / 产品内测 / AI产品 / 创业)
        assert "#indiehackers" in post.body
        assert "#独立开发" not in post.body

    def test_language_override_zh_target_en(self):
        # Bilingual brand might want xiaohongshu visual + en body
        post = render_recruit_invite(
            _project(),
            user_action_verbs=["say", "listen"],
            validation_hook="Test.",
            target="xiaohongshu",
            language="en",
        )
        assert "your friend can" in post.body
        assert post.platform == Platform.XIAOHONGSHU

    def test_extra_tags_appear_and_dedupe(self):
        post = render_recruit_invite(
            _project(),
            user_action_verbs=["v1", "v2"],
            validation_hook="ok",
            extra_tags=["互动内容", "AI产品", "独立开发"],  # last collides w/ default
        )
        # Custom tag appears
        assert "#互动内容" in post.body
        assert "#AI产品" in post.body
        # Defaults still appear
        assert "#独立开发" in post.body
        # No duplicate
        assert post.body.count("#独立开发") == 1


# ────────────────────────────────────────────────────────────────────
# Casual humanizer
# ────────────────────────────────────────────────────────────────────

class TestWaveBorrow:
    def test_en_twitter_default(self):
        p = Project(name="SFOS", tagline="11 MIT agents for the operational stack",
                     github_url="https://github.com/alex-jb/solo-founder-os")
        post = render_wave_borrow_post(
            p,
            wave_actor="Anthropic",
            wave_action="shipped Claude connectors to 8 creative tools last week",
            your_angle="I built the same shape — for solo founders' operational stack.",
        )
        assert post.platform == Platform.X
        assert "Anthropic shipped Claude connectors" in post.body
        assert "solo founders' operational stack" in post.body
        assert "SFOS — 11 MIT agents" in post.body
        # github_url tail
        assert "github.com/alex-jb/solo-founder-os" in post.body

    def test_zh_xiaohongshu(self):
        p = Project(name="念念", tagline="你说一句话,世界长出来一点东西",
                     website_url="https://niannian.app")
        post = render_wave_borrow_post(
            p,
            wave_actor="Anthropic",
            wave_action="上周把 Claude 接进了 8 个创意工具",
            your_angle="我做了同样的事 — 给情绪型 user 的语音日记。",
            target="xiaohongshu",
        )
        assert post.platform == Platform.XIAOHONGSHU
        assert "Anthropic 上周把" in post.body
        assert "niannian.app" in post.body

    def test_falls_back_to_website_if_no_github(self):
        p = Project(name="X", tagline="t", website_url="https://x.com")
        post = render_wave_borrow_post(
            p, wave_actor="A", wave_action="did Y", your_angle="we do Z",
        )
        assert "https://x.com" in post.body

    def test_no_url_section_if_neither_set(self):
        p = Project(name="X", tagline="t")
        post = render_wave_borrow_post(
            p, wave_actor="A", wave_action="did Y", your_angle="we do Z",
        )
        # Should not have trailing url
        assert post.body.count("\n\n") == 2  # exactly: actor, angle, project


class TestLintDraft:
    def test_clean_draft_zero_issues(self):
        text = "We built a thing. It's small. Try it: https://x.com"
        assert lint_draft(text) == []

    def test_corporate_opener_flagged(self):
        text = "We're excited to announce our new product."
        issues = lint_draft(text)
        assert any("corporate launch opener" in i["issue"] for i in issues)
        assert any(i["severity"] == "error" for i in issues)

    def test_triple_exclamation_flagged(self):
        text = "This is amazing!!!"
        issues = lint_draft(text)
        assert any("triple exclamation" in i["issue"] for i in issues)
        assert issues[0]["severity"] == "error"

    def test_cringe_vocab_default_normal(self):
        text = "We leverage our robust platform to unlock seamless workflows."
        issues = lint_draft(text)
        # 'leverage', 'robust', 'unlock', 'seamless' all in vocab list
        flagged_words = {i["issue"] for i in issues}
        assert any("leverage" in i for i in flagged_words)
        assert any("robust" in i for i in flagged_words)
        assert any("unlock" in i for i in flagged_words)
        assert any("seamless" in i for i in flagged_words)

    def test_loose_skips_vocab_warns(self):
        text = "We leverage our robust platform."
        # Loose only catches errors (no errors here), so 0 issues
        assert lint_draft(text, strictness="loose") == []

    def test_emoji_wall_flagged(self):
        text = "🚀 🔥 ✨ 💯 🎉 launched!"
        issues = lint_draft(text)
        assert any("emoji wall" in i["issue"] for i in issues)

    def test_emoji_under_threshold_ok(self):
        text = "Drop a 👀 below or DM me 🙏"
        issues = lint_draft(text)
        assert not any("emoji wall" in i["issue"] for i in issues)

    def test_all_caps_warning(self):
        text = "BUY NOW LIMITED TIME ONLY"
        issues = lint_draft(text)
        assert any("majority-caps" in i["issue"] for i in issues)

    def test_line_no_reported(self):
        text = "Normal line\nWe're excited to announce something\nAnother normal"
        issues = lint_draft(text)
        opener_issues = [i for i in issues if "corporate launch opener" in i["issue"]]
        assert opener_issues
        assert opener_issues[0]["line_no"] == 2

    def test_chinese_text_passes_vocab_filter(self):
        # Chinese drafts should pass the EN-vocab linter unscathed
        text = "你说一句话,世界长出来一点东西。"
        assert lint_draft(text) == []


class TestCasualHumanizer:
    def test_empty_passes_through(self):
        assert casual_humanizer_zh("") == ""
        assert casual_humanizer_zh("   ") == "   "

    def test_skips_structural_lines(self):
        text = "# 标题\n- 列表\n```code\nx\n```"
        assert casual_humanizer_zh(text, seed=1) == text

    def test_skips_formal_lines(self):
        text = "请访问 https://niannian.app 试一下。"
        assert casual_humanizer_zh(text, seed=1) == text

    def test_inserts_interjection_on_joyful_sentence(self):
        text = "昨天我试了一下,评论区炸了。"
        out = casual_humanizer_zh(text, seed=1)
        # "炸" triggers interjection injection
        assert any(ij in out for ij in ("哈哈", "哈哈哈"))

    def test_interjection_only_once_per_draft(self):
        text = "我试了一次,效果炸了。又试了一次,还是炸了。"
        out = casual_humanizer_zh(text, seed=42)
        # Count interjection occurrences — at most one
        # (count "哈哈哈" first, then "哈哈" minus 哈哈哈 to avoid double-count)
        joyful = out.count("哈哈哈") + (out.count("哈哈") - 2 * out.count("哈哈哈"))
        assert joyful <= 1

    def test_zero_aggressiveness_no_particle_changes(self):
        text = "我们做了一个工具。"
        out = casual_humanizer_zh(text, seed=1, aggressiveness=0.0,
                                   inject_interjection=False)
        assert out == text

    def test_deterministic_with_seed(self):
        text = "我做了一个东西。我觉得挺有意思的。我们想找用户试一下。"
        out1 = casual_humanizer_zh(text, seed=7)
        out2 = casual_humanizer_zh(text, seed=7)
        assert out1 == out2

    def test_preserves_line_breaks(self):
        text = "第一行。\n\n第二行。\n第三行。"
        out = casual_humanizer_zh(text, seed=3, aggressiveness=0.5)
        assert out.count("\n") == text.count("\n")

    def test_does_not_double_particle_already_ended(self):
        text = "我们做了这个嘛。"
        out = casual_humanizer_zh(text, seed=1, aggressiveness=1.0)
        # The existing 嘛 should NOT cause a second particle inserted
        assert out.count("嘛") == 1


# ────────────────────────────────────────────────────────────────────
# Meme-borrow (render_meme_borrow)
# ────────────────────────────────────────────────────────────────────


class TestMemeBorrowTemplates:
    """Catalog-level invariants for MEME_TEMPLATES."""

    def test_all_templates_have_en_and_zh(self):
        for key, meme in MEME_TEMPLATES.items():
            assert "en" in meme, f"{key} missing en"
            assert "zh" in meme, f"{key} missing zh"
            assert "required_slots" in meme, f"{key} missing required_slots"

    def test_required_slots_present_in_both_languages(self):
        """If a template requires `{persona}`, both en + zh must reference it."""
        for key, meme in MEME_TEMPLATES.items():
            for lang in ("en", "zh"):
                tmpl = meme[lang]
                for slot in meme["required_slots"]:
                    assert (
                        "{" + slot + "}" in tmpl
                    ), f"{key}.{lang} doesn't reference {{{slot}}}"

    def test_product_and_tagline_auto_referenced(self):
        """{product} and/or {tagline} should be in most templates."""
        with_product = sum(
            1 for meme in MEME_TEMPLATES.values()
            if "{product}" in meme["en"] or "{product}" in meme["zh"]
        )
        assert with_product >= 3  # most templates use the brand


class TestMemeBorrowRender:
    def _proj(self) -> Project:
        return Project(name="SFOS", tagline="run a one-person company on YOUR keys")

    def test_x_but_for_y_en(self):
        post = render_meme_borrow(
            self._proj(),
            template_key="x_but_for_y",
            slots={"known_thing": "LangGraph", "target_user": "solo founders"},
            target="twitter",
            language="en",
        )
        assert post.body == "SFOS — LangGraph but for solo founders."
        assert post.platform == Platform.X

    def test_x_but_for_y_zh(self):
        post = render_meme_borrow(
            self._proj(),
            template_key="x_but_for_y",
            slots={"known_thing": "LangGraph", "target_user": "一人公司"},
            target="xiaohongshu",
        )
        # Default language for xiaohongshu is zh
        assert "给 一人公司 的 LangGraph" in post.body
        assert post.platform == Platform.XIAOHONGSHU

    def test_pov_persona_inherits_tagline(self):
        post = render_meme_borrow(
            self._proj(),
            template_key="pov_persona",
            slots={
                "persona": "a solo founder",
                "trigger_moment": "your 11 agents just shipped retro",
            },
            target="twitter",
            language="en",
        )
        # auto-filled tagline lands in body
        assert "run a one-person company on YOUR keys" in post.body
        assert "POV: you're a solo founder" in post.body

    def test_day_n_building(self):
        post = render_meme_borrow(
            self._proj(),
            template_key="day_n_building",
            slots={"day_n": 14, "today_in_one_line": "L4 evolver shipped its first PR"},
            target="twitter",
            language="en",
        )
        assert "Day 14 of building SFOS" in post.body
        assert "L4 evolver" in post.body

    def test_explained_in_n(self):
        post = render_meme_borrow(
            self._proj(),
            template_key="explained_in_n",
            slots={
                "n": 3,
                "beat_1": "pip install per agent",
                "beat_2": "cron runs Sunday 8am",
                "beat_3": "you approve PRs",
            },
            target="twitter",
            language="en",
        )
        assert "1. pip install per agent" in post.body
        assert "3. you approve PRs" in post.body

    def test_stop_use_zh(self):
        post = render_meme_borrow(
            self._proj(),
            template_key="stop_use",
            slots={"popular_action": "把 key 给 SaaS"},
            target="xiaohongshu",
        )
        assert post.body.startswith("别再 把 key 给 SaaS 了。")
        assert "SFOS" in post.body

    def test_custom_template(self):
        post = render_meme_borrow(
            self._proj(),
            custom_template="{product} > {competitor}. End of thread.",
            slots={"competitor": "Cofounder 2"},
            target="twitter",
            language="en",
        )
        assert post.body == "SFOS > Cofounder 2. End of thread."

    def test_rejects_both_template_key_and_custom(self):
        with pytest.raises(ValueError, match="exactly one"):
            render_meme_borrow(
                self._proj(),
                template_key="x_but_for_y",
                custom_template="hi {product}",
                slots={"known_thing": "X", "target_user": "Y"},
            )

    def test_rejects_neither_template_key_nor_custom(self):
        with pytest.raises(ValueError, match="exactly one"):
            render_meme_borrow(self._proj(), slots={})

    def test_rejects_unknown_template_key(self):
        with pytest.raises(ValueError, match="Unknown template_key"):
            render_meme_borrow(
                self._proj(),
                template_key="not_a_real_template",
                slots={},
            )

    def test_rejects_missing_required_slot(self):
        with pytest.raises(ValueError, match="missing required slot"):
            render_meme_borrow(
                self._proj(),
                template_key="x_but_for_y",
                slots={"known_thing": "LangGraph"},  # missing target_user
            )

    def test_custom_template_missing_slot_raises(self):
        with pytest.raises(ValueError, match="not provided"):
            render_meme_borrow(
                self._proj(),
                custom_template="{product} for {audience}.",
                slots={},  # missing audience
            )

    def test_platform_routing(self):
        proj = self._proj()
        for target, expected in [
            ("twitter", Platform.X),
            ("xiaohongshu", Platform.XIAOHONGSHU),
            ("showhn", Platform.HACKER_NEWS),
            ("linkedin", Platform.LINKEDIN),
            ("reddit", Platform.REDDIT),
        ]:
            post = render_meme_borrow(
                proj,
                template_key="x_but_for_y",
                slots={"known_thing": "X", "target_user": "Y"},
                target=target,
                language="en",
            )
            assert post.platform == expected
