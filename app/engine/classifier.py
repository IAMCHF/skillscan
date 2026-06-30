"""
技能分类检测引擎 — 基于多维度加权关键词评分，7 类判定（无需 LLM）
"""
from __future__ import annotations
from dataclasses import dataclass, field

CATEGORY_DISPLAY: dict[str, str] = {
    "aiAgent": "AI 智能", "itOpsSecurity": "IT 运维/安全",
    "development": "开发工具", "dataAnalysis": "数据分析",
    "contentCreation": "内容创作", "officeEfficiency": "办公效率",
    "others": "其他",
}

@dataclass
class ClassificationResult:
    detected_category: str = "others"
    confidence: float = 0.0
    category_scores: dict[str, float] = field(default_factory=dict)
    detection_method: str = "default"
    evidence: list[str] = field(default_factory=list)

SLUG_KEYWORDS: dict[str, list[str]] = {
    "aiAgent": ["agent", "ai-agent", "agentic", "autonomy", "memory", "orchestrat", "swarm", "agent-team", "llm", "gpt", "claude", "rag", "prompt-engin", "agent-factory", "neural-memory"],
    "itOpsSecurity": ["security", "vulnerab", "firewall", "cyber", "threat", "audit", "compliance", "siem", "ops", "devops", "k8s", "kubernetes", "docker", "deploy", "monitor", "terraform", "ansible", "osint"],
    "development": ["code", "coding", "program", "develop", "python", "javascript", "typescript", "java", "golang", "rust", "react", "vue", "api", "database", "sql", "git", "testing", "framework", "cli", "code-review", "refactor", "sdk"],
    "dataAnalysis": ["data-analy", "analytics", "statistic", "machine-learning", "visualization", "chart", "dashboard", "etl", "pipeline", "excel", "csv", "report", "predict", "forecast", "bioinformatic", "spreadsheet"],
    "contentCreation": ["content", "creat", "writer", "writing", "blog", "article", "novel", "document", "ppt", "presentation", "slide", "design", "graphic", "image", "video", "seo", "copywriting", "social-media", "translate", "logo"],
    "officeEfficiency": ["productivity", "workflow", "automat", "efficiency", "task", "todo", "calendar", "planner", "office", "word", "wps", "email", "note", "meeting", "knowledge", "project-manag", "prd", "format", "convert", "organiz", "file-manag"],
}

def classify_skill(slug: str = "", name: str = "", description: str = "", skill_md_content: str = "", file_extensions: list[str] | None = None, original_category: str = "") -> ClassificationResult:
    scores = {cat: 0.0 for cat in CATEGORY_DISPLAY}
    evidence = []
    slug_text = f"{slug} {name}".lower()
    desc_text = description.lower()
    full_text = f"{desc_text}\n{skill_md_content}".lower()

    for cat, keywords in SLUG_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in slug_text)
        if hits > 0:
            scores[cat] += min(hits * 0.6, 3.0)
            if hits >= 2:
                evidence.append(f"Slug 命中 {cat} 关键词 ({hits} 个)")

    for cat, keywords in SLUG_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in full_text)
        if hits > 2:
            scores[cat] += min(hits * 0.2, 1.5)
            evidence.append(f"全文命中 {cat} 关键词 ({hits} 个)")

    if file_extensions:
        py_count = sum(1 for e in file_extensions for x in [e.lower()] if x in (".py", "py"))
        if py_count >= 3:
            scores["development"] += 0.5
            scores["dataAnalysis"] += 0.3

    if original_category:
        mapping = {"aiintelligence": "aiAgent", "securitycompliance": "itOpsSecurity", "devtools": "development", "dataanalysis": "dataAnalysis", "contentcreation": "contentCreation", "productivity": "officeEfficiency", "communication": "officeEfficiency"}
        mapped = mapping.get(original_category.lower().replace("-", "").replace("_", ""), "")
        if mapped in scores:
            scores[mapped] += 0.3

    max_cat = max(scores, key=scores.get)
    max_score = scores[max_cat]
    sorted_v = sorted(scores.values(), reverse=True)
    confidence = min(max_score / 3.0 + (sorted_v[0] - sorted_v[1]) * 0.1 if len(sorted_v) >= 2 and sorted_v[0] > 0 else 0.0, 1.0)
    if max_score < 0.8:
        max_cat = "others"
        confidence = 0.6

    return ClassificationResult(
        detected_category=max_cat, confidence=round(confidence, 2),
        category_scores={k: round(v, 2) for k, v in scores.items()},
        detection_method="多维度关键词分析" if evidence else "default",
        evidence=evidence or ["无明确分类信号"],
    )
