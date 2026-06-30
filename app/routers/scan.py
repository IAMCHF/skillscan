"""
SkillScan API — 单技能 TRACE 审核接口

POST /scan  — 上传技能 zip，返回 TRACE 结构化 JSON（与 HTML 模板字段对应）
GET  /health — 健康检查
"""
from __future__ import annotations
import os, uuid, tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import Optional

from app.engine.scanner import scan_single_skill

router = APIRouter(prefix="", tags=["SkillScan"])


@router.post("/scan", summary="TRACE 审核单个技能")
async def scan_skill(
    file: UploadFile = File(..., description="技能 .zip 文件"),
    slug: Optional[str] = Query(None, description="技能 slug"),
    name: Optional[str] = Query(None, description="技能名称"),
    category: Optional[str] = Query(None, description="原始分类"),
    stars: Optional[int] = Query(None, description="星标数"),
    author: Optional[str] = Query(None, description="作者"),
    description_zh: Optional[str] = Query(None, description="中文描述"),
    version: Optional[str] = Query(None, description="版本号"),
    downloads: Optional[int] = Query(None, description="下载量"),
    updated_at: Optional[str] = Query(None, description="更新时间"),
):
    """
    上传单个技能 zip，LLM 执行 TRACE 五维度静态分析，返回结构化 JSON。

    返回字段与 HTML 报告模板一一对应，前端可直接绑定展示：
    - trace_scores: 五维度评分 (T/R/A/C/E)
    - security_level: 安全 / 存在潜在风险 / 不安全
    - security_findings: 安全发现列表
    - verdict: 通过 / 有条件通过 / 淘汰
    - overall_score: 综合评分 (0-5)
    - detected_category: 自动分类
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的技能包")

    tmp_path = os.path.join(tempfile.gettempdir(), f"skillscan_{uuid.uuid4().hex}.zip")
    try:
        with open(tmp_path, "wb") as f:
            f.write(await file.read())

        metadata = {
            "slug": slug or os.path.splitext(file.filename)[0],
            "name": name or "", "category": category or "",
            "stars": stars or 0, "owner_name": author or "",
            "description_zh": description_zh or "",
            "version": version or "", "downloads": downloads or 0,
            "updated_at": updated_at or "",
        }
        return await scan_single_skill(tmp_path, metadata)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "SkillScan TRACE", "version": "2.0.0"}
