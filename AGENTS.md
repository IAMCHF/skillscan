# AGENTS.md

## 项目

SkillScan TRACE — 企业内网 AI 技能静态安全审核服务（FastAPI），纯静态分析，不执行技能代码。

## 命令

- `make dev` / `make test` / `make prod`：按 `.env.{dev,test,prod}` 启动
- `pip install -r requirements.txt`；API 文档 `/docs`（本地静态 Swagger）

## 结构

- `app/routers/scan.py`：`/scan`、`/fix-skill`、`/health`
- `app/engine/`：编排、提示词、LLM 客户端、格式修复、分类
- `app/models/schemas.py`：数据模型与 TRACE 指标
- `app/templates/report.html`、`app/report_renderer.py`：HTML 报告

## 约定

- 不执行、import 或 eval 技能代码；服务端不保留临时文件；路径用相对路径
- 改数据模型时同步 `schemas.py`、`prompts.py`、报告模板与文档
- 每次提交只包含本次需求相关改动，不夹带用户手动修改或之前已有的改动
- 提交信息清晰易读，说明改动动机；每次修改完成后自动提交
- 删除、合并、同步等破坏性操作由用户手动执行，或每次单独请求授权

## 工作流程

先全面分析并规划；不清楚的地方先与用户确认，给出完整总体规划，经用户确认后再执行。
