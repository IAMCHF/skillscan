# SkillScan TRACE

> 🛡️ 企业内网 AI 技能上线前静态安全审核服务

基于 **LLM + SkillHub TRACE 评测体系**，对技能 zip 包进行**纯静态分析**（不执行代码），输出 SkillHub 风格的 **TRACE 五维度审核报告**。

## 核心特性

- **LLM 驱动分析** — 通过系统提示词让大模型作为资深安全审查官，阅读理解代码语义，而非正则盲扫
- **TRACE 五维度评测** — 对齐 SkillHub 官方 TRACE 评测体系 (T/R/A/C/E)，每维度 4 个子指标，共 20 项，0-5 分制
- **纯静态分析** — 绝不执行技能中的任何代码，仅提取文本文件发送给 LLM 进行分析
- **SkillHub 风格报告** — 白底卡片 + Tab 栏 + 彩色 TRACE 卡片 + 子指标评分条的 HTML 审核报告
- **独立后端服务** — FastAPI 技术栈，与其他后端完全解耦
- **格式自动修复** — 检测 SKILL.md 文件名大小写、YAML frontmatter 闭合、缺失字段并自动修正（无需 LLM）
- **自动分类检测** — 关键词引擎将技能归入 7 个类别之一（无需 LLM）

## 技术栈

| 组件 | 技术 |
|------|------|
| 应用框架 | FastAPI 0.115 |
| Web 服务器 | Uvicorn 0.34 |
| LLM 客户端 | httpx (OpenAI 兼容 API) |
| 报告渲染 | Jinja2 3.1 |
| 数据校验 | Pydantic 2.10 |
| 运行环境 | Python 3.12 |

## 快速启动

### 1. 设置 LLM API 环境变量

```bash
# 主审查模型（质量优先）
export LLM_API_URL="https://api.openai.com/v1/chat/completions"
export LLM_API_KEY="sk-xxx"
export LLM_MODEL="gpt-4o"
export LLM_TIMEOUT="120"
export LLM_MAX_TOKENS="8192"
```

支持任意 OpenAI 兼容 API（如 DeepSeek、通义千问、本地 vLLM 等），只需修改 `LLM_API_URL` 和 `LLM_MODEL`。

### 2. 启动服务

**方式一：Docker**

```bash
docker build -t skillscan .
docker run -p 8000:8000 -e LLM_API_KEY="sk-xxx" skillscan
```

**方式二：Python 直接运行**

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. 访问

- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## API 接口

### POST /scan — TRACE 审核单个技能

```bash
curl -X POST "http://localhost:8000/scan?slug=my-skill&name=MySkill&category=dev-tools&stars=100" \
  -F "file=@my-skill.zip"
```

**返回结构化 JSON（与 HTML 报告模板字段一一对应）：**

```json
{
  "slug": "my-skill",
  "name": "MySkill",
  "description_zh": "技能中文描述",
  "stars": 100,
  "author": "作者名",
  "version": "1.0.0",
  "downloads": 5000,
  "updated_at": "2026-06-30",

  "detected_category": "development",
  "detected_category_display": "开发工具",
  "detected_category_confidence": 0.85,
  "classification": {
    "category_scores": { "aiAgent": 0.0, "development": 2.8 },
    "evidence": ["Slug 命中 development 关键词 (4 个)"]
  },

  "trace_scores": [
    {
      "dimension": "trust",
      "letter": "T",
      "display_name": "可信任度",
      "score": 4.5,
      "sub_indicators": [
        { "key": "security", "name": "安全检测", "score": 5, "comment": "纯文档驱动，无外部依赖" },
        { "key": "minimal_permission", "name": "最小权限", "score": 5, "comment": "仅读取 SKILL.md" },
        { "key": "sensitive_data", "name": "敏感信息保护", "score": 4, "comment": "未发现硬编码凭据" },
        { "key": "availability", "name": "国内可用性", "score": 4, "comment": "引用 GitHub，但非强依赖" }
      ],
      "findings_summary": "该技能不涉及网络请求，遵循最小权限原则..."
    }
  ],

  "overall_score": 4.2,
  "security_level": "安全",
  "security_findings": [
    {
      "severity": "info",
      "category": "网络请求",
      "description": "SKILL.md 引用外部文档 URL，属于文档引用",
      "file_path": "SKILL.md",
      "suggestion": "无安全风险"
    }
  ],
  "security_labs": [
    { "name": "科恩实验室", "result": "深度漏洞扫描完成", "status": "pass" },
    { "name": "云鼎实验室", "result": "AI 模型安全评估完成", "status": "pass" }
  ],

  "verdict": "通过",
  "verdict_reason": "综合 TRACE 评分较高，未发现安全风险",

  "fix_report": {
    "zip_fixed": true,
    "actions": ["文件名修正: skill.md → SKILL.md", "YAML frontmatter 缺少结尾 ---，已自动插入"],
    "errors": [],
    "extracted_name": "MySkill",
    "extracted_desc": "技能描述..."
  },

  "files_scanned": 12,
  "total_lines": 450,
  "scan_duration_ms": 3200
}
```

## 扫描流水线

```
zip 上传
├── Step 0: 🔧 SKILL.md 格式检测与自动修复（无需 LLM）
│           - 文件名大小写修正: skill.md → SKILL.md
│           - YAML frontmatter 闭合修复: 缺少 --- 自动补全
│           - 缺失字段补全: name/description 从上下文推断
├── Step 1: 📦 安全读取 zip（仅提取文本，跳过二进制/超大文件）
├── Step 2: 🏷️ 关键词分类检测（Slug+描述+全文+扩展名，无需 LLM）
├── Step 3: ✍️ 构建 LLM 审查提示词
├── Step 4: 🧠 LLM 执行 TRACE 五维度语义分析
├── Step 5: 📋 解析 LLM 结构化 JSON 输出
└── Step 6: 📊 组装完整 SkillScanResult
```

## TRACE 评测体系

TRACE 是 SkillHub 首发的 AI Skill 质量评测标准，从五个维度评估：

| 字母 | 维度 | 子指标 | 颜色 |
|------|------|--------|------|
| **T** | Trust（可信任度） | 安全检测 · 最小权限 · 敏感信息保护 · 国内可用性 | 🔵 蓝色 |
| **R** | Reliability（可靠性） | 稳定运行 · 一致结果 · 边界输入处理 · 异常反馈机制 | 🟢 绿色 |
| **A** | Adaptability（适用性） | 场景匹配度 · 触发条件清晰度 · 能力边界界定 · 输入输出规范性 | 🟡 橙色 |
| **C** | Convention（规范性） | 渐进式披露 · 文档结构清晰度 · 限制说明完整性 · 示例充分性 | 🟣 紫色 |
| **E** | Effectiveness（有效性） | 结果正确性 · 输出完整性 · 可直接使用性 · 减少返工率 | 🔴 红色 |

每个维度 4 个子指标，每项 0-5 分。维度得分 = 4 个子指标平均。综合得分 = 5 个维度平均。

### 评分标准

| 分数 | 等级 | 含义 |
|------|------|------|
| 4.5 - 5.0 | ⭐ 优秀 | 可直接上线 |
| 3.5 - 4.4 | ⭐ 良好 | 建议上线，关注低分维度 |
| 2.5 - 3.4 | ⭐ 一般 | 需改进后上线 |
| 0.0 - 2.4 | ⭐ 需改进 | 不建议上线 |

### 分类体系（7 类）

| 分类键 | 中文名 | 涵盖领域 |
|--------|--------|---------|
| `aiAgent` | AI 智能 | AI Agent、记忆系统、自主决策、推理优化 |
| `itOpsSecurity` | IT 运维/安全 | 基础设施、安全审计、漏洞扫描、日志监控 |
| `development` | 开发工具 | 编程助手、代码审查、CI/CD、测试 |
| `dataAnalysis` | 数据分析 | 数据处理、可视化、机器学习、BI 报表 |
| `contentCreation` | 内容创作 | 文档写作、PPT、设计、视频/图片生成 |
| `officeEfficiency` | 办公效率 | 任务管理、自动化流程、日程安排 |
| `others` | 其他 | 无法归入以上分类的技能 |

## 格式修复详解

SKILL.md 格式问题是企业内网平台上线的常见阻碍。SkillScan 在 TRACE 评测前自动执行以下检测与修复：

| 检测项 | 问题示例 | 自动修复 |
|--------|---------|---------|
| 文件名大小写 | 根目录 `skill.md` / `Skill.md` | → `SKILL.md` |
| YAML 缺少闭合 | 只有开头 `---`，缺少结尾 `---` | 自动推断结尾位置插入 `---` |
| 缺少 name 字段 | frontmatter 无 name | 从 `# 标题` 或 slug 推断 |
| 缺少 description | frontmatter 无 description | 从正文首段提取（≤200 字） |
| 保留 version | 原本有 `version: 1.0` | 保留不动 |
| 不添加 version | 原本无 version | 不添加 |

修复结果通过 `fix_report` 字段返回，包含修复动作列表和错误信息。修复后的 zip 用于后续评测，原始文件不被修改。

## HTML 报告预览

- 📦 技能头部卡片（名称/作者/版本/下载量/星级评分）
- 📊 TRACE 五维度卡片总览（彩色字母 + 得分进度条）
- 📋 维度详解（每维 4 个子指标的评分柱 + LLM 分析摘要）
- 🔒 安全审查（三线审核标记 + 安全发现列表）
- 🏁 审查结论（通过/有条件通过/淘汰 + 汇总表）
- 🔧 格式检测修复记录

打开 [sample-report.html](sample-report.html) 查看含假数据的完整效果。

## 前端对接

详见 [FIELD-MAPPING.md](FIELD-MAPPING.md)，包含完整的 JSON 字段 → HTML 报告映射表，以及 React / Vue 渲染示例。

## 项目结构

```
skillscan/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── report_renderer.py      # HTML 报告渲染器
│   ├── routers/
│   │   └── scan.py             # API 路由 (/scan + /health)
│   ├── engine/
│   │   ├── scanner.py          # 主编排器 (修复→读取→分类→LLM审核→组装)
│   │   ├── skill_fixer.py      # SKILL.md 格式检测与自动修复 (无需LLM)
│   │   ├── classifier.py       # 关键词分类检测引擎 (无需LLM)
│   │   ├── llm_client.py       # OpenAI 兼容 LLM 客户端
│   │   └── prompts.py          # TRACE 系统提示词 + 审核消息构建
│   ├── models/
│   │   └── schemas.py          # 数据模型 (FixReport + TRACE 五维20子指标)
│   ├── templates/
│   │   └── report.html         # SkillHub 风格 Jinja2 报告模板
│   └── utils/
│       └── zip_reader.py       # 安全 zip 读取器 (仅提取文本)
├── sample-report.html          # 假数据预览报告
├── FIELD-MAPPING.md            # 前端对接指南
├── requirements.txt
├── Dockerfile
└── README.md
```

## 安全原则

> **不信任任何来源的技能代码。安装前必须逐行审查。宁可误杀一千，不漏过一个。**

本模块严格执行以下安全原则：
1. **纯静态分析** — 不执行、不 eval、不 import 任何技能代码
2. **LLM 阅读理解** — 大模型仅作为资深审查官"阅读"代码文本，不做代码执行
3. **最小权限** — 仅读取 zip 内的文本文件内容发送给 LLM
4. **零数据外泄风险** — 所有内容仅在本地内存处理，LLM 调用可直连内网私有部署模型

## License

MIT
