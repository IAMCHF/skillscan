# SkillScan

> 🛡️ 企业内网技能上线前静态安全审核服务

基于 **Skill-Vetter 协议**，对技能 zip 包进行**纯静态分析**（不执行代码），输出统一 HTML 格式的 **5 分制多维度审核报告**。

## 核心特性

- **纯静态分析** — 绝不执行技能中的任何代码，仅做文本内容安全扫描
- **15 条红牌规则** — 基于 Skill-Vetter Phase 3 安全审查协议
- **5 维度 5 分制评分** — 来源可信度 · 网络隔离度 · 权限最小化 · 代码安全性 · 离线兼容性
- **统一 HTML 报告** — 所有技能审核输出统一风格的 HTML 报告
- **独立后端服务** — FastAPI 技术栈，与其他后端完全解耦
- **批量扫描** — 支持单技能/批量技能上传审核

## 技术栈

| 组件 | 技术 |
|------|------|
| 应用框架 | FastAPI 0.115 |
| Web 服务器 | Uvicorn 0.34 |
| 报告渲染 | Jinja2 3.1 |
| 数据校验 | Pydantic 2.10 |
| 运行环境 | Python 3.12 |

## 快速启动

### 方式一：Docker

```bash
docker build -t skillscan .
docker run -p 8000:8000 skillscan
```

### 方式二：Python 直接运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动后访问：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- 审核维度说明: http://localhost:8000/dimensions

## API 接口

### POST /scan — 扫描单个技能

```bash
curl -X POST "http://localhost:8000/scan?slug=my-skill&name=MySkill&category=dev-tools&stars=100" \
  -F "file=@my-skill.zip"
```

返回完整的静态安全审查结果（JSON），包括：
- `source_check`: 来源可信度分析
- `red_flag_hits`: 红牌规则命中列表
- `permission_scope`: 权限范围分析
- `dimension_scores`: 五维度评分（1-5 分制）
- `risk_level`: LOW / MEDIUM / HIGH / EXTREME
- `verdict`: 通过 / 有条件通过 / 淘汰

### POST /scan/batch — 批量扫描

```bash
curl -X POST "http://localhost:8000/scan/batch" \
  -F "files=@skill1.zip" \
  -F "files=@skill2.zip" \
  -F "files=@skill3.zip"
```

返回批量结果 + HTML 报告链接。

### GET /report/{scan_id} — 查看 HTML 报告

```bash
curl "http://localhost:8000/report/20260630_120000_abc12345"
```

### GET /dimensions — 审核维度说明

返回五维度评分体系的详细说明和评分标准。

## 五维度评分体系

| 维度 | 图标 | 衡量标准 |
|------|------|---------|
| 来源可信度 | 🔐 | 作者信誉、星标数量、分类匹配度 |
| 网络隔离度 | 🌐 | 外部 API 调用、网络工具依赖 |
| 权限最小化 | 🔑 | 文件操作范围、命令执行、危险命令检测 |
| 代码安全性 | 🛡️ | 15 条红牌规则命中、可疑代码模式 |
| 离线兼容性 | 📡 | 内网离线环境可运行程度 |

每个维度采用 **5 分制**评分：
- **5 分** = 优秀，完全符合内网安全要求
- **4 分** = 良好，基本安全
- **3 分** = 可接受，建议复查
- **2 分** = 存在问题，需人工审批
- **1 分** = 不及格，存在严重风险

## 风险等级

| 等级 | 颜色 | 判定条件 | 处理方式 |
|------|------|---------|---------|
| 🟢 LOW | 绿色 | 无红牌，高评分 | 直接通过，正常安装 |
| 🟡 MEDIUM | 黄色 | 无红牌，网络/离线略有风险 | 通过但标记，定期复查 |
| 🔴 HIGH | 红色 | 无红牌但安全/权限低分 | 需人工审批 |
| ⛔ EXTREME | 紫色 | 命中红牌规则 | 立即淘汰，不可安装 |

## 15 条红牌规则 (R1-R15)

| 编号 | 规则 | 类别 |
|------|------|------|
| R1 | curl/wget 外部请求 | 网络请求 |
| R2 | HTTP 数据提交 | 网络请求 |
| R3 | 硬编码凭据/Token | 凭据安全 |
| R4 | 读取敏感目录 | 文件系统 |
| R5 | 访问隐私文件 | 文件系统 |
| R6 | base64 解码 | 代码执行 |
| R7 | eval/exec 执行 | 代码执行 |
| R8 | 修改系统文件 | 文件系统 |
| R9 | 动态命令执行 | 代码执行 |
| R10 | IP 直连请求 | 网络请求 |
| R11 | 代码混淆 | 代码执行 |
| R12 | 提权请求 | 系统安全 |
| R13 | 浏览器数据窃取 | 系统安全 |
| R14 | 凭证文件触碰 | 凭据安全 |
| R15 | 二进制可执行文件 | 二进制文件 |

## 项目结构

```
skillscan/
├── app/
│   ├── main.py                # FastAPI 入口
│   ├── report_renderer.py     # HTML 报告渲染器
│   ├── routers/
│   │   └── scan.py            # API 路由
│   ├── engine/
│   │   ├── scanner.py         # 主扫描编排器
│   │   ├── red_flags.py       # 15 条红牌规则
│   │   ├── source_check.py    # 来源可信度检查
│   │   └── permission.py      # 权限范围分析
│   ├── models/
│   │   └── schemas.py         # Pydantic 数据模型
│   ├── templates/
│   │   └── report.html        # Jinja2 报告模板
│   ├── utils/
│   │   └── zip_reader.py      # 安全 zip 读取器
│   └── static/                # 静态文件
├── requirements.txt
├── Dockerfile
└── README.md
```

## 安全原则

> **不信任任何来源的技能代码。安装前必须逐行审查。宁可误杀一千，不漏过一个。**

本模块严格执行以下安全原则：
1. **纯静态分析** — 不执行、不 eval、不 import 任何技能代码
2. **最小权限** — 仅读取 zip 内的文本文件内容进行模式匹配
3. **白名单模式** — 默认拒绝，仅放行已知安全模式
4. **深度防御** — 三层审查：来源检查 → 红牌规则 → 权限分析

## License

MIT
