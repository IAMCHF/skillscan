"""
15 条红牌规则定义 — Skill-Vetter Protocol Phase 3 安全审查核心

每条规则包含:
- rule_id: R1-R15
- name: 规则名称（中文）
- description: 规则描述
- patterns: 正则表达式列表
- severity: 严重级别 (固定 EXTREME，命中即淘汰)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RedFlagRule:
    rule_id: str
    name: str
    description: str
    patterns: list[str]     # regex patterns
    category: str           # 所属类别
    severity: str = "EXTREME"


# ─── 完整 15 条红牌规则 ──────────────────────────────────

RED_FLAG_RULES: list[RedFlagRule] = [
    # ── 网络请求 (Network Requests) ──
    RedFlagRule(
        rule_id="R1",
        name="curl/wget 外部请求",
        description="检测到 curl 或 wget 命令向外部 URL 发起请求",
        patterns=[
            r'curl\s+https?://(?!localhost|127\.0\.0\.1|192\.168\.)',
            r'wget\s+https?://(?!localhost|127\.0\.0\.1|192\.168\.)',
            r'Invoke-WebRequest\s+https?://(?!localhost|127\.0\.0\.1|192\.168\.)',
            r'Invoke-RestMethod\s+https?://(?!localhost|127\.0\.0\.1|192\.168\.)',
        ],
        category="网络请求",
    ),
    RedFlagRule(
        rule_id="R2",
        name="向外部发送数据",
        description="检测到 HTTP POST/PUT/PATCH 向非白名单 URL 发送数据",
        patterns=[
            r'requests\.(post|put|patch)\s*\(',
            r'httpx\.(post|put|patch)\s*\(',
            r'fetch\s*\(\s*["\']https?://(?!localhost|127\.0\.0\.1|192\.168\.)',
            r'aiohttp\.ClientSession.*\.(post|put|patch)\s*\(',
            r'urllib\.request\.urlopen\s*\(\s*.*Request\s*\(',
            r'curl\s+.*-(?:d|F|--data|--form)',
        ],
        category="网络请求",
    ),
    RedFlagRule(
        rule_id="R10",
        name="IP 直连请求",
        description="通过 IP 地址发起 HTTP 请求（内网 192.168.* 除外）",
        patterns=[
            r'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
        ],
        category="网络请求",
    ),

    # ── 凭据安全 (Credential Security) ──
    RedFlagRule(
        rule_id="R3",
        name="硬编码凭据/Token",
        description="检测到硬编码或环境变量读取 API Key/Token/Secret",
        patterns=[
            r'(?:api[_-]?key|api[_-]?secret|access[_-]?token|auth[_-]?token|bearer[_-]?token)\s*[=:]\s*["\'][A-Za-z0-9_\-]{8,}',
            r'(?:os\.getenv|environ\.get|os\.environ)\s*\(\s*["\']\w*(?:key|token|secret|password|credential)',
            r'(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|GITHUB_TOKEN|DOCKER_PASSWORD)\s*=\s*["\']',
            r'process\.env\.\w*(?:KEY|TOKEN|SECRET|PASSWORD)',
            r'(?:password|passwd|pwd)\s*[=:]\s*["\'][^\s]{3,}["\']\s*$',
        ],
        category="凭据安全",
    ),
    RedFlagRule(
        rule_id="R14",
        name="凭证文件触碰",
        description="检测到读取 .env、credentials.json、token、secrets 等凭证文件",
        patterns=[
            r'\.env\b(?!\.example|\.sample|\.template)',
            r'credentials\.json',
            r'\b(?:secrets?|tokens?)\.(?:json|yaml|yml|toml)\b',
            r'(?:open|read)\s*\(\s*["\'].*(?:\.env|credentials|secret|token).*["\']',
        ],
        category="凭据安全",
    ),

    # ── 文件系统安全 (Filesystem Security) ──
    RedFlagRule(
        rule_id="R4",
        name="读取敏感目录",
        description="检测到访问 ~/.ssh、~/.aws、~/.config 等敏感目录",
        patterns=[
            r'~/\.ssh',
            r'~/\.aws',
            r'~/\.config',
            r'(?:/root/|/etc/passwd|/etc/shadow)',
            r'C:\\Users\\.*\\\.ssh',
            r'%USERPROFILE%\\\.ssh',
            r'%USERPROFILE%\\\.aws',
        ],
        category="文件系统安全",
    ),
    RedFlagRule(
        rule_id="R5",
        name="访问隐私文件",
        description="检测到读取 MEMORY.md、USER.md、SOUL.md、IDENTITY.md 等隐私文件",
        patterns=[
            r'\b(?:MEMORY|USER|SOUL|IDENTITY)\.md\b',
            r'(?:open|read|cat)\s*\(\s*["\'].*(?:MEMORY|USER|SOUL|IDENTITY)',
            r'path.*(?:MEMORY|USER|SOUL|IDENTITY)\.md',
        ],
        category="文件系统安全",
    ),
    RedFlagRule(
        rule_id="R8",
        name="修改系统文件",
        description="检测到写入或修改系统目录中的文件",
        patterns=[
            r'(?:/etc/|C:\\Windows\\|/System/|/Library/)',
            r'chmod\s+[0-7]{3,4}',
            r'(?:chown|chgrp)\s+',
            r'write.*(?:/etc/|C:\\Windows\\)',
            r'Set-Content.*(?:C:\\Windows\\|/etc/)',
        ],
        category="文件系统安全",
    ),

    # ── 代码执行 (Code Execution) ──
    RedFlagRule(
        rule_id="R6",
        name="base64 解码",
        description="检测到使用 base64 解码（可能隐藏恶意代码）",
        patterns=[
            r'base64\.(?:b64|standard_b64|urlsafe_b64)decode',
            r'atob\s*\(',
            r'from\s+base64\s+import\s+.*decode',
            r'base64\s+-d\b',
            r'\[System\.Convert\]::FromBase64String',
        ],
        category="代码执行",
    ),
    RedFlagRule(
        rule_id="R7",
        name="eval/exec 动态执行",
        description="检测到 eval() 或 exec() 处理动态/外部输入",
        patterns=[
            r'\beval\s*\(',
            r'\bexec\s*\(',
            r'new\s+Function\s*\(',
            r'Function\s*\(\s*["\']return',
            r'__import__\s*\(\s*.*\)',
            r'importlib\.import_module\s*\(',
            r'compile\s*\(\s*.+["\']exec["\']',
            r'vm\.runIn',
        ],
        category="代码执行",
    ),
    RedFlagRule(
        rule_id="R9",
        name="动态命令执行",
        description="检测到 os.system/subprocess 执行动态拼接的命令",
        patterns=[
            r'os\.system\s*\(',
            r'subprocess\.(?:call|run|Popen|check_output|check_call)\s*\(',
            r'popen\s*\(',
            r'shell_exec\s*\(',
            r'exec\s*\(\s*["\'].*\$\(',
            r'passthru\s*\(',
            r'Start-Process\s+',
        ],
        category="代码执行",
    ),
    RedFlagRule(
        rule_id="R11",
        name="代码混淆",
        description="检测到压缩/编码/minified 的可疑代码",
        patterns=[
            r'(?:eval\(function|Function\s*\(\s*["\'].*,\s*["\'].*\)\s*\()',
            r'(?:unescape|String\.fromCharCode)\s*\(',
            r'__obfuscate|_0x[a-f0-9]{4,}',
            r'atob\s*\(\s*["\'].{50,}',
            r'gzinflate\s*\(',
            r'base64_decode\s*\(\s*["\'].{50,}',
        ],
        category="代码执行",
    ),

    # ── 系统安全 (System Security) ──
    RedFlagRule(
        rule_id="R12",
        name="提权请求",
        description="检测到 sudo、runas 或管理员权限提升请求",
        patterns=[
            r'\bsudo\b',
            r'\brunas\b',
            r'RunAsAdministrator',
            r'#Requires\s+-RunAsAdministrator',
            r'require.*root',
            r'os\.setuid\s*\(',
            r'pkexec\b',
            r'doas\b',
        ],
        category="系统安全",
    ),
    RedFlagRule(
        rule_id="R13",
        name="浏览器数据窃取",
        description="检测到访问浏览器 cookies、sessions、localStorage 等隐私数据",
        patterns=[
            r'(?:cookies|localStorage|sessionStorage)',
            r'chrome\.(?:cookies|storage)',
            r'document\.cookie',
            r'(?:Chrome|Firefox|Edge|Safari)\\.*\\User Data',
            r'sqlite3.*(?:Cookies|History|Login Data)',
        ],
        category="系统安全",
    ),

    # ── 二进制文件 ──
    RedFlagRule(
        rule_id="R15",
        name="包含二进制可执行文件",
        description="zip 包内包含 .exe、.dll、.so、.bin 等二进制文件",
        patterns=[],  # 文件级别检查，不在内容中匹配
        category="二进制文件",
    ),
]


# ─── 恶意命令模式（PERMISSION 分析辅助）──────────────────

DANGEROUS_COMMAND_PATTERNS: list[tuple[str, str]] = [
    (r'\brm\s+-rf\b', "rm -rf 危险删除"),
    (r'\bformat\s+', "磁盘格式化"),
    (r'\bdd\s+if=', "dd 磁盘操作"),
    (r'\bmkfs\.', "创建文件系统"),
    (r'\bfdisk\b', "分区操作"),
    (r'\bdrop\s+(?:table|database)\b', "SQL DROP 操作"),
    (r'shutdown\s+', "系统关机"),
    (r'\breboot\b', "系统重启"),
    (r'\bkillall\b', "killall 进程终止"),
    (r'\bpkill\b', "pkill 进程终止"),
    (r'(?:Stop-Process|Stop-Service)\s+-Force', "强制停止进程/服务"),
]


def get_rule_by_id(rule_id: str) -> RedFlagRule | None:
    for rule in RED_FLAG_RULES:
        if rule.rule_id == rule_id:
            return rule
    return None


def get_rules_by_category() -> dict[str, list[RedFlagRule]]:
    """按类别分组红牌规则"""
    categories: dict[str, list[RedFlagRule]] = {}
    for rule in RED_FLAG_RULES:
        categories.setdefault(rule.category, []).append(rule)
    return categories
