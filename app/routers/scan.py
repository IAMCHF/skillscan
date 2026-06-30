"""
SkillScan API 路由 — 技能静态安全审查接口

端点:
- POST /scan          — 上传单个技能 zip，返回审核结果 JSON
- POST /scan/batch    — 上传多个技能 zip (ZIP of ZIPs)，返回批量结果 + HTML 报告
- GET  /report/{id}   — 获取已生成的 HTML 审核报告
- GET  /dimensions    — 获取审核维度说明
- GET  /health        — 健康检查
"""
from __future__ import annotations

import os
import uuid
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse

from app.engine.scanner import scan_single_skill, build_report_context
from app.models.schemas import BatchScanResponse, DIMENSION_DISPLAY, DIMENSION_ICONS
from app.report_renderer import render_html_report

router = APIRouter(prefix="", tags=["SkillScan"])

# 报告存储目录
REPORTS_DIR = os.path.join(tempfile.gettempdir(), "skillscan_reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


@router.post("/scan", summary="扫描单个技能")
async def scan_single_zip(
    file: UploadFile = File(..., description="技能 .zip 文件"),
    slug: Optional[str] = Query(None, description="技能 slug"),
    name: Optional[str] = Query(None, description="技能名称"),
    category: Optional[str] = Query(None, description="技能分类"),
    stars: Optional[int] = Query(None, description="星标数"),
    author: Optional[str] = Query(None, description="作者"),
    description_zh: Optional[str] = Query(None, description="中文描述"),
):
    """上传单个技能 zip，返回完整静态安全审查结果（JSON）"""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的技能包")

    # 保存上传文件到临时目录
    tmp_path = os.path.join(tempfile.gettempdir(), f"skillscan_{uuid.uuid4().hex}.zip")
    try:
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 构建元数据
        metadata = {
            "slug": slug or os.path.splitext(file.filename)[0],
            "name": name or "",
            "category": category or "",
            "stars": stars or 0,
            "owner_name": author or "",
            "description_zh": description_zh or "",
        }

        result = scan_single_skill(tmp_path, metadata)
        return result

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/scan/batch", summary="批量扫描多个技能")
async def scan_batch(
    files: list[UploadFile] = File(..., description="多个技能 .zip 文件"),
):
    """
    上传多个技能 zip 包，返回:
    - 每个技能的详细审查结果 (JSON)
    - 汇总 HTML 审核报告路径
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个技能 zip 文件")

    results = []
    tmp_dir = tempfile.mkdtemp(prefix="skillscan_batch_")

    try:
        for file in files:
            if not file.filename or not file.filename.endswith(".zip"):
                continue

            slug = os.path.splitext(file.filename)[0]
            tmp_path = os.path.join(tmp_dir, file.filename)

            with open(tmp_path, "wb") as f:
                content = await file.read()
                f.write(content)

            metadata = {"slug": slug}
            result = scan_single_skill(tmp_path, metadata)
            results.append(result)

        if not results:
            raise HTTPException(status_code=400, detail="未找到有效的 zip 文件")

        # 生成 HTML 报告
        scan_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        context = build_report_context(scan_id, results)
        report_html = render_html_report(context)

        # 保存报告
        report_path = os.path.join(REPORTS_DIR, f"report_{scan_id}.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_html)

        passed = sum(1 for r in results if r.verdict.value == "通过")
        conditional = sum(1 for r in results if r.verdict.value == "有条件通过")
        rejected = sum(1 for r in results if r.verdict.value == "淘汰")

        return BatchScanResponse(
            scan_id=scan_id,
            total_scanned=len(results),
            passed=passed,
            conditional=conditional,
            rejected=rejected,
            results=results,
            report_html_path=f"/report/{scan_id}",
        )

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/report/{scan_id}", summary="获取 HTML 审核报告")
async def get_report(scan_id: str):
    """根据 scan_id 返回对应的 HTML 审核报告"""
    report_path = os.path.join(REPORTS_DIR, f"report_{scan_id}.html")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="报告不存在或已过期")

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)


@router.get("/report/{scan_id}/download", summary="下载 HTML 审核报告")
async def download_report(scan_id: str):
    """下载 HTML 审核报告文件"""
    report_path = os.path.join(REPORTS_DIR, f"report_{scan_id}.html")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="报告不存在或已过期")

    return FileResponse(
        report_path,
        media_type="text/html",
        filename=f"skillscan_report_{scan_id}.html",
    )


@router.get("/dimensions", summary="审核维度说明")
async def get_dimensions():
    """返回 Skill-Vetter 五维度评分体系说明"""
    dimensions = []
    for dim_key, display_name in DIMENSION_DISPLAY.items():
        dimensions.append({
            "key": dim_key,
            "name": display_name,
            "icon": DIMENSION_ICONS.get(dim_key, ""),
            "description": _dimension_descriptions.get(dim_key, ""),
            "scale": {
                "1": _scale_labels.get(dim_key, {}).get(1, ""),
                "2": _scale_labels.get(dim_key, {}).get(2, ""),
                "3": _scale_labels.get(dim_key, {}).get(3, ""),
                "4": _scale_labels.get(dim_key, {}).get(4, ""),
                "5": _scale_labels.get(dim_key, {}).get(5, ""),
            },
        })
    return {"dimensions": dimensions}


@router.get("/health", summary="健康检查")
async def health_check():
    return {"status": "ok", "service": "SkillScan", "version": "1.0.0"}


# ─── 维度说明文本 ──────────────────────────────────────

_dimension_descriptions = {
    "source_trust": "评估技能来源的可信度：作者是否为官方/已知可信开发者、技能星标数量、分类是否匹配等。高分表示来源可靠。",
    "network_isolation": "评估技能代码中是否存在向外部网络发起请求的代码。高分表示不依赖外部 API，适合内网部署。",
    "permission_minimality": "评估技能权限范围是否最小化：文件读写操作范围、命令执行需求、是否包含危险命令。高分表示权限最小化设计。",
    "code_security": "评估代码静态安全性：是否命中 Skill-Vetter 15 条红牌规则（如 eval/exec、硬编码凭据、系统目录操作等）。高分表示代码安全。",
    "offline_compat": "评估技能在内网离线环境下能否正常工作：是否依赖浏览器工具、外部搜索引擎、云服务 API 等。高分表示完全离线兼容。",
}

_scale_labels = {
    "source_trust": {
        1: "完全未知来源，无星标，无作者信息",
        2: "新作者，极低星标，分类存疑",
        3: "已知作者或中等星标，分类基本匹配",
        4: "高星标仓库(1000+)，可信来源",
        5: "官方/已验证技能，高度可信",
    },
    "network_isolation": {
        1: "大量外部 API 调用，包含网络爬虫/浏览器工具",
        2: "多处外部网络请求，可能向外部发送数据",
        3: "有外部 URL 但无网络工具依赖",
        4: "仅访问安全域名/文档站点",
        5: "零网络请求，完全内网兼容",
    },
    "permission_minimality": {
        1: "检测到危险命令，权限严重超出声明范围",
        2: "文件写入+命令执行+权限超出功能范围",
        3: "有文件操作和命令执行，但基本匹配功能",
        4: "仅文件操作，无命令执行",
        5: "纯文档/知识技能，无代码执行，无文件操作",
    },
    "code_security": {
        1: "命中红牌规则，包含安全风险代码",
        2: "多处可疑模式，需要详细人工审查",
        3: "少量可疑代码模式，建议复查",
        4: "代码基本安全，未发现明显问题",
        5: "代码完全干净，无任何安全风险",
    },
    "offline_compat": {
        1: "完全依赖互联网服务，内网不可用",
        2: "依赖外部 API 和网络工具",
        3: "引用外部 URL 但不强依赖",
        4: "基本可离线运行，少量外部引用为文档",
        5: "完全离线兼容，内网可直接部署",
    },
}
