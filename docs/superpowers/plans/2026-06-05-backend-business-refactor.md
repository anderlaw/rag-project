# 后端业务全量重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有 API、数据库模型和外部行为的前提下，系统性重构后端业务代码。

**Architecture:** 保留现有 API routes 作为 HTTP 入口，service 层负责编排业务流程，repository 层负责数据库读写，复杂领域逻辑拆到小型 helper/module。RAG Debug 作为当前最大业务服务，拆成 `app/services/rag_debug/` 包；ingestion、chunking、embedding、storage、synonym 等后端业务同步清理边界、注释和隐式规则。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pydantic, pytest.

---

## 范围

本轮只处理后端，不处理前端。

覆盖目录：

```text
app/api/routes/
app/services/
app/repositories/
app/schemas/
app/models/
app/core/
app/utils/
tests/
```

重点文件：

```text
app/services/rag_debug_service.py
app/services/ingest_service.py
app/services/chunker.py
app/services/document_parser.py
app/services/embedding.py
app/services/storage.py
app/services/synonym_service.py
app/repositories/document_repo.py
app/api/routes/documents.py
app/api/routes/rag.py
```

## 非目标

- 不修改前端文件。
- 不修改 API 路由路径。
- 不修改 Pydantic schema 对外字段。
- 不修改 SQLAlchemy model 字段。
- 不新增数据库迁移。
- 不调整检索权重、阈值、排序策略。
- 不引入 ruff、mypy、pre-commit 等新工具。
- 不把后端重写成全新架构。

## 当前问题

### RAG Debug 服务职责过大

`app/services/rag_debug_service.py` 同时包含查询归一化、同义词加载、多路召回、打分、protected recall、文档诊断、Prompt 构建、query log 落库、failure/eval case 创建。它需要拆成职责明确的内部模块。

### Scoring 规则缺少命名和解释

代码中存在大量业务数字，例如：

```python
weighted_mix = (
    section_score * 0.35
    + heading_score * 0.25
    + content_score * 0.35
    + document_name_score * 0.05
)
raw_score = max(
    section_score * 1.35,
    min(heading_score * 1.20, 0.90),
    content_score,
    document_name_score * 0.45,
    weighted_mix,
)
```

这些数字表达字段权重、boost、cap、弱信号惩罚等业务规则，不应裸写在函数内部。重构时必须提成具名常量，分组说明计算原则，并保持原值不变。

### Ingest 流程职责混杂

`app/services/ingest_service.py` 混合了上传校验、文档创建、版本创建、文件存储、文档解析、chunk 构建、embedding、chunk 持久化、version 状态流转和失败回滚。需要拆清步骤，降低单函数复杂度。

### Chunker 注释和边界不清晰

`app/services/chunker.py` 存在口语化、疑问式和临时 TODO 式注释。`absolute_start` 当前是估算逻辑，也需要明确限制。

### Repository 和 Service 边界不够清晰

`DocumentRepository` 已承担部分数据操作，但 service 中仍有不少状态流转和持久化细节。重构后 repository 应负责 DB 操作，service 应负责编排业务流程。

### API routes 偏业务化

routes 应尽量保持薄层，只处理 request/response 和 HTTP error 转换。复杂业务留在 service。

## 目标结构

### RAG Debug

创建：

```text
app/services/rag_debug/
app/services/rag_debug/__init__.py
app/services/rag_debug/types.py
app/services/rag_debug/scoring_rules.py
app/services/rag_debug/query_normalization.py
app/services/rag_debug/scoring.py
app/services/rag_debug/candidate_selection.py
app/services/rag_debug/diagnostics.py
app/services/rag_debug/query_logs.py
app/services/rag_debug/prompting.py
```

职责：

- `types.py`：内部 dataclass，如 `SearchProfile`、`CandidateDraft`、`NormalizedQuery`、`QuerySynonymGroup`。
- `scoring_rules.py`：scoring 相关常量和规则说明。
- `query_normalization.py`：query 清洗、同义词扩展、ASCII/CJK token、phrase、term 去重。
- `scoring.py`：vector/keyword/trgm/heading/final score、topic gate、chunk quality。
- `candidate_selection.py`：候选合并、protected recall、final selection、父 chunk 去重。
- `diagnostics.py`：文档状态诊断和未参与检索文档匹配原因。
- `query_logs.py`：query log 持久化、query log detail、candidate response、source payload。
- `prompting.py`：Prompt 构建和当前 LLM 占位响应。

`app/services/rag_debug_service.py` 只保留对外入口和编排逻辑，并在本轮保留必要 re-export，降低旧测试和调用方迁移风险。

### Document Ingestion

创建：

```text
app/services/ingestion/
app/services/ingestion/__init__.py
app/services/ingestion/validation.py
app/services/ingestion/pipeline.py
app/services/ingestion/chunk_persistence.py
```

职责：

- `validation.py`：上传文件名、扩展名、大小、空文件校验。
- `pipeline.py`：ingest 主流程编排。
- `chunk_persistence.py`：把 `ChunkGroup` 显式保存为 DB chunk。
- `ingest_service.py` 保留对外入口 `ingest_document`。

### 其他服务

- `chunker.py`：保留现有切分行为，清理注释，明确 search text 构建规则和 `absolute_start` 限制。
- `document_parser.py`：保留现有解析行为，说明文件类型判断限制。
- `embedding.py`：保留 fake/DashScope provider 行为，整理 batch size、timeout、错误处理说明。
- `storage.py`：保留 local/S3 provider 行为和 storage key 格式，说明 safe filename 规则。
- `synonym_service.py`：复用 query normalization 公共逻辑，整理 group/term 状态更新边界。
- `document_repo.py`：明确 create/update/status transition 方法职责。
- API routes：保持 HTTP 层薄化，不改变 URL 和 response model。

## Scoring 常量化规则

创建 `app/services/rag_debug/scoring_rules.py`，迁移并说明以下规则。

### Topic Gate

```python
TOPIC_GATE_MIN_SCORE = 0.40
INTENT_GATE_MIN_SCORE = 0.75
TOPICLESS_SYNONYM_SCORE_CAP = 0.50
```

说明：topic gate 用于防止泛同义词命中把主题不相关 chunk 推高。只有命中同义词组且分数超过 cap 时才触发 gate。

### Protected Recall

```python
PROTECTED_RECALL_TOP_K = 3
LEXICAL_PROTECTION_MIN_SCORE = 0.70
HEADING_PROTECTION_MIN_SCORE = 0.70
```

说明：heading/keyword 强命中各保护一个，只从强命中 top 3 中选择，避免弱相关内容被强行保送。

### Keyword Field Scoring

```python
KEYWORD_SECTION_MIX_WEIGHT = 0.35
KEYWORD_HEADING_MIX_WEIGHT = 0.25
KEYWORD_CONTENT_MIX_WEIGHT = 0.35
KEYWORD_DOCUMENT_NAME_MIX_WEIGHT = 0.05
KEYWORD_SECTION_BOOST = 1.35
KEYWORD_HEADING_BOOST = 1.20
KEYWORD_HEADING_SCORE_CAP = 0.90
KEYWORD_DOCUMENT_NAME_MULTIPLIER = 0.45
```

说明：section title 是强结构信号，可以 boost；heading path 可能过宽，所以 boost 后 cap；content 是正文主信号；document name 只作为弱辅助信号，避免文件名主导召回。

### Trgm Field Scoring

```python
TRGM_SECTION_BOOST = 1.20
TRGM_HEADING_BOOST = 1.10
TRGM_HEADING_SCORE_CAP = 0.85
TRGM_DOCUMENT_NAME_MULTIPLIER = 0.40
```

说明：trgm 是模糊匹配，应比 keyword 更保守，因此 boost 和 document name multiplier 都低于 keyword。

### Diagnostics

```python
DIAGNOSTIC_RELATED_MATCH_MIN_SCORE = 0.35
```

说明：用于判断被排除文档是否值得提示；低于该分数不展示为相关未参与检索文档。

### Directory-like Chunk

```python
DIRECTORY_LIKE_CHUNK_SCORE_MULTIPLIER = 0.45
DIRECTORY_SINGLE_LINE_MIN_MARKER_COUNT = 3
DIRECTORY_SINGLE_LINE_MAX_CHARS = 300
DIRECTORY_SHORT_LINE_MAX_CHARS = 40
DIRECTORY_PROSE_LINE_MIN_CHARS = 30
DIRECTORY_LIST_LIKE_LINE_RATIO = 0.60
DIRECTORY_SHORT_LINE_RATIO = 0.60
```

说明：目录 chunk 可能有导航价值，所以降权而不是直接删除；表格不按目录处理；编号数量、短行比例、列表行比例用于识别目录结构；长句比例用于避免把正常正文误判为目录。

### ASCII Matching

```python
MIN_ASCII_MATCH_TERM_LENGTH = 3
```

说明：避免过短英文 token 造成误匹配。

## 注释规范

重构时同步整理注释。

原则：

- 注释解释“为什么”，不要翻译“代码做了什么”。
- 权重、阈值、倍率、cap 必须说明业务含义。
- 启发式规则必须说明适用场景和误判取舍。
- 删除口语化、疑问式、临时 TODO 式注释。
- 保留真实限制和风险说明。

重点补充：

- scoring 规则常量。
- topic gate 的触发条件和压分逻辑。
- protected recall 的保送边界。
- directory-like chunk 的降权取舍。
- `chunker.py` 中 `absolute_start` 的估算限制。
- `ingest_service.py` 的失败回滚语义。
- `storage.py` 的 safe filename 和 storage key 规则。
- `document_parser.py` 的文件类型判断限制。

## 实施任务

### Task 1: 建立后端行为保护测试

**Files:**

- Modify: `tests/test_rag_debug_service.py`
- Modify: `tests/test_rag_debug_api.py`
- Modify: `tests/test_chunker.py`
- Modify: `tests/test_ingestion_failure.py`
- Modify: `tests/test_embedding.py`
- Modify: `tests/test_storage.py`
- Modify: `tests/test_synonyms_api.py`

- [ ] 补充 RAG scoring 常量行为测试，锁定 keyword/trgm/heading 对典型 chunk 的当前分数。
- [ ] 补充 protected recall 测试，覆盖 heading/keyword 各最多保护一个、只从强命中 top 3 中选。
- [ ] 补充 final selection 测试，覆盖 `min_final_score`、父 chunk 去重、低信息 chunk 过滤。
- [ ] 补充 fake embedding profile 降级测试。
- [ ] 补充 ingest 失败回滚、chunker search text、synonym normalization、storage key 行为测试。

Run:

```bash
.venv/bin/pytest -q
```

Expected: all tests pass before refactor continues.

### Task 2: 重构 RAG Debug

**Files:**

- Create: `app/services/rag_debug/__init__.py`
- Create: `app/services/rag_debug/types.py`
- Create: `app/services/rag_debug/scoring_rules.py`
- Create: `app/services/rag_debug/query_normalization.py`
- Create: `app/services/rag_debug/scoring.py`
- Create: `app/services/rag_debug/candidate_selection.py`
- Create: `app/services/rag_debug/diagnostics.py`
- Create: `app/services/rag_debug/query_logs.py`
- Create: `app/services/rag_debug/prompting.py`
- Modify: `app/services/rag_debug_service.py`

- [ ] 先拆 `types.py`，保留 `rag_debug_service.py` re-export。
- [ ] 拆 `scoring_rules.py`，所有业务数字具名化并补规则说明。
- [ ] 拆 `query_normalization.py`，迁移 query 清洗、同义词、token helper。
- [ ] 拆 `scoring.py`，迁移 vector/keyword/trgm/heading/final score、topic gate、chunk quality。
- [ ] 拆 `candidate_selection.py`，迁移候选合并、protected recall、final selection。
- [ ] 拆 `diagnostics.py`，迁移文档状态诊断逻辑。
- [ ] 拆 `query_logs.py`，迁移 query log、candidate response、source payload。
- [ ] 拆 `prompting.py`，迁移 Prompt 和 LLM 占位响应。
- [ ] 精简 `rag_debug_service.py`，只保留编排入口。

Run after each subsection:

```bash
.venv/bin/pytest tests/test_rag_debug_service.py tests/test_rag_debug_api.py -q
```

Expected: RAG behavior and API snapshots unchanged.

### Task 3: 重构 Ingestion

**Files:**

- Create: `app/services/ingestion/__init__.py`
- Create: `app/services/ingestion/validation.py`
- Create: `app/services/ingestion/pipeline.py`
- Create: `app/services/ingestion/chunk_persistence.py`
- Modify: `app/services/ingest_service.py`

- [ ] 抽出上传校验到 `validation.py`。
- [ ] 抽出 chunk 持久化到 `chunk_persistence.py`。
- [ ] 用显式 mapper 替代 `group.parent.__dict__` 和 `child.__dict__`。
- [ ] 在 `pipeline.py` 中组织 version 初始化、文件保存、parse/chunk/embed、状态完成和失败回滚。
- [ ] `ingest_service.py` 保留 `ingest_document` 对外入口。
- [ ] 保持当前失败回滚语义：删除当前 version chunks，标记 version failed。

Run:

```bash
.venv/bin/pytest tests/test_ingestion_failure.py tests/test_documents_api.py -q
```

Expected: upload、version、失败回滚行为不变。

### Task 4: 重构 Chunker

**Files:**

- Modify: `app/services/chunker.py`
- Modify: `tests/test_chunker.py`

- [ ] 清理口语化、疑问式、临时 TODO 式注释。
- [ ] 明确 `absolute_start` 当前是估算值，依赖 block 拼接假设。
- [ ] 保持 `split_text` 行为不变。
- [ ] 补充 search text 构建规则说明。

Run:

```bash
.venv/bin/pytest tests/test_chunker.py -q
```

Expected: chunk 切分和 search text 行为不变。

### Task 5: 重构 Parser

**Files:**

- Modify: `app/services/document_parser.py`
- Modify: `tests/test_documents_api.py`
- Modify: `tests/test_ingestion_failure.py`

- [ ] 清理文件类型判断相关注释。
- [ ] 说明当前仍按扩展名选择 parser。
- [ ] 保持 text、md、pdf、docx 解析行为不变。
- [ ] 不引入文件头识别，本能力作为单独后续任务。

Run:

```bash
.venv/bin/pytest tests/test_documents_api.py tests/test_ingestion_failure.py -q
```

Expected: 文档解析和上传 API 行为不变。

### Task 6: 重构 Embedding

**Files:**

- Modify: `app/services/embedding.py`
- Modify: `tests/test_embedding.py`

- [ ] 整理 fake embedding 和 DashScope embedding 职责边界。
- [ ] batch size、timeout、provider 限制使用具名常量。
- [ ] 保持 fake embedding 确定性输出不变。
- [ ] 保持 DashScope HTTP 错误处理行为不变。

Run:

```bash
.venv/bin/pytest tests/test_embedding.py -q
```

Expected: embedding tests pass.

### Task 7: 重构 Storage

**Files:**

- Modify: `app/services/storage.py`
- Modify: `tests/test_storage.py`

- [ ] 整理 storage interface 注释。
- [ ] 明确 local/S3 provider 职责边界。
- [ ] safe filename 规则补注释。
- [ ] 不修改 storage key 格式。

Run:

```bash
.venv/bin/pytest tests/test_storage.py -q
```

Expected: storage key 和 provider 行为不变。

### Task 8: 重构 Synonym Service

**Files:**

- Modify: `app/services/synonym_service.py`
- Modify: `tests/test_synonyms_api.py`
- Modify: `tests/test_rag_debug_service.py`

- [ ] 复用 `rag_debug/query_normalization.py` 中的公共 query normalization 逻辑。
- [ ] 保持 group/term 状态更新行为不变。
- [ ] 注释说明 synonym status 和 term weight 的业务含义。

Run:

```bash
.venv/bin/pytest tests/test_synonyms_api.py tests/test_rag_debug_service.py -q
```

Expected: synonyms API 和 RAG 同义词扩展行为不变。

### Task 9: 整理 Repository

**Files:**

- Modify: `app/repositories/document_repo.py`
- Modify: `tests/test_documents_api.py`
- Modify: `tests/test_database.py`

- [ ] 明确 repository 只做 DB 读写和状态字段更新。
- [ ] service 层不重复 repository 已表达的 DB 操作。
- [ ] 保持 model 和 schema 不变。

Run:

```bash
.venv/bin/pytest tests/test_documents_api.py tests/test_database.py -q
```

Expected: document DB 行为不变。

### Task 10: 整理 API Routes

**Files:**

- Modify: `app/api/routes/documents.py`
- Modify: `app/api/routes/rag.py`
- Modify: `tests/test_documents_api.py`
- Modify: `tests/test_rag_debug_api.py`
- Modify: `tests/test_synonyms_api.py`

- [ ] routes 只保留 request/response/HTTP error 转换。
- [ ] 复杂业务调用 service。
- [ ] 不修改 URL、status code、response model。

Run:

```bash
.venv/bin/pytest tests/test_documents_api.py tests/test_rag_debug_api.py tests/test_synonyms_api.py -q
```

Expected: API 行为不变。

## 最终验证

Run:

```bash
.venv/bin/pytest -q
```

Expected:

- 所有后端测试通过。
- API 行为不变。
- 数据库模型不变。
- `rag_debug_service.py` 只保留编排逻辑。
- ingest 流程步骤清晰。
- scoring 数字全部具名化并有规则说明。
- 后端业务注释解释设计原因和限制。
- 无口语化、疑问式、临时 TODO 式注释。
- 没有前端文件改动。
