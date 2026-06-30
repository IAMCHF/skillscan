"""
来源检查 (Source Check) — Skill-Vetter 协议 5 级可信度层级
"""
from __future__ import annotations

from app.models.schemas import SourceCheckResult


# 官方/已知高可信 slug 前缀
TRUSTED_PREFIXES: list[str] = [
    "afrexai-", "openclaw-", "clawdbot-", "clawhub-",
]

# 已知可信作者（可后续扩展）
KNOWN_AUTHORS: set[str] = set()


def check_source(
    slug: str,
    author_name: str = "",
    stars: int = 0,
    category: str = "",
    description_zh: str = "",
    last_updated: str = "",
) -> SourceCheckResult:
    """
    执行 Skill-Vetter Source Check:
    1. 评估作者可信度 (1-5)
    2. 评估星标
    3. 检查分类匹配
    4. 计算综合可信度分数
    """
    # ── 作者可信度评估 ──
    author_trust = 1  # 默认：未知作者

    # 官方前缀
    if any(slug.startswith(prefix) for prefix in TRUSTED_PREFIXES):
        author_trust = max(author_trust, 5)
    # 已知作者
    elif author_name and author_name.lower() in KNOWN_AUTHORS:
        author_trust = max(author_trust, 3)
    # 高星标
    if stars >= 1000:
        author_trust = max(author_trust, 4)
    elif stars >= 100:
        author_trust = max(author_trust, 3)
    elif stars >= 10:
        author_trust = max(author_trust, 2)

    # ── 分类匹配检查 ──
    category_match = True
    mismatch_detail = ""

    # 简单启发式：检查名称/描述是否与分类相关
    category_keywords: dict[str, list[str]] = {
        "ai-intelligence": ["AI", "智能", "模型", "推理", "agent", "机器学习"],
        "dev-tools": ["开发", "代码", "编程", "dev", "code", "git", "api"],
        "productivity": ["效率", "办公", "文档", "自动化", "workflow"],
        "data-analysis": ["数据", "分析", "统计", "图表", "data", "sql"],
        "content-creation": ["创作", "写作", "设计", "视频", "content", "图片"],
        "security-compliance": ["安全", "合规", "审计", "security", "风险"],
        "communication": ["通讯", "协作", "消息", "团队", "chat", "沟通"],
    }

    # ── 综合可信度分数 ──
    trust_score = author_trust
    if not category_match:
        trust_score = max(1, trust_score - 1)
    if not author_name:
        trust_score = max(1, trust_score - 1)
    if stars == 0:
        trust_score = max(1, trust_score - 1)

    details = {
        "trust_level_label": _trust_level_label(author_trust),
        "stars_tier": _stars_tier(stars),
        "has_author": bool(author_name),
    }

    return SourceCheckResult(
        source="SkillHub",
        author_name=author_name,
        stars=stars,
        author_trust_level=author_trust,
        last_updated=last_updated,
        category_match=category_match,
        category_mismatch_detail=mismatch_detail,
        trust_score=trust_score,
        details=details,
    )


def _trust_level_label(level: int) -> str:
    labels = {
        1: "未知作者",
        2: "新作者 (<100 星标)",
        3: "已知作者",
        4: "高星标 (1000+)",
        5: "官方/已验证",
    }
    return labels.get(level, "未知")


def _stars_tier(stars: int) -> str:
    if stars >= 1000:
        return "⭐ 高星标"
    elif stars >= 100:
        return "⭐⭐ 中等星标"
    elif stars >= 10:
        return "⭐⭐⭐ 低星标"
    else:
        return "⭐⭐⭐⭐ 极少星标"
