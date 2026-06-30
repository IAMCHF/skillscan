"""
Pydantic 数据模型 — SkillScan 审核结果的所有数据结构
严格按照 Skill-Vetter 协议定义各审核维度的输出格式
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ─── 风险等级 ───────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

    @classmethod
    def display(cls, level: str) -> str:
        return {"LOW": "🟢 低风险", "MEDIUM": "🟡 中风险",
                "HIGH": "🔴 高风险", "EXTREME": "⛔ 极高风险"}.get(level, level)

    @classmethod
    def color(cls, level: str) -> str:
        return {"LOW": "#22c55e", "MEDIUM": "#eab308",
                "HIGH": "#ef4444", "EXTREME": "#7c3aed"}.get(level, "#6b7280")


class Verdict(str, Enum):
    PASS = "通过"
    CONDITIONAL = "有条件通过"
    REJECT = "淘汰"


# ─── 审核维度（5 个评分维度）─────────────────────────────

class AuditDimension(str, Enum):
    SOURCE_TRUST = "source_trust"       # 来源可信度
    NETWORK_ISOLATION = "network_isolation"  # 网络隔离度
    PERMISSION_MINIMALITY = "permission_minimality"  # 权限最小化
    CODE_SECURITY = "code_security"      # 代码安全性
    OFFLINE_COMPAT = "offline_compat"    # 离线兼容性


DIMENSION_DISPLAY = {
    "source_trust": "来源可信度",
    "network_isolation": "网络隔离度",
    "permission_minimality": "权限最小化",
    "code_security": "代码安全性",
    "offline_compat": "离线兼容性",
}

DIMENSION_ICONS = {
    "source_trust": "🔐",
    "network_isolation": "🌐",
    "permission_minimality": "🔑",
    "code_security": "🛡️",
    "offline_compat": "📡",
}


# ─── 请求模型 ───────────────────────────────────────────

class ScanRequest(BaseModel):
    """单技能扫描请求（上传 zip 文件）"""
    pass  # file handled via UploadFile in route


class BatchScanResponse(BaseModel):
    """批量扫描响应包装"""
    scan_id: str
    total_scanned: int
    passed: int
    conditional: int
    rejected: int
    results: list[SkillScanResult]
    report_html_path: str = ""


# ─── 来源检查结果 ────────────────────────────────────────

class SourceCheckResult(BaseModel):
    """Phase 3 Source Check 结果"""
    source: str = "SkillHub"
    author_name: str = ""
    stars: int = 0
    author_trust_level: int = Field(default=1, ge=1, le=5,
        description="1-未知作者 2-新作者(<100星) 3-已知作者 4-高星(1000+) 5-官方/已验证")
    last_updated: str = ""
    category_match: bool = True
    category_mismatch_detail: str = ""
    trust_score: int = Field(default=1, ge=1, le=5,
        description="综合可信度 1=不可信 5=完全可信")
    details: dict = Field(default_factory=dict)


# ─── 红牌规则命中 ────────────────────────────────────────

class RedFlagHit(BaseModel):
    """单条红牌规则命中记录"""
    rule_id: str          # R1-R15
    rule_name: str        # 规则名称
    description: str      # 规则描述
    file_path: str        # 命中文件路径
    matched_content: str  # 命中的代码片段（截取前 200 字）
    line_number: int = 0
    severity: str = "EXTREME"


# ─── 权限范围分析 ────────────────────────────────────────

class PermissionScope(BaseModel):
    """权限范围分析结果"""
    file_read_patterns: list[str] = Field(default_factory=list)
    file_write_patterns: list[str] = Field(default_factory=list)
    commands_detected: list[str] = Field(default_factory=list)
    network_requirement: str = "None"
    network_detail: str = ""
    scope_matches_function: bool = True
    scope_mismatch_detail: str = ""
    has_dangerous_commands: bool = False
    dangerous_commands: list[str] = Field(default_factory=list)


# ─── 五维度评分 ──────────────────────────────────────────

class DimensionScore(BaseModel):
    """单个维度的 5 分制评分"""
    dimension: str                          # AuditDimension value
    score: int = Field(default=3, ge=1, le=5)
    max_score: int = 5
    display_name: str = ""                  # 中文显示名
    icon: str = ""                          # emoji icon
    reason: str = ""                        # 评分理由
    findings: list[str] = Field(default_factory=list)  # 具体发现


# ─── 完整扫描结果 ────────────────────────────────────────

class SkillScanResult(BaseModel):
    """单个技能的完整静态分析结果"""
    slug: str
    name: str = ""
    category: str = ""
    description_zh: str = ""
    stars: int = 0

    # 三部分审查结果
    source_check: SourceCheckResult = Field(default_factory=SourceCheckResult)
    red_flag_hits: list[RedFlagHit] = Field(default_factory=list)
    permission_scope: PermissionScope = Field(default_factory=PermissionScope)

    # 综合评分
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    total_score: float = Field(default=0.0, ge=0.0, le=5.0,
        description="五维度加权平均分")

    # 最终判定
    risk_level: RiskLevel = RiskLevel.LOW
    verdict: Verdict = Verdict.PASS

    # 元信息
    files_scanned: int = 0
    scan_duration_ms: int = 0
    summary: str = ""


# ─── 报告 HTML 上下文模型 ────────────────────────────────

class ReportContext(BaseModel):
    """传递给 Jinja2 HTML 模板的完整上下文"""
    scan_id: str
    generated_at: str
    total: int
    results: list[SkillScanResult]

    # 统计聚合
    risk_distribution: dict = Field(default_factory=dict)
    dimension_averages: dict = Field(default_factory=dict)
    red_flag_summary: dict = Field(default_factory=dict)
    category_stats: list[dict] = Field(default_factory=list)

    # 淘汰清单
    rejected: list[SkillScanResult] = Field(default_factory=list)
    conditional: list[SkillScanResult] = Field(default_factory=list)
    passed: list[SkillScanResult] = Field(default_factory=list)
