"""
FastAPI 应用入口 — SkillScan TRACE 审核服务

在导入任何引擎模块前加载 .env 文件，确保配置优先就绪。
"""
# 环境变量加载器 — 最先导入（导入时自动读取 .env.{dev|test|prod}）
from app import env_loader  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.scan import router as scan_router
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from pathlib import Path

app = FastAPI(
    title="SkillScan TRACE",
    description="企业内网 AI 技能静态安全审核服务。基于 LLM + SkillHub TRACE 五维度评测体系，纯静态分析不执行代码。",
    version="2.0.0",
    docs_url=None,  # 禁用默认的 /docs 路由
    redoc_url=None,  # 禁用默认的 /redoc 路由
)

# CORS 配置（内网服务，鉴权由网关层统一承担）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录，用于本地托管 Swagger UI 资源
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """自定义 Swagger UI 路由，使用本地静态资源。"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
        swagger_favicon_url="/static/favicon.png",
    )


# 注册路由
app.include_router(scan_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
