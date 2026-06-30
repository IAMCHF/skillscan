# 前端对接指南 — JSON 字段 → HTML 报告映射

`POST /scan` 返回的 `SkillScanResult` JSON 与 HTML 报告模板严格一一对应。

## 报告预览

打开 [sample-report.html](sample-report.html) 查看含假数据的完整效果。

## JSON → HTML 映射表

### 1. 技能头部

| HTML 显示 | JSON 字段路径 | 类型 | 示例值 |
|-----------|-------------|------|--------|
| 技能头像首字母 | `name` 或 `slug` 取前 2 字 | string | `"Excel Formula"` → "Ex" |
| 技能名称 | `name` | string | `"Excel Formula"` |
| AI 综合评分 | `overall_score` | float (0-5) | `4.2` |
| 评级文字 | 4.5+="优秀" 3.5+="良好" 2.5+="一般" <2.5="需改进" | string | `"优秀"` |
| 安全徽章 | `security_level` | "安全" / "存在潜在风险" / "不安全" | `"安全"` |
| "源自 SkillHub" | 固定文本 | - | - |
| 技能描述 | `description_zh` | string | `"通过自然语言描述需求..."` |
| 标签列表 | 从 `detected_category_display` + 固定标签 | - | `"办公效率"` |
| 元信息 | `slug`, `version`, `updated_at` | - | - |

### 2. 统计行

| HTML 显示 | JSON 字段路径 | 类型 |
|-----------|-------------|------|
| 下载量 | `downloads` | int |
| 收藏量 | (暂不展示，预留) | - |
| AI 评分 | `overall_score` | float |
| 作者 | `author` | string |
| 科恩实验室 | `security_labs[0]` → `name`, `result`, `status` | string |
| 云鼎实验室 | `security_labs[1]` → `name`, `result`, `status` | string |

### 3. TRACE 五维度卡片

遍历 `trace_scores[]` 数组，每个元素：

| HTML 显示 | JSON 字段路径 | 类型 |
|-----------|-------------|------|
| 维度字母 | `trace_scores[i].letter` | "T" / "R" / "A" / "C" / "E" |
| 维度名称 | `trace_scores[i].display_name` | "可信任度" / "可靠性" / "适用性" / "规范性" / "有效性" |
| 维度评分 | `trace_scores[i].score` | float (0-5) |
| 进度条百分比 | `score / 5 * 100` | 计算得出 |
| 颜色映射 | T=#3b82f6 R=#10b981 A=#f59e0b C=#8b5cf6 E=#ef4444 | 固定常量 |

### 4. 子指标详解

遍历 `trace_scores[i].sub_indicators[]` 数组，每个元素：

| HTML 显示 | JSON 字段路径 | 类型 |
|-----------|-------------|------|
| 子指标名 | `sub_indicators[j].name` | "安全检测" / "最小权限" / ... |
| 子指标评分 | `sub_indicators[j].score` | int (0-5) |
| 进度条百分比 | `score / 5 * 100` | 计算得出 |
| LLM 备注 | `sub_indicators[j].comment` | string |

### 5. 维度分析摘要

| HTML 显示 | JSON 字段路径 | 类型 |
|-----------|-------------|------|
| LLM 分析文字 | `trace_scores[i].findings_summary` | string |

### 6. 安全审查发现

遍历 `security_findings[]` 数组：

| HTML 显示 | JSON 字段路径 | 类型 |
|-----------|-------------|------|
| 严重等级徽章 | `security_findings[k].severity` | "info" / "warning" / "critical" |
| 分类标签 | `security_findings[k].category` | "网络请求" / "命令执行" / ... |
| 发现描述 | `security_findings[k].description` | string |
| 涉及文件 | `security_findings[k].file_path` | string |
| 安全建议 | `security_findings[k].suggestion` | string |

### 7. 审查结论

| HTML 显示 | JSON 字段路径 | 类型 |
|-----------|-------------|------|
| 结论横幅 | `verdict` | "通过" / "有条件通过" / "淘汰" |
| 结论原因 | `verdict_reason` | string |
| 综合评分 | `overall_score` | float |
| 安全等级 | `security_level` | string |
| 检测分类 | `detected_category_display` | string |
| 扫描文件数 | `files_scanned` | int |
| 代码总行数 | `total_lines` | int |
| 扫描耗时 | `scan_duration_ms` | int (毫秒) |

---

## 前端渲染示例 (React)

```jsx
// 调用接口
const res = await fetch('http://localhost:8000/scan', {
  method: 'POST',
  body: formData
});
const data = await res.json();

// 直接绑定
<SkillHeader
  name={data.name}
  overallScore={data.overall_score}
  securityLevel={data.security_level}
  description={data.description_zh}
/>

<TraceRadar
  dimensions={data.trace_scores}
/>

<DimensionDetails
  dimensions={data.trace_scores}
/>

<SecurityFindings
  findings={data.security_findings}
  labs={data.security_labs}
/>

<VerdictBanner
  verdict={data.verdict}
  reason={data.verdict_reason}
/>

<SummaryTable
  overallScore={data.overall_score}
  securityLevel={data.security_level}
  category={data.detected_category_display}
  verdict={data.verdict}
  filesScanned={data.files_scanned}
  totalLines={data.total_lines}
  scanDurationMs={data.scan_duration_ms}
/>
```

## 前端渲染示例 (Vue)

```vue
<template>
  <div>
    <SkillHeader
      :name="report.name"
      :overall-score="report.overall_score"
      :security-level="report.security_level"
    />
    <TraceRadar :dimensions="report.trace_scores" />
    <DimensionDetails :dimensions="report.trace_scores" />
    <SecurityFindings :findings="report.security_findings" :labs="report.security_labs" />
    <VerdictBanner :verdict="report.verdict" :reason="report.verdict_reason" />
    <SummaryTable v-bind="report" />
  </div>
</template>
```
