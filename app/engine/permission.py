"""
权限范围分析 (Permission Scope Analysis) — Skill-Vetter 协议
"""
from __future__ import annotations

import re

from app.models.schemas import PermissionScope
from app.engine.red_flags import DANGEROUS_COMMAND_PATTERNS


# 文件操作模式
FILE_READ_PATTERNS: list[tuple[str, str]] = [
    (r'open\s*\(\s*["\']([^"\']+)["\'].*[\'"]r[\'"]', "open() 读取"),
    (r'(?:read|cat)\s+["\']([^"\']+)["\']', "读取文件"),
    (r'pathlib\.Path\s*\(\s*["\']([^"\']+)["\']\).*read', "pathlib 读取"),
    (r'os\.path\.(?:exists|isfile|isdir)\s*\(', "文件系统检查"),
    (r'glob\.glob\s*\(', "glob 文件搜索"),
    (r'walk\s*\(\s*["\']([^"\']+)["\']', "目录遍历"),
    (r'Get-ChildItem\s+', "PowerShell 目录遍历"),
    (r'Get-Content\s+["\']([^"\']+)["\']', "PowerShell 读取"),
]

FILE_WRITE_PATTERNS: list[tuple[str, str]] = [
    (r'open\s*\(\s*["\']([^"\']+)["\'].*[\'"]w[\'"]', "open() 写入"),
    (r'open\s*\(\s*["\']([^"\']+)["\'].*[\'"]a[\'"]', "open() 追加"),
    (r'\.write\s*\(', ".write() 调用"),
    (r'\.dump\s*\(', ".dump() 序列化"),
    (r'shutil\.(?:copy|move)\s*\(', "文件复制/移动"),
    (r'os\.(?:remove|unlink|rmdir|removedirs)\s*\(', "文件/目录删除"),
    (r'Set-Content\s+["\']([^"\']+)["\']', "PowerShell 写入"),
    (r'Out-File\s+["\']([^"\']+)["\']', "PowerShell 输出"),
]

NETWORK_PATTERNS: list[tuple[str, str]] = [
    (r'requests\.(get|post|put|delete|patch)\s*\(', "HTTP 请求 (requests)"),
    (r'urllib\.request\.urlopen\s*\(', "HTTP 请求 (urllib)"),
    (r'httpx\.', "HTTP 请求 (httpx)"),
    (r'fetch\s*\(\s*["\']https?://', "HTTP fetch"),
    (r'Invoke-WebRequest\s+', "PowerShell HTTP"),
    (r'Invoke-RestMethod\s+', "PowerShell REST"),
    (r'websocket', "WebSocket 连接"),
    (r'socket\.(?:connect|create_connection)\s*\(', "Socket 连接"),
]


def analyze_permissions(skill_md_content: str, file_contents: list[tuple[str, str]]) -> PermissionScope:
    """
    分析技能的权限范围:
    - 文件读取范围
    - 文件写入范围
    - 命令执行检测
    - 网络需求评估
    - 危险命令检测
    """
    all_content = skill_md_content
    for path, content in file_contents:
        all_content += "\n" + content

    # ── 文件读取分析 ──
    file_reads: set[str] = set()
    for pattern, desc in FILE_READ_PATTERNS:
        for match in re.finditer(pattern, all_content, re.IGNORECASE):
            file_reads.add(desc)

    # ── 文件写入分析 ──
    file_writes: set[str] = set()
    for pattern, desc in FILE_WRITE_PATTERNS:
        for match in re.finditer(pattern, all_content, re.IGNORECASE):
            file_writes.add(desc)

    # ── 命令执行检测 ──
    commands: set[str] = set()
    cmd_patterns = [
        (r'os\.system\s*\(', "os.system()"),
        (r'subprocess\.(?:call|run|Popen|check_output)\s*\(', "subprocess 调用"),
        (r'shell_exec\s*\(', "shell_exec()"),
        (r'Start-Process\s+', "Start-Process"),
        (r'Invoke-Expression\s+', "Invoke-Expression"),
    ]
    for pattern, desc in cmd_patterns:
        if re.search(pattern, all_content, re.IGNORECASE):
            commands.add(desc)

    # ── 网络需求分析 ──
    network_requirement = "None"
    network_details: list[str] = []

    localhost_pattern = re.compile(
        r'(?:localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})', re.IGNORECASE
    )
    has_localhost = bool(localhost_pattern.search(all_content))

    for pattern, desc in NETWORK_PATTERNS:
        if re.search(pattern, all_content, re.IGNORECASE):
            # 检查是否是 localhost
            network_details.append(desc)

    if network_details:
        # 检查是否所有网络请求都指向 localhost/内网
        external_patterns: list[str] = []
        for pattern, desc in NETWORK_PATTERNS:
            matches = list(re.finditer(pattern, all_content, re.IGNORECASE))
            for match in matches:
                context = all_content[max(0, match.start()-50):match.end()+200]
                if not localhost_pattern.search(context):
                    if desc not in external_patterns:
                        external_patterns.append(desc)

        if external_patterns:
            network_requirement = "外部网络"
        elif has_localhost:
            network_requirement = "localhost 仅限"
            network_details = ["所有网络请求仅限 localhost/内网"]
        else:
            network_requirement = "可能存在"

    # ── 危险命令检测 ──
    dangerous_cmds: list[str] = []
    for pattern, desc in DANGEROUS_COMMAND_PATTERNS:
        if re.search(pattern, all_content, re.IGNORECASE):
            dangerous_cmds.append(desc)

    return PermissionScope(
        file_read_patterns=sorted(file_reads),
        file_write_patterns=sorted(file_writes),
        commands_detected=sorted(commands),
        network_requirement=network_requirement,
        network_detail="; ".join(network_details) if network_details else "",
        scope_matches_function=len(dangerous_cmds) == 0,
        scope_mismatch_detail="发现危险命令" if dangerous_cmds else "",
        has_dangerous_commands=len(dangerous_cmds) > 0,
        dangerous_commands=dangerous_cmds,
    )
