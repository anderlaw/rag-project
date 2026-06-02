# RAG 知识库问答系统：前端架构设计文档

## 1. 文档说明

本文档描述 RAG 知识库问答系统的前端架构设计，包含：

1. 前端技术栈
2. 页面结构
3. 路由设计
4. 页面线框图
5. 页面元素说明
6. 组件设计
7. 接口映射
8. 状态管理
9. 交互流程
10. 开发落地顺序

---

# 2. 前端目标

前端不是单纯做一个聊天窗口，而是要支持：

```txt
文档上传和管理
文档版本查看
chunk 查看和调试
RAG 问答
检索调试
prompt 查看
用户反馈
失败案例管理
测试用例草稿、审核和评估运行管理
搜索配置管理
质量看板
```

测试用例在前端必须体现后端的审核约束：

```txt
自动生成、查询日志转入、失败案例转入的用例都先进入 DRAFT。
DRAFT 用例需要人工补充或确认 expected_answer 和 expected_sources。
审核通过后 status 变为 ACTIVE，才参与 eval_run。
DRAFT / REJECTED / INACTIVE 不参与固定评测。
```

前端需要服务两个角色：

```txt
普通用户：上传文档、提问、查看回答和来源、反馈。
开发/管理员：调试检索、查看 prompt、分析失败案例、运行测试集、调整检索参数。
```

---

# 3. 技术选型

```txt
框架：React
构建工具：Vite
UI：shadcn/ui
样式：Tailwind CSS
状态管理：TanStack Query + React local state
路由：React Router
表单：React Hook Form
表格：TanStack Table
图表：Recharts
代码展示：react-syntax-highlighter 或 textarea readonly
请求：fetch / axios
```

---

# 4. 前端目录结构

```txt
src/
  main.tsx
  App.tsx

  app/
    router.tsx
    providers.tsx

  layouts/
    AppLayout.tsx
    SidebarNav.tsx
    TopBar.tsx

  pages/
    DashboardPage.tsx
    DocumentsPage.tsx
    DocumentDetailPage.tsx
    ChatPage.tsx
    DebugPage.tsx
    QueryLogDetailPage.tsx
    FailureCasesPage.tsx
    FailureCaseDetailPage.tsx
    EvalCasesPage.tsx
    EvalRunDetailPage.tsx
    SearchProfilesPage.tsx

  features/
    documents/
      api.ts
      types.ts
      components/
        DocumentUploadCard.tsx
        DocumentTable.tsx
        DocumentStatusBadge.tsx
        VersionTimeline.tsx
        ChunkTable.tsx
        ChunkPreview.tsx

    rag/
      api.ts
      types.ts
      components/
        QueryInput.tsx
        AnswerCard.tsx
        SourceList.tsx
        SourceDrawer.tsx
        FeedbackBar.tsx
        CandidateTable.tsx
        ScoreBadge.tsx
        PromptViewer.tsx
        LLMResultPanel.tsx
        DebugQueryForm.tsx
        SelectedChunkPanel.tsx
        DebugActions.tsx
        QueryLogSnapshotPanel.tsx

    failures/
      api.ts
      types.ts
      components/
        FailureCaseTable.tsx
        FailureTypeSelect.tsx
        FailureStatusBadge.tsx
        FailureAnalysisForm.tsx

    evals/
      api.ts
      types.ts
      components/
        EvalCaseTable.tsx
        EvalCaseForm.tsx
        EvalCaseReviewPanel.tsx
        EvalExpectedSourceEditor.tsx
        EvalDraftActions.tsx
        EvalRunSummary.tsx
        EvalResultTable.tsx

    searchProfiles/
      api.ts
      types.ts
      components/
        SearchProfileTable.tsx
        SearchProfileForm.tsx
        WeightSlider.tsx
        SetDefaultSearchProfileButton.tsx

  components/
    common/
      PageHeader.tsx
      EmptyState.tsx
      LoadingState.tsx
      ErrorState.tsx
      ConfirmDialog.tsx
      JsonViewer.tsx
      CopyButton.tsx

  lib/
    http.ts
    format.ts
    constants.ts
```

---

# 5. 路由设计

```txt
/                         DashboardPage
/documents                DocumentsPage
/documents/:id            DocumentDetailPage
/chat                     ChatPage
/rag/debug                DebugPage
/rag/query-logs/:id       QueryLogDetailPage
/rag/failures             FailureCasesPage
/rag/failures/:id         FailureCaseDetailPage
/rag/eval-cases           EvalCasesPage
/rag/eval-runs/:id        EvalRunDetailPage
/rag/search-profiles      SearchProfilesPage
```

---

# 6. 全局布局

## 6.1 AppLayout

页面整体布局：

```txt
+--------------------------------------------------------------------------------+
| TopBar                                                                         |
| Logo / 系统名                                      当前模型 / 用户 / 设置       |
+----------------------+---------------------------------------------------------+
| SidebarNav           | Page Content                                            |
|                      |                                                         |
| - 总览               |                                                         |
| - 文档管理           |                                                         |
| - 知识库问答         |                                                         |
| - 检索调试           |                                                         |
| - 失败案例           |                                                         |
| - 测试集             |                                                         |
| - 搜索配置           |                                                         |
|                      |                                                         |
+----------------------+---------------------------------------------------------+
```

---

## 6.2 SidebarNav 菜单

菜单项：

```txt
总览
文档管理
知识库问答
检索调试
失败案例
测试集
搜索配置
```

---

# 7. 页面一：DashboardPage 总览页

## 7.1 页面用途

展示系统整体运行状态。

包括：

```txt
文档数量
chunk 数量
今日提问次数
平均最高分
低置信度次数
失败案例数量
测试集通过率
最近失败案例
最近查询记录
```

---

## 7.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 总览                                                                           |
| 查看系统整体运行状态                                                           |
+--------------------------------------------------------------------------------+

+------------------+------------------+------------------+------------------+
| 文档总数          | Chunk 总数        | 今日提问          | 失败案例          |
| 12               | 3,850            | 42               | 8                |
+------------------+------------------+------------------+------------------+

+------------------+------------------+------------------+------------------+
| 平均最高分        | 低置信度查询      | 用户点踩率        | 测试集通过率      |
| 0.78             | 5                | 12%              | 82%              |
+------------------+------------------+------------------+------------------+

+--------------------------------------+-----------------------------------------+
| 最近查询                              | 最近失败案例                             |
| 问题 / 最高分 / 时间                  | 问题 / 失败类型 / 状态                   |
|                                      |                                         |
+--------------------------------------+-----------------------------------------+
```

---

## 7.3 页面组件

```txt
DashboardMetricCard
RecentQueryTable
RecentFailureTable
EvalPassRateCard
```

---

## 7.4 使用接口

```txt
GET /api/v1/rag/query-logs
GET /api/v1/rag/failure-cases
GET /api/v1/rag/eval-runs
```

---

# 8. 页面二：DocumentsPage 文档管理页

## 8.1 页面用途

上传文档、查看文档列表、查看处理状态。

---

## 8.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 文档管理                                                         [上传文档]     |
| 管理知识库文档，查看版本和 chunk                                                |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 上传区域                                                                       |
| +--------------------------------------------------------------------------+   |
| | 拖拽文件到这里，或点击选择文件                                             |   |
| | 支持：txt / md / pdf / docx                                                |   |
| +--------------------------------------------------------------------------+   |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 搜索文档 [输入文档名...]        状态筛选 [全部 v]       类型筛选 [全部 v]       |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 文档列表                                                                       |
| 文档名              类型     当前版本     状态        Chunk数    更新时间   操作 |
| 公司报销制度.pdf     pdf      v2          ACTIVE      42         ...       详情 |
| 产品手册.md          md       v1          ACTIVE      18         ...       删除 |
+--------------------------------------------------------------------------------+
```

---

## 8.3 页面元素

```txt
上传卡片
文档搜索框
状态筛选
文件类型筛选
文档表格
上传进度
处理状态 badge
操作按钮
```

---

## 8.4 组件设计

### DocumentUploadCard

功能：

```txt
选择文件
拖拽上传
显示上传进度
上传成功后刷新文档列表
```

接口：

```txt
POST /api/v1/documents/upload
```

### DocumentTable

字段：

```txt
文档名
文件类型
当前版本
状态
chunk 数量
更新时间
操作
```

操作：

```txt
查看详情
上传新版本
删除
```

接口：

```txt
GET /api/v1/documents
DELETE /api/v1/documents/{document_id}
POST /api/v1/documents/{document_id}/versions/upload
```

---

# 9. 页面三：DocumentDetailPage 文档详情页

## 9.1 页面用途

查看文档基础信息、版本、chunk 列表、chunk 内容。

这是调试 RAG 的关键页面之一。

---

## 9.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 文档详情：公司报销制度.pdf                                      [上传新版本]    |
| 类型：pdf   当前版本：v2   状态：ACTIVE   Chunk：42                             |
+--------------------------------------------------------------------------------+

+-------------------------------+------------------------------------------------+
| 版本列表                       | 当前版本信息                                    |
| v1 COMPLETED 36 chunks         | version_id: 2                                  |
| v2 COMPLETED 42 chunks [当前]  | file_hash: xxxxx                              |
|                               | parser_version: pdf-parser-v1                 |
|                               | chunk_strategy: parent_child_v1               |
|                               | 创建时间：...   处理完成：...                   |
|                               | [生成测试用例草稿]                              |
+-------------------------------+------------------------------------------------+

+--------------------------------------------------------------------------------+
| Chunk 筛选                                                                    |
| 类型 [CHILD v]    章节 [全部 v]    搜索内容 [输入关键词...]                     |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| Chunk 列表                                                                     |
| Index | 类型   | 章节         | Parent | Tokens | 内容摘要                  |
| 1     | CHILD | 差旅报销      | 3      | 420    | 差旅报销需要提供...       |
| 2     | CHILD | 住宿费用      | 3      | 390    | 如涉及住宿费用...         |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| Chunk 内容预览                                                                 |
| 文档：公司报销制度.pdf                                                         |
| 章节：报销制度 / 差旅报销                                                       |
| 内容：                                                                          |
| 差旅报销需要提供发票、行程单、审批记录...                                       |
+--------------------------------------------------------------------------------+
```

---

## 9.3 页面元素

```txt
文档基础信息卡片
版本列表
版本解析配置和切片配置快照
chunk 筛选区
chunk 表格
chunk 内容预览
parent/child 切换
从文档版本生成测试用例草稿按钮
```

---

## 9.4 组件设计

### VersionTimeline

展示版本：

```txt
版本号
状态
chunk 数量
原始文件名
文件 hash
parser_version
chunk_strategy_name
parser_config_snapshot
chunk_config_snapshot
创建时间
处理完成时间
是否当前版本
```

接口：

```txt
GET /api/v1/documents/{document_id}
```

### ChunkTable

展示 chunk：

```txt
chunk_index
child_index
chunk_type
section_title
parent_chunk_id
token_count
content 摘要
```

说明：

```txt
chunk_index 是当前 document_version 下同一种 chunk_type 的全局顺序。
PARENT 0 和 CHILD 0 可以同时存在。
child_index 表示 CHILD 在所属 parent chunk 内的顺序，PARENT 为空。
```

接口：

```txt
GET /api/v1/documents/{document_id}/chunks
```

### ChunkPreview

点击 chunk 后展示：

```txt
content
content_with_context（CHILD 可能有，PARENT 可为空）
metadata
```

### DocumentVersionEvalDraftButton

功能：

```txt
基于当前文档版本的 PARENT chunks 生成测试用例 DRAFT 候选。
生成结果不会直接进入 ACTIVE，必须在测试集页面人工审核。
```

接口：

```txt
POST /api/v1/rag/document-versions/{document_version_id}/eval-case-drafts
```

---

# 10. 页面四：ChatPage 知识库问答页

## 10.1 页面用途

普通用户使用的主要问答页面。

重点是：

```txt
提问
查看回答
查看引用来源
展开来源原文
提交反馈
```

---

## 10.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 知识库问答                                               搜索配置 [默认混合检索] |
+--------------------------------------------------------------------------------+

+----------------------------+--------------------------------+------------------+
| 历史问题                    | 问答区域                         | 引用来源          |
|                            |                                  |                  |
| - 差旅报销需要...           | 用户：差旅报销需要什么材料？       | 来源 1            |
| - 年假怎么计算...           |                                  | 公司报销制度.pdf   |
| - PTO 是什么...             | AI：差旅报销需要提供发票...        | 章节：差旅报销     |
|                            |                                  | 相似度：0.86      |
|                            | 依据：片段1、片段2                | [展开原文]         |
|                            |                                  |                  |
|                            | [👍 有帮助] [👎 没帮助]            | 来源 2            |
|                            |                                  | ...              |
+----------------------------+--------------------------------+------------------+

+--------------------------------------------------------------------------------+
| 输入问题：                                                                      |
| [ 请问知识库内容...                                                     ] [发送] |
+--------------------------------------------------------------------------------+
```

---

## 10.3 页面元素

```txt
历史问题列表
搜索配置选择器
问答消息区
答案卡片
引用来源侧栏
来源原文展开
反馈按钮
问题输入框
发送按钮
loading 状态
低置信度提示
```

---

## 10.4 组件设计

### QueryInput

功能：

```txt
输入问题
回车发送
loading 时禁用
```

接口：

```txt
POST /api/v1/rag/debug-query
```

请求：

```json
{
  "question": "差旅报销需要什么材料？",
  "use_llm": true,
  "search_profile_id": 1
}
```

### AnswerCard

展示：

```txt
用户问题
AI 回答
生成耗时
模型名称
最高分
低置信度或无召回时的拒答状态
```

### SourceList

展示：

```txt
文档名
版本
章节
页码
分数
chunk 内容摘要
展开按钮
```

### FeedbackBar

按钮：

```txt
👍 有帮助
👎 没帮助
```

点踩后弹窗：

```txt
答案不准确
引用来源不对
回答不完整
没有找到内容
回答太啰嗦
其他
备注输入框
```

接口：

```txt
POST /api/v1/rag/query-logs/{query_log_id}/feedback
```

---

# 11. 页面五：DebugPage 检索调试页

## 11.1 页面用途

开发者分析 RAG 质量的核心页面。

用于回答：

```txt
这次问题搜到了哪些 chunk？
每个 chunk 的分数是多少？
哪些 chunk 被送入 prompt？
prompt 长什么样？
LLM 回答是否基于资料？
```

---

## 11.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 检索调试                                                                        |
| 用于分析 query -> retrieval -> prompt -> answer 全链路                           |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 问题输入                                                                        |
| [ 差旅报销需要什么材料？                                         ] [运行调试]   |
| use_llm [x]     搜索配置 [默认混合检索 v]                                        |
+--------------------------------------------------------------------------------+

+--------------------------------------+-----------------------------------------+
| 检索候选 chunks                       | 最终送入 Prompt 的 chunks                |
|                                      |                                         |
| Rank | 文档 | 章节 | V分 | K分 | T分 | 总分 | 选中 |
| 1    | 报销 | 差旅 | .86| .42| .31| .78 | 是   |
| 2    | 报销 | 住宿 | .80| .28| .20| .68 | 是   |
| 3    | 行政 | 餐饮 | .55| .10| .05| .39 | 否   |
+--------------------------------------+-----------------------------------------+

+--------------------------------------+-----------------------------------------+
| Prompt 预览                           | LLM 回答                                  |
| 你是一个知识库问答助手...              | 差旅报销需要提供发票、行程单...          |
| 资料：                               |                                         |
| [片段1]...                            | 模型：zhipu-configured-model             |
|                                      | 耗时：2300ms                             |
+--------------------------------------+-----------------------------------------+

+--------------------------------------------------------------------------------+
| 操作                                                                            |
| [标记为失败案例] [转为测试用例草稿] [复制 Prompt] [打开查询详情]                  |
+--------------------------------------------------------------------------------+
```

---

## 11.3 页面元素

```txt
问题输入框
use_llm 开关
搜索配置选择
运行按钮
候选 chunk 表
最终 chunk 区
prompt 预览
LLM 回答区
分数展示
手动标记失败按钮
转为测试用例草稿按钮
复制 prompt 按钮
查询日志快照入口
```

---

## 11.4 组件设计

### DebugQueryForm

字段：

```txt
question
search_profile_id
use_llm
```

接口：

```txt
POST /api/v1/rag/debug-query
```

### CandidateTable

列：

```txt
rank
document_name
section_title
vector_score
keyword_score
trgm_score
final_score
selected_for_prompt
content preview
```

### SelectedChunkPanel

展示最终进入 prompt 的 chunks。

### PromptViewer

展示完整 prompt。

需要支持：

```txt
复制
折叠/展开
只读查看
当后端返回 prompt=null 时展示未构建 prompt 的状态
```

### LLMResultPanel

展示：

```txt
answer
model
latency
error
used
无召回拒答状态
```

说明：

```txt
use_llm=true 但没有 selected chunks 时，后端不会调用 LLM。
此时 llm.used=false、prompt=null、model=null，answer 可为“根据当前资料无法确定”。
前端应展示为低置信度/无召回拒答，而不是 LLM 调用失败。
```

### DebugActions

按钮：

```txt
标记失败案例
转为测试用例草稿
复制 prompt
查看查询详情
```

接口：

```txt
POST /api/v1/rag/query-logs/{query_log_id}/failure-case
POST /api/v1/rag/query-logs/{query_log_id}/eval-case-draft
```

### QueryLogSnapshotPanel

展示：

```txt
search_profile_snapshot
model_config_snapshot
answer_prompt_version
answer_prompt_text
```

---

# 12. 页面六：QueryLogDetailPage 查询详情页

## 12.1 页面用途

查看历史某一次查询的完整链路。

---

## 12.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 查询详情 #1001                                                                   |
| 问题：差旅报销需要什么材料？                                                     |
| 时间：2026-06-01 12:00                                                          |
+--------------------------------------------------------------------------------+

+-----------------------------+-----------------------------+--------------------+
| 基础信息                     | 检索配置                     | 耗时               |
| search_mode: HYBRID          | vector_weight: 0.65          | search: 120ms      |
| use_llm: true                | keyword_weight: 0.25         | llm: 2300ms        |
| max_score: 0.86              | trgm_weight: 0.10            | total: 2420ms      |
+-----------------------------+-----------------------------+--------------------+

+--------------------------------------------------------------------------------+
| 配置快照                                                                         |
| search_profile_snapshot / model_config_snapshot                                  |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 候选 Chunks                                                                      |
| Rank | 文档 | 版本 | 章节 | 分数 | 是否进入 prompt | 内容摘要                     |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| Answer Prompt                                                                    |
| version: rag_qa_v1                                                               |
| answer_prompt_text: ...                                                          |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| Answer                                                                           |
| ...                                                                              |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| Feedback / Failure                                                               |
| 用户反馈：NOT_HELPFUL / WRONG_SOURCE                                             |
| 失败案例：RETRIEVAL_LOW_RANK / OPEN                                              |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 操作                                                                             |
| [转为测试用例草稿] [标记失败案例]                                                 |
+--------------------------------------------------------------------------------+
```

---

## 12.3 使用接口

```txt
GET /api/v1/rag/query-logs/{query_log_id}
POST /api/v1/rag/query-logs/{query_log_id}/feedback
POST /api/v1/rag/query-logs/{query_log_id}/failure-case
POST /api/v1/rag/query-logs/{query_log_id}/eval-case-draft
```

展示字段：

```txt
question
search_mode
use_llm
search_profile_snapshot
model_config_snapshot
answer_prompt_version
answer_prompt_text
answer
max_score
min_score
search_latency_ms
llm_latency_ms
total_latency_ms
llm_error
candidates
feedback
failure_case
```

---

# 13. 页面七：FailureCasesPage 失败案例列表页

## 13.1 页面用途

统一管理失败案例。

---

## 13.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 失败案例                                                                         |
| 所有用户反馈、人工调试、测试失败、自动规则生成的问题统一在这里处理                |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 筛选                                                                            |
| 来源 [全部 v]   失败类型 [全部 v]   状态 [OPEN v]   优先级 [全部 v]              |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 失败案例列表                                                                     |
| ID | 问题摘要 | 来源 | 失败类型 | 状态 | 优先级 | 创建时间 | 操作                 |
| 5  | 差旅报销... | USER_FEEDBACK | 未分类 | OPEN | 2 | ... | 查看/分析             |
| 6  | PTO...     | EVAL_RUN      | NO_RECALL | OPEN | 3 | ... | 查看/分析             |
+--------------------------------------------------------------------------------+
```

---

## 13.3 页面元素

```txt
来源筛选
失败类型筛选
状态筛选
优先级筛选
失败案例表格
状态 badge
操作按钮
```

---

## 13.4 组件设计

### FailureCaseTable

列：

```txt
id
question summary
source_type
primary_failure_type
status
priority
created_at
actions
```

接口：

```txt
GET /api/v1/rag/failure-cases
```

---

# 14. 页面八：FailureCaseDetailPage 失败案例详情页

## 14.1 页面用途

分析一个失败案例，确认失败类型，填写修复计划。

---

## 14.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 失败案例 #5                                                                      |
| 来源：USER_FEEDBACK    状态：OPEN    优先级：2                                   |
+--------------------------------------------------------------------------------+

+--------------------------------------+-----------------------------------------+
| 用户问题                              | AI 回答                                  |
| 差旅报销需要什么材料？                 | 差旅报销需要...                          |
+--------------------------------------+-----------------------------------------+

+--------------------------------------------------------------------------------+
| 用户反馈 / 来源信息                                                              |
| rating: NOT_HELPFUL                                                             |
| reason: WRONG_SOURCE                                                            |
| comment: 引用来源不对                                                            |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 检索候选 chunks                                                                  |
| Rank | 文档 | 章节 | 分数 | 是否进入 prompt | 内容摘要                              |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| Prompt                                                                            |
| ...                                                                               |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 失败分析                                                                          |
| 失败类型 [选择 v]                                                                 |
| 分析备注 [textarea]                                                               |
| 修复计划 [textarea]                                                               |
| 状态 [OPEN/ANALYZING/FIXED/WONT_FIX]   优先级 [1-5]                               |
| [保存] [加入测试集]                                                               |
+--------------------------------------------------------------------------------+
```

---

## 14.3 页面元素

```txt
问题展示
回答展示
用户反馈展示
候选 chunk 表
prompt 预览
失败类型选择
分析备注
修复计划
状态选择
优先级选择
保存按钮
加入测试集按钮
```

---

## 14.4 使用接口

```txt
GET /api/v1/rag/failure-cases/{failure_case_id}
PATCH /api/v1/rag/failure-cases/{failure_case_id}
POST /api/v1/rag/eval-cases
```

---

# 15. 页面九：EvalCasesPage 测试集页面

## 15.1 页面用途

管理固定测试问题，运行测试集。

---

## 15.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 测试集                                                          [新建测试用例]   |
| 用于验证切片、检索和回答效果                                                      |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 操作                                                                            |
| 搜索配置 [默认混合检索 v]   use_llm [ ]   [运行测试集]                            |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 测试用例列表                                                                     |
| ID | 问题 | 类型 | 期望文档 | 期望章节 | 状态 | 优先级 | 操作                   |
| 1  | 差旅报销需要什么材料？ | CORE_RULE | 报销制度 | 差旅报销 | ACTIVE | 1 | 编辑 |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 最近运行结果                                                                     |
| Run ID | 名称 | 总数 | 通过 | 失败 | 通过率 | 时间 | 查看详情                 |
+--------------------------------------------------------------------------------+
```

---

## 15.3 页面元素

```txt
测试用例表
新建测试用例弹窗
运行测试集按钮
搜索配置选择
use_llm 开关
最近运行结果表
```

---

## 15.4 组件设计

### EvalCaseTable

列：

```txt
question
case_type
expected_document
expected_section
status
priority
actions
```

接口：

```txt
GET /api/v1/rag/eval-cases
```

### EvalCaseForm

字段：

```txt
question
expected_answer
case_type
expected_document_id
expected_section_title
expected_keywords
priority
```

接口：

```txt
POST /api/v1/rag/eval-cases
PATCH /api/v1/rag/eval-cases/{id}
```

### RunEvalButton

接口：

```txt
POST /api/v1/rag/eval-runs
```

---

# 16. 页面十：EvalRunDetailPage 测试运行详情页

## 16.1 页面用途

查看某次测试运行的详细结果。

---

## 16.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 测试运行详情 #10                                                                  |
| 名称：调整混合检索权重后的测试                                                    |
+--------------------------------------------------------------------------------+

+------------------+------------------+------------------+------------------+
| 总用例            | 通过              | 失败              | 通过率            |
| 20               | 16               | 4                | 80%              |
+------------------+------------------+------------------+------------------+

+--------------------------------------------------------------------------------+
| 结果列表                                                                         |
| 问题 | Top1命中 | Top5命中 | Answer通过 | 失败原因 | 查询日志 | 失败案例             |
| ...  | 是       | 是       | -          | -        | 查看     | -                    |
| ...  | 否       | 否       | -          | 未命中   | 查看     | 查看                 |
+--------------------------------------------------------------------------------+
```

---

## 16.3 使用接口

```txt
GET /api/v1/rag/eval-runs/{eval_run_id}
GET /api/v1/rag/query-logs/{query_log_id}
GET /api/v1/rag/failure-cases/{failure_case_id}
```

---

# 17. 页面十一：SearchProfilesPage 搜索配置页

## 17.1 页面用途

配置混合检索参数。

---

## 17.2 线框图

```txt
+--------------------------------------------------------------------------------+
| 搜索配置                                                        [新建配置]       |
| 调整向量检索、关键词检索、模糊检索的权重和阈值                                    |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 配置列表                                                                         |
| 名称 | 模式 | V TopK | K TopK | T TopK | FinalK | 权重 | 阈值 | 默认 | 操作       |
| 默认混合检索 | HYBRID | 20 | 20 | 20 | 5 | .65/.25/.10 | .55 | 是 | 编辑 |
+--------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------+
| 编辑配置                                                                         |
| 名称 [默认混合检索]                                                              |
| 模式 [HYBRID v]                                                                  |
| vector_top_k [20] keyword_top_k [20] trgm_top_k [20] final_top_k [5]              |
| vector_weight [0.65] keyword_weight [0.25] trgm_weight [0.10]                    |
| min_final_score [0.55]                                                           |
| [保存] [设为默认]                                                                |
+--------------------------------------------------------------------------------+
```

---

## 17.3 页面元素

```txt
配置表
编辑表单
权重输入
top_k 输入
阈值输入
设为默认按钮
```

---

## 17.4 使用接口

```txt
GET /api/v1/rag/search-profiles
POST /api/v1/rag/search-profiles
PATCH /api/v1/rag/search-profiles/{id}
```

---

# 18. 组件和接口映射总表

| 页面                    | 组件                  | 接口                                  |
| --------------------- | ------------------- | ----------------------------------- |
| DocumentsPage         | DocumentUploadCard  | POST /documents/upload              |
| DocumentsPage         | DocumentTable       | GET /documents                      |
| DocumentDetailPage    | VersionTimeline     | GET /documents/{id}                 |
| DocumentDetailPage    | ChunkTable          | GET /documents/{id}/chunks          |
| ChatPage              | QueryInput          | POST /rag/debug-query               |
| ChatPage              | SourceList          | POST /rag/debug-query 返回 sources    |
| ChatPage              | FeedbackBar         | POST /rag/query-logs/{id}/feedback  |
| DebugPage             | DebugQueryForm      | POST /rag/debug-query               |
| DebugPage             | CandidateTable      | POST /rag/debug-query 返回 candidates |
| DebugPage             | PromptViewer        | POST /rag/debug-query 返回 prompt     |
| DebugPage             | LLMResultPanel      | POST /rag/debug-query 返回 llm        |
| QueryLogDetailPage    | QueryDetail         | GET /rag/query-logs/{id}            |
| FailureCasesPage      | FailureCaseTable    | GET /rag/failure-cases              |
| FailureCaseDetailPage | FailureAnalysisForm | PATCH /rag/failure-cases/{id}       |
| EvalCasesPage         | EvalCaseTable       | GET /rag/eval-cases                 |
| EvalCasesPage         | EvalCaseForm        | POST /rag/eval-cases                |
| EvalCasesPage         | RunEvalButton       | POST /rag/eval-runs                 |
| EvalRunDetailPage     | EvalResultTable     | GET /rag/eval-runs/{id}             |
| SearchProfilesPage    | SearchProfileTable  | GET /rag/search-profiles            |
| SearchProfilesPage    | SearchProfileForm   | POST/PATCH /rag/search-profiles     |

---

# 19. 前端状态管理

## 19.1 使用 TanStack Query 管理服务端状态

适合管理：

```txt
documents
document detail
chunks
query logs
failure cases
eval cases
eval runs
search profiles
```

示例 query key：

```ts
["documents"]
["document", documentId]
["document-chunks", documentId, version, chunkType]
["query-log", queryLogId]
["failure-cases", filters]
["eval-cases"]
["search-profiles"]
```

---

## 19.2 使用 local state 管理页面临时状态

适合管理：

```txt
当前输入问题
use_llm 开关
当前选中的 chunk
当前展开的 source
当前编辑中的表单
弹窗打开状态
```

---

# 20. 关键交互流程

## 20.1 文档上传流程

```txt
用户进入文档管理页
  ↓
拖拽或选择文件
  ↓
前端调用 POST /documents/upload
  ↓
显示上传中
  ↓
后端处理完成
  ↓
刷新文档列表
  ↓
用户进入文档详情页查看 chunk
```

---

## 20.2 普通问答流程

```txt
用户进入 /chat
  ↓
输入问题
  ↓
选择搜索配置
  ↓
点击发送
  ↓
调用 POST /rag/debug-query use_llm=true
  ↓
展示 AI 回答
  ↓
右侧展示引用来源
  ↓
用户可展开原文
  ↓
用户可点赞/点踩
```

---

## 20.3 检索调试流程

```txt
开发者进入 /rag/debug
  ↓
输入问题
  ↓
选择 use_llm=false
  ↓
运行
  ↓
查看 candidates
  ↓
判断是否召回正确 chunk
  ↓
切换 use_llm=true
  ↓
查看 prompt 和回答
  ↓
如有问题，标记失败案例或保存为测试用例
```

---

## 20.4 失败案例处理流程

```txt
用户点踩 / 测试失败 / 人工标记
  ↓
生成 failure_case
  ↓
开发者进入失败案例页
  ↓
查看问题、候选 chunks、prompt、answer
  ↓
选择失败类型
  ↓
填写分析备注和修复计划
  ↓
修改系统策略
  ↓
重新运行测试集
  ↓
确认修复后标记 FIXED
```

---

## 20.5 测试集运行流程

```txt
开发者进入测试集页面
  ↓
维护测试问题
  ↓
选择搜索配置
  ↓
点击运行测试集
  ↓
后端逐条调用 debug-query
  ↓
生成 eval_run 和 eval_results
  ↓
前端展示通过率
  ↓
失败项可跳转 query log 和 failure case
```

---

# 21. UI 展示原则

## 21.1 回答页面

回答不要只展示一大段文本，要分层：

```txt
结论
补充说明
依据来源
```

示例：

```txt
结论：
差旅报销需要提供发票、行程单、审批记录。

补充：
如果涉及住宿费用，还需要上传酒店发票和入住记录。

依据：
1. 公司报销制度.pdf / 差旅报销 / 片段1
2. 公司报销制度.pdf / 住宿费用 / 片段2
```

---

## 21.2 来源展示

来源卡片应包含：

```txt
文档名
版本
章节
页码
相似度
原文摘要
展开按钮
```

---

## 21.3 调试页展示

调试页必须显示：

```txt
候选 chunks
最终 chunks
完整 prompt
LLM 回答
分数明细
是否进入 prompt
```

---

## 21.4 失败案例页展示

失败案例页必须显示：

```txt
失败来源
用户问题
AI 回答
用户反馈
候选 chunks
prompt
失败类型
分析备注
修复计划
状态
```

---

# 22. 前端开发优先级

## 阶段一：文档和问答 MVP

```txt
AppLayout
DocumentsPage
DocumentDetailPage
ChatPage
DocumentUploadCard
DocumentTable
ChunkTable
QueryInput
AnswerCard
SourceList
FeedbackBar
```

---

## 阶段二：调试能力

```txt
DebugPage
CandidateTable
PromptViewer
LLMResultPanel
DebugActions
QueryLogDetailPage
```

---

## 阶段三：失败案例

```txt
FailureCasesPage
FailureCaseDetailPage
FailureCaseTable
FailureAnalysisForm
FailureTypeSelect
```

---

## 阶段四：测试集

```txt
EvalCasesPage
EvalRunDetailPage
EvalCaseForm
EvalCaseTable
EvalResultTable
```

---

## 阶段五：搜索配置和看板

```txt
SearchProfilesPage
DashboardPage
SearchProfileForm
DashboardMetricCard
```

---

# 23. 前端验收标准

## 23.1 文档管理验收

```txt
可以上传文档。
可以看到文档列表。
可以进入文档详情。
可以看到版本列表。
可以看到 chunk 列表。
可以预览 chunk 内容。
```

---

## 23.2 问答验收

```txt
可以输入问题。
可以返回 AI 回答。
可以展示来源。
可以展开来源原文。
可以提交用户反馈。
```

---

## 23.3 调试验收

```txt
可以选择 use_llm。
可以查看 candidates。
可以查看 selected chunks。
可以查看 prompt。
可以查看 LLM answer。
可以标记失败案例。
可以保存为测试用例。
```

---

## 23.4 失败案例验收

```txt
可以查看失败案例列表。
可以进入失败案例详情。
可以选择失败类型。
可以填写分析备注。
可以填写修复计划。
可以更新状态。
```

---

## 23.5 测试集验收

```txt
可以创建测试用例。
可以维护期望来源。
可以运行测试集。
可以查看运行结果。
失败用例可以跳转查询详情。
```

---

# 24. 前端总结

前端不是简单聊天 UI，而是围绕 RAG 全链路构建：

```txt
文档管理
+
问答使用
+
检索调试
+
失败分析
+
测试评估
+
搜索配置
```

核心页面优先级：

```txt
1. 文档管理页
2. 文档详情页
3. 知识库问答页
4. 检索调试页
5. 失败案例页
6. 测试集页面
7. 搜索配置页
8. 总览页
```

真正体现工程价值的是：

```txt
能看到 chunk
能看到候选结果
能看到 prompt
能看到回答
能收集反馈
能沉淀失败案例
能运行测试集
能持续调优
```
