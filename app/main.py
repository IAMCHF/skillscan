"""
FastAPI 应用入口 — SkillScan 静态安全审核服务
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.routers.scan import router as scan_router

app = FastAPI(
    title="SkillScan",
    description="企业内网技能上线前静态安全审核服务。基于 Skill-Vetter 协议进行纯静态分析，输出统一 HTML 格式的 5 分制多维度审核报告。",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置（允许其他后端服务调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 注册路由
app.include_router(scan_router)


@app.on_event("startup")
async def startup_event():
    """服务启动时清理过期报告"""
    from app.report_renderer import cleanup_old_reports
    cleanup_old_reports()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
