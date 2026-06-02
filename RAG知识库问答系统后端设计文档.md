# RAG 知识库问答系统：后端系统设计文档

## 1. 文档说明

本文档描述 RAG 知识库问答系统的后端设计，包含：

1. 系统目标
2. 后端架构
3. 功能模块
4. 数据库表设计
5. 接口设计
6. 文档入库流程
7. Chunk 生成方案
8. 向量检索方案
9. 混合检索方案
10. 调试与日志方案
11. 用户反馈与失败案例方案
12. 测试用例录入、审核与评估方案
13. 技术选型与插件
14. 核心伪代码
15. 开发落地顺序

---

# 2. 系统目标

本系统是一个可持续优化的 RAG 知识库问答系统。

系统不仅要完成基础问答链路：

```txt
文档上传
  ↓
文本解析
  ↓
切片 chunk
  ↓
生成 embedding
  ↓
存入 Neon Postgres
  ↓
用户提问
  ↓
检索相关 chunk
  ↓
拼接 prompt
  ↓
调用 LLM
  ↓
返回回答和引用来源
```

还要支持：

```txt
检索调试
失败案例沉淀
用户反馈
测试集评估
文档版本管理
混合检索
搜索参数调优
```

系统定位不是简单聊天机器人，而是：

```txt
知识入库系统
+
向量检索系统
+
问答生成系统
+
调试系统
+
评估系统
+
优化闭环系统
```

---

# 3. 技术选型

## 3.1 后端技术栈

```txt
后端框架：FastAPI
数据库：Neon Postgres
ORM：SQLAlchemy
数据库迁移：Alembic
向量扩展：pgvector
全文检索：PostgreSQL Full Text Search
模糊检索：pg_trgm
Embedding：通义向量（tongyi-embedding-vision-plus-2026-03-06）
LLM：智谱大模型
文件解析：pypdf / pymupdf / python-docx / markdown parser
异步任务：MVP 同步处理，后续可接 Celery / RQ / Dramatiq
日志：Python logging
配置：pydantic-settings
```

---

## 3.2 数据库插件

需要在 Neon SQL Editor 或 Alembic migration 中执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

说明：

```txt
vector：pgvector 扩展，用于存储 embedding 和执行向量相似度检索。
pg_trgm：PostgreSQL 扩展，用于字符串相似度、模糊匹配、近似关键词检索。
Full Text Search：PostgreSQL 内置能力，不需要额外 CREATE EXTENSION。
```

---

# 4. 后端目录结构

```txt
app/
  main.py

  api/
    deps.py
    routes/
      documents.py
      rag.py
      feedback.py
      failures.py
      evals.py
      search_profiles.py

  core/
    config.py
    database.py
    logging.py
    errors.py

  models/
    rag_document.py
    rag_document_version.py
    rag_chunk.py
    rag_query_log.py
    rag_query_candidate.py
    rag_feedback.py
    rag_failure_case.py
    rag_eval_case.py
    rag_eval_expected_source.py
    rag_eval_run.py
    rag_eval_result.py
    rag_search_profile.py

  schemas/
    document.py
    rag.py
    feedback.py
    failure.py
    eval.py
    search_profile.py

  repositories/
    document_repo.py
    chunk_repo.py
    query_log_repo.py
    feedback_repo.py
    failure_repo.py
    eval_repo.py
    search_profile_repo.py

  services/
    document_parser.py
    chunker.py
    embedding_service.py
    llm_service.py
    vector_search_service.py
    keyword_search_service.py
    trigram_search_service.py
    hybrid_search_service.py
    prompt_builder.py
    ingest_service.py
    rag_service.py
    feedback_service.py
    failure_service.py
    eval_service.py

  utils/
    hash.py
    text.py
    timer.py
```

分层说明：

```txt
api 层：负责接收 HTTP 请求，参数校验，调用 service。
service 层：负责编排业务流程。
repository 层：负责数据库读写。
models 层：定义 SQLAlchemy ORM。
schemas 层：定义请求和响应结构。
core 层：配置、数据库连接、日志、异常处理。
utils 层：通用工具函数。
```

---

# 5. 核心业务模块

## 5.1 文档管理模块

功能：

```txt
上传文档
查看文档列表
查看文档详情
查看文档版本
查看 chunk 列表
更新文档
删除文档
```

核心原则：

```txt
文档更新时不覆盖旧 chunk。
每次更新创建新的 document_version。
正常问答只检索 current_version_id 对应的 chunk。
旧版本用于历史追溯、调试和回滚。
```

---

## 5.2 文档入库模块

流程：

```txt
接收文件
  ↓
创建 rag_documents
  ↓
创建 rag_document_versions
  ↓
解析文本 blocks
  ↓
生成 parent chunks
  ↓
生成 child chunks
  ↓
给 child chunks 生成 embedding
  ↓
生成 search_text/search_tsv
  ↓
写入 rag_chunks
  ↓
更新 document.current_version_id
```

---

## 5.3 Chunk 模块

本系统采用父子 chunk 方案。

```txt
Parent chunk：大 chunk，用于给 LLM 提供完整上下文。
Child chunk：小 chunk，用于精准向量检索。
```

检索流程：

```txt
用户问题
  ↓
检索 child chunk
  ↓
根据 parent_chunk_id 找到 parent chunk
  ↓
把 parent chunk 放入 prompt
```

---

## 5.4 检索模块

支持三种检索：

```txt
VECTOR：向量检索，使用 pgvector。
KEYWORD：全文关键词检索，使用 PostgreSQL Full Text Search。
TRIGRAM：模糊匹配，使用 pg_trgm。
HYBRID：混合检索，融合以上三种结果。
```

---

## 5.5 调试模块

统一使用一个调试接口：

```http
POST /api/v1/rag/debug-query
```

通过参数控制是否调用 LLM：

```json
{
  "use_llm": true
}
```

返回统一结构：

```txt
question
search candidates
selected chunks
prompt
llm answer
latency
query_log_id
```

---

## 5.6 用户反馈模块

用户对回答进行反馈：

```txt
HELPFUL
NOT_HELPFUL
```

如果用户点踩，系统生成失败案例。

---

## 5.7 失败案例模块

失败案例统一进入：

```txt
rag_failure_cases
```

失败来源包括：

```txt
USER_FEEDBACK：用户反馈生成
MANUAL_DEBUG：人工调试生成
EVAL_RUN：测试集失败生成
AUTO_RULE：系统规则自动生成
```

---

## 5.8 测试集评估模块

用于持续优化检索质量。

测试用例先进入草稿和审核流程，审核通过后才参与固定评测。

测试集不需要覆盖所有 chunk，而是覆盖：

```txt
核心规则问题
高频用户问题
边界问题
历史失败问题
```

---

# 6. 数据库表设计

数据库关系策略：

```txt
本系统不使用数据库物理外键。
所有 xxx_id 字段均为逻辑外键，由 service / repo 层校验关联是否存在、是否属于同一业务范围、是否允许删除。
数据库层保留主键、唯一约束、CHECK 约束和必要索引，但不使用 REFERENCES / FOREIGN KEY / ON DELETE。
删除、归档、版本切换等级联动作由业务代码在事务中显式处理，避免物理外键带来的迁移、导入、重建索引和历史日志保留问题。
```

逻辑外键索引建议：

```sql
CREATE INDEX idx_rag_documents_current_version
ON rag_documents(current_version_id);

CREATE INDEX idx_rag_document_versions_document
ON rag_document_versions(document_id);

CREATE INDEX idx_rag_query_logs_search_profile
ON rag_query_logs(search_profile_id);

CREATE INDEX idx_rag_query_candidates_query_log
ON rag_query_candidates(query_log_id);

CREATE INDEX idx_rag_feedback_query_log
ON rag_feedback(query_log_id);

CREATE INDEX idx_rag_failure_cases_query_log
ON rag_failure_cases(query_log_id);

CREATE INDEX idx_rag_eval_expected_sources_case
ON rag_eval_expected_sources(eval_case_id);

CREATE INDEX idx_rag_eval_runs_search_profile
ON rag_eval_runs(search_profile_id);

CREATE INDEX idx_rag_eval_results_run
ON rag_eval_results(eval_run_id);

CREATE INDEX idx_rag_eval_results_case
ON rag_eval_results(eval_case_id);

CREATE INDEX idx_rag_eval_results_query_log
ON rag_eval_results(query_log_id);
```

说明：

```txt
这些索引不是物理外键，只是为了支撑按逻辑关系查询、校验和清理。
rag_chunks 的 document_version_id、parent_chunk_id 等索引在 rag_chunks 表小节中单独定义。
```

## 6.1 rag_documents

表用途：

```txt
保存文档的主记录。
一个文档可以有多个版本。
current_version_id 指向当前生效版本。
正常问答只检索当前版本的 chunk。
```

```sql
CREATE TABLE rag_documents (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  file_type TEXT,
  file_size BIGINT,
  current_version_id BIGINT,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_documents IS '文档主表，保存文档基础信息，一个文档可以有多个版本';
COMMENT ON COLUMN rag_documents.id IS '文档主键 ID';
COMMENT ON COLUMN rag_documents.name IS '文档名称，例如 公司报销制度.pdf';
COMMENT ON COLUMN rag_documents.file_type IS '文件类型，例如 pdf、txt、md、docx';
COMMENT ON COLUMN rag_documents.file_size IS '文件大小，单位 byte';
COMMENT ON COLUMN rag_documents.current_version_id IS '当前生效版本 ID，正常问答只检索该版本的 chunk';
COMMENT ON COLUMN rag_documents.status IS '文档状态，ACTIVE 表示可用，DELETED 表示已删除';
COMMENT ON COLUMN rag_documents.created_at IS '文档首次创建时间';
COMMENT ON COLUMN rag_documents.updated_at IS '文档最近更新时间';
```

字段说明：

| 字段                 | 类型        | 说明     |
| ------------------ | --------- | ------ |
| id                 | BIGSERIAL | 文档主键   |
| name               | TEXT      | 文档名称   |
| file_type          | TEXT      | 文件类型   |
| file_size          | BIGINT    | 文件大小   |
| current_version_id | BIGINT    | 当前生效版本 |
| status             | TEXT      | 文档状态   |
| created_at         | TIMESTAMP | 创建时间   |
| updated_at         | TIMESTAMP | 更新时间   |

---

## 6.2 rag_document_versions

表用途：

```txt
保存文档版本。
每次文档更新时创建一个新版本。
旧版本不会直接覆盖，用于历史追溯和调试。
```

```sql
CREATE TABLE rag_document_versions (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT NOT NULL,
  version_no INT NOT NULL,
  file_hash TEXT NOT NULL,
  original_filename TEXT,
  storage_key TEXT,
  parser_version TEXT,
  parser_config_snapshot JSONB,
  chunk_strategy_name TEXT,
  chunk_config_snapshot JSONB,
  status TEXT NOT NULL DEFAULT 'PROCESSING',
  chunk_count INT DEFAULT 0,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT now(),
  processed_at TIMESTAMP,

  UNIQUE (document_id, version_no),
  UNIQUE (document_id, id)
);

COMMENT ON TABLE rag_document_versions IS '文档版本表，每次上传或更新文档都会创建新版本';
COMMENT ON COLUMN rag_document_versions.id IS '文档版本主键 ID';
COMMENT ON COLUMN rag_document_versions.document_id IS '所属文档 ID';
COMMENT ON COLUMN rag_document_versions.version_no IS '版本号，从 1 开始递增';
COMMENT ON COLUMN rag_document_versions.file_hash IS '文件内容 hash，用于判断文件是否变化';
COMMENT ON COLUMN rag_document_versions.original_filename IS '原始上传文件名';
COMMENT ON COLUMN rag_document_versions.storage_key IS '原始文件存储位置或对象存储 key';
COMMENT ON COLUMN rag_document_versions.parser_version IS '业务解析流水线版本，例如 pdf-parser-v1，不只是第三方库版本';
COMMENT ON COLUMN rag_document_versions.parser_config_snapshot IS '解析配置快照，记录解析器名称、规则版本、第三方库版本和关键参数';
COMMENT ON COLUMN rag_document_versions.chunk_strategy_name IS 'chunk 策略名称，例如 parent_child_v1';
COMMENT ON COLUMN rag_document_versions.chunk_config_snapshot IS 'chunk 配置快照，记录 parent/child 大小、overlap、是否按标题切分等参数';
COMMENT ON COLUMN rag_document_versions.status IS '版本处理状态，PROCESSING、COMPLETED、FAILED';
COMMENT ON COLUMN rag_document_versions.chunk_count IS '该版本生成的 chunk 数量';
COMMENT ON COLUMN rag_document_versions.error_message IS '处理失败时的错误信息';
COMMENT ON COLUMN rag_document_versions.created_at IS '版本创建时间';
COMMENT ON COLUMN rag_document_versions.processed_at IS '版本处理完成或失败时间';
```

字段说明：

| 字段            | 类型        | 说明       |
| ------------- | --------- | -------- |
| id            | BIGSERIAL | 版本主键     |
| document_id   | BIGINT    | 所属文档     |
| version_no    | INT       | 版本号      |
| file_hash     | TEXT      | 文件 hash  |
| original_filename | TEXT      | 原始文件名    |
| storage_key   | TEXT      | 文件存储位置   |
| parser_version | TEXT     | 业务解析流水线版本 |
| parser_config_snapshot | JSONB | 解析配置快照 |
| chunk_strategy_name | TEXT | chunk 策略名称 |
| chunk_config_snapshot | JSONB | chunk 配置快照 |
| status        | TEXT      | 处理状态     |
| chunk_count   | INT       | chunk 数量 |
| error_message | TEXT      | 错误信息     |
| created_at    | TIMESTAMP | 创建时间     |
| processed_at  | TIMESTAMP | 处理完成时间   |

状态枚举：

```txt
PROCESSING
COMPLETED
FAILED
```

逻辑外键说明：

```txt
current_version_id 允许为空，表示文档尚未成功入库。
业务层必须保证 current_version_id 指向同一 document_id 下 status=COMPLETED 的 rag_document_versions.id。
切换当前版本必须在同一事务中完成版本状态更新和 rag_documents.current_version_id 更新。
```

解析与 chunk 配置说明：

```txt
parser_version 表示业务里的解析流水线版本，而不是单纯的第三方插件版本。
例如 pdf-parser-v1、pdf-parser-v2-heading-regex、docx-parser-v1。
如果第三方库版本、标题识别规则、表格提取策略、去页眉页脚规则发生变化，都应该体现在 parser_config_snapshot 中。

chunk_strategy_name 只保存策略名。
chunk_config_snapshot 保存真正影响切片结果的参数，使用 JSONB 是为了保留结构化配置，方便后续复现入库结果和比较不同版本。
```

示例：

```json
{
  "parser_version": "pdf-parser-v1",
  "parser_config_snapshot": {
    "parser": "pymupdf",
    "library_version": "1.24.x",
    "heading_rule_version": "heading-regex-v1",
    "remove_header_footer": true
  },
  "chunk_strategy_name": "parent_child_v1",
  "chunk_config_snapshot": {
    "split_by_heading": true,
    "parent_chunk_size": 1600,
    "child_chunk_size": 500,
    "child_overlap": 80,
    "embedding_text": "content_with_context"
  }
}
```

---

## 6.3 rag_chunks

表用途：

```txt
保存文档切片。
同时保存 parent chunk 和 child chunk。
child chunk 用于检索。
parent chunk 用于回答上下文。
```

```sql
CREATE TABLE rag_chunks (
  id BIGSERIAL PRIMARY KEY,

  document_id BIGINT NOT NULL,
  document_version_id BIGINT NOT NULL,

  parent_chunk_id BIGINT,

  chunk_type TEXT NOT NULL,
  chunk_index INT NOT NULL,
  child_index INT,

  section_title TEXT,
  heading_path TEXT,

  page_start INT,
  page_end INT,
  start_char INT,
  end_char INT,

  content TEXT NOT NULL,
  content_with_context TEXT,

  content_hash TEXT,
  token_count INT,

  embedding VECTOR(1536),

  search_text TEXT,
  search_tsv tsvector,

  created_at TIMESTAMP DEFAULT now(),

  UNIQUE (document_id, document_version_id, id),
  UNIQUE (document_version_id, chunk_type, chunk_index),
  UNIQUE (parent_chunk_id, child_index),

  CONSTRAINT chk_rag_chunks_type
    CHECK (chunk_type IN ('PARENT', 'CHILD')),

  CONSTRAINT chk_rag_chunks_parent
    CHECK (
      (
        chunk_type = 'PARENT'
        AND parent_chunk_id IS NULL
        AND child_index IS NULL
        AND embedding IS NULL
      )
      OR
      (
        chunk_type = 'CHILD'
        AND parent_chunk_id IS NOT NULL
        AND child_index IS NOT NULL
        AND content_with_context IS NOT NULL
        AND embedding IS NOT NULL
      )
    )
);

COMMENT ON TABLE rag_chunks IS '文档切片表，保存 parent chunk 和 child chunk';
COMMENT ON COLUMN rag_chunks.id IS 'chunk 主键 ID';
COMMENT ON COLUMN rag_chunks.document_id IS '所属文档 ID';
COMMENT ON COLUMN rag_chunks.document_version_id IS '所属文档版本 ID';
COMMENT ON COLUMN rag_chunks.parent_chunk_id IS '父 chunk ID，child chunk 通过该字段关联 parent chunk';
COMMENT ON COLUMN rag_chunks.chunk_type IS 'chunk 类型，PARENT 或 CHILD';
COMMENT ON COLUMN rag_chunks.chunk_index IS 'chunk 在当前文档版本、同一 chunk_type 下的全局顺序';
COMMENT ON COLUMN rag_chunks.child_index IS 'child chunk 在所属 parent chunk 内的顺序，PARENT 行为空';
COMMENT ON COLUMN rag_chunks.section_title IS '当前 chunk 所属章节标题';
COMMENT ON COLUMN rag_chunks.heading_path IS '标题路径，例如 公司制度 / 报销制度 / 差旅报销';
COMMENT ON COLUMN rag_chunks.page_start IS 'chunk 起始页码，主要用于 PDF';
COMMENT ON COLUMN rag_chunks.page_end IS 'chunk 结束页码，主要用于 PDF';
COMMENT ON COLUMN rag_chunks.start_char IS 'chunk 在原始文本中的起始字符位置';
COMMENT ON COLUMN rag_chunks.end_char IS 'chunk 在原始文本中的结束字符位置';
COMMENT ON COLUMN rag_chunks.content IS '原始 chunk 内容，用于展示给用户';
COMMENT ON COLUMN rag_chunks.content_with_context IS '带文档名、标题、页码的上下文文本，CHILD 必填，用于生成 embedding';
COMMENT ON COLUMN rag_chunks.content_hash IS 'chunk 内容 hash，用于判断是否变化和去重';
COMMENT ON COLUMN rag_chunks.token_count IS 'chunk token 或字符数量估算';
COMMENT ON COLUMN rag_chunks.embedding IS 'embedding 向量，通常只给 CHILD chunk 生成';
COMMENT ON COLUMN rag_chunks.search_text IS '用于关键词和模糊检索的文本，通常包含文档名、标题、正文';
COMMENT ON COLUMN rag_chunks.search_tsv IS 'PostgreSQL Full Text Search 使用的 tsvector 字段';
COMMENT ON COLUMN rag_chunks.created_at IS 'chunk 创建时间';
```

字段说明：

| 字段                   | 类型           | 说明                  |
| -------------------- | ------------ | ------------------- |
| id                   | BIGSERIAL    | chunk 主键            |
| document_id          | BIGINT       | 所属文档                |
| document_version_id  | BIGINT       | 所属文档版本              |
| parent_chunk_id      | BIGINT       | 父 chunk ID          |
| chunk_type           | TEXT         | PARENT / CHILD      |
| chunk_index          | INT          | 同类型全局顺序             |
| child_index          | INT          | 父 chunk 内子顺序         |
| section_title        | TEXT         | 章节标题                |
| heading_path         | TEXT         | 标题路径                |
| page_start           | INT          | 起始页码                |
| page_end             | INT          | 结束页码                |
| start_char           | INT          | 起始字符                |
| end_char             | INT          | 结束字符                |
| content              | TEXT         | 原始内容                |
| content_with_context | TEXT         | CHILD 必填，用于 embedding 的上下文文本 |
| content_hash         | TEXT         | 内容 hash             |
| token_count          | INT          | token 数             |
| embedding            | VECTOR(1536) | PARENT 为空，CHILD 必填 |
| search_text          | TEXT         | 关键词检索文本             |
| search_tsv           | tsvector     | 全文检索向量              |
| created_at           | TIMESTAMP    | 创建时间                |

约束说明：

```txt
child chunk 必须指向同一 document_version 下的 parent chunk。
parent chunk 不允许有 parent_chunk_id。
child chunk 必须有 child_index，parent chunk 的 child_index 必须为空。
chunk_index 表示当前 document_version 下，同一种 chunk_type 的全局顺序；因此 PARENT 0 和 CHILD 0 可以同时存在。
业务层必须校验 document_id 与 document_version_id 一致，避免 chunk 被挂到错误文档版本。
业务层必须校验 CHILD 的 parent_chunk_id 指向同一 document_version 下的 PARENT 行，避免 child 指向另一个 child。
PARENT 不生成 embedding；CHILD 必须有 content_with_context 和 embedding。
embedding 维度必须与实际 embedding 模型输出一致；如果模型不是 1536 维，建表时必须同步调整 VECTOR(N)。
```

字段填充建议：

| 字段                 | PARENT | CHILD |
| ------------------ | ------ | ----- |
| content            | 必填     | 必填    |
| content_with_context | 可空   | 必填    |
| embedding          | 空      | 必填    |
| search_text        | 可填     | 必填    |
| search_tsv         | 可生成    | 可生成   |

索引：

```sql
CREATE INDEX idx_rag_chunks_document_version
ON rag_chunks(document_id, document_version_id);

CREATE INDEX idx_rag_chunks_parent
ON rag_chunks(parent_chunk_id, child_index)
WHERE chunk_type = 'CHILD';

CREATE INDEX idx_rag_chunks_type
ON rag_chunks(chunk_type);

CREATE INDEX idx_rag_chunks_search_tsv
ON rag_chunks
USING GIN(search_tsv);

CREATE INDEX idx_rag_chunks_search_text_trgm
ON rag_chunks
USING GIN(search_text gin_trgm_ops);

CREATE INDEX idx_rag_chunks_embedding_hnsw
ON rag_chunks
USING hnsw (embedding vector_cosine_ops)
WHERE chunk_type = 'CHILD' AND embedding IS NOT NULL;
```

查询某个 parent 下的 child：

```sql
SELECT *
FROM rag_chunks
WHERE parent_chunk_id = :parent_chunk_id
  AND chunk_type = 'CHILD'
ORDER BY child_index ASC;
```

说明：

```txt
数据量小于几千 chunk 时，向量索引可以暂缓创建。
数据量达到几万 chunk 后，再创建 HNSW 索引。
```

---

## 6.4 rag_query_logs

表用途：

```txt
记录每一次用户提问、调试查询、LLM 回答。
该表同时承担问答历史、调试日志、性能分析的作用。
不再单独创建 qa_records 表，避免重复。
```

```sql
CREATE TABLE rag_query_logs (
  id BIGSERIAL PRIMARY KEY,

  question TEXT NOT NULL,

  search_mode TEXT NOT NULL DEFAULT 'HYBRID',
  use_llm BOOLEAN NOT NULL DEFAULT true,

  search_profile_id BIGINT,
  search_profile_snapshot JSONB,
  model_config_snapshot JSONB,
  answer_prompt_version TEXT,

  top_k INT DEFAULT 20,
  final_top_k INT DEFAULT 5,

  embedding_model TEXT,
  llm_model TEXT,

  answer_prompt_text TEXT,
  answer TEXT,

  max_score FLOAT,
  min_score FLOAT,

  search_latency_ms INT,
  llm_latency_ms INT,
  total_latency_ms INT,

  llm_error TEXT,

  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_query_logs IS '查询日志表，记录每次问题、检索、prompt、回答和耗时';
COMMENT ON COLUMN rag_query_logs.id IS '查询日志主键 ID';
COMMENT ON COLUMN rag_query_logs.question IS '用户输入的问题';
COMMENT ON COLUMN rag_query_logs.search_mode IS '检索模式，VECTOR、KEYWORD、TRIGRAM、HYBRID';
COMMENT ON COLUMN rag_query_logs.use_llm IS '是否调用 LLM，false 表示只调试检索';
COMMENT ON COLUMN rag_query_logs.search_profile_id IS '使用的搜索配置 ID';
COMMENT ON COLUMN rag_query_logs.search_profile_snapshot IS '查询时的搜索配置快照，避免后续配置修改影响历史分析';
COMMENT ON COLUMN rag_query_logs.model_config_snapshot IS '查询时实际生效的 embedding/LLM 模型配置快照，来自 settings 和模型服务运行时配置';
COMMENT ON COLUMN rag_query_logs.answer_prompt_version IS '本次生成最终回答使用的主回答 prompt 版本标签，例如 rag_qa_v1；不是全套提示词的统一版本';
COMMENT ON COLUMN rag_query_logs.top_k IS '候选检索数量';
COMMENT ON COLUMN rag_query_logs.final_top_k IS '最终送入 prompt 的 chunk 数量';
COMMENT ON COLUMN rag_query_logs.embedding_model IS '问题 embedding 使用的模型';
COMMENT ON COLUMN rag_query_logs.llm_model IS '回答生成使用的 LLM 模型';
COMMENT ON COLUMN rag_query_logs.answer_prompt_text IS '最终发送给 LLM 的主回答 prompt 快照';
COMMENT ON COLUMN rag_query_logs.answer IS 'LLM 返回的回答';
COMMENT ON COLUMN rag_query_logs.max_score IS '候选 chunk 中最高分';
COMMENT ON COLUMN rag_query_logs.min_score IS '候选 chunk 中最低分';
COMMENT ON COLUMN rag_query_logs.search_latency_ms IS '检索耗时，毫秒';
COMMENT ON COLUMN rag_query_logs.llm_latency_ms IS 'LLM 调用耗时，毫秒';
COMMENT ON COLUMN rag_query_logs.total_latency_ms IS '总耗时，毫秒';
COMMENT ON COLUMN rag_query_logs.llm_error IS 'LLM 调用失败时的错误信息';
COMMENT ON COLUMN rag_query_logs.created_at IS '查询创建时间';
```

字段说明：

| 字段                | 类型        | 说明           |
| ----------------- | --------- | ------------ |
| id                | BIGSERIAL | 查询日志 ID      |
| question          | TEXT      | 用户问题         |
| search_mode       | TEXT      | 检索模式         |
| use_llm           | BOOLEAN   | 是否调用 LLM     |
| search_profile_id | BIGINT    | 搜索配置         |
| search_profile_snapshot | JSONB | 搜索配置快照      |
| model_config_snapshot | JSONB | 模型配置快照       |
| answer_prompt_version | TEXT | 本次最终回答使用的主回答 prompt 代码版本，例如 rag_qa_v1 |
| top_k             | INT       | 候选数量         |
| final_top_k       | INT       | 入 prompt 数量  |
| embedding_model   | TEXT      | embedding 模型 |
| llm_model         | TEXT      | LLM 模型       |
| answer_prompt_text | TEXT     | 主回答 prompt 快照 |
| answer            | TEXT      | 回答           |
| max_score         | FLOAT     | 最高分          |
| min_score         | FLOAT     | 最低分          |
| search_latency_ms | INT       | 检索耗时         |
| llm_latency_ms    | INT       | LLM 耗时       |
| total_latency_ms  | INT       | 总耗时          |
| llm_error         | TEXT      | LLM 错误       |
| created_at        | TIMESTAMP | 创建时间         |

model_config_snapshot 来源：

```txt
model_config_snapshot 不是来自数据库表。
它来自当前应用运行时配置，例如 .env、pydantic-settings、app/core/config.py，以及 embedding_service / llm_service 初始化时实际使用的参数。
它用于记录这次 query 当时生效的模型配置，避免后续修改模型后，历史查询无法判断当时用了哪个 provider、model 和参数。
不要在 model_config_snapshot 中保存 API key、secret、token 等敏感信息。
```

示例：

```json
{
  "embedding": {
    "provider": "tongyi",
    "model": "tongyi-embedding-vision-plus-2026-03-06",
    "dimension": 1536
  },
  "llm": {
    "provider": "zhipu",
    "model": "glm-configured-model",
    "temperature": 0.2,
    "max_tokens": 1024
  }
}
```

answer_prompt_version 来源：

```txt
answer_prompt_version 不是来自提示词表。
MVP 阶段它由 app/services/prompt_builder.py 中的 ANSWER_PROMPT_VERSION 常量定义。
该字段只记录主回答 prompt 的版本，例如 rag_qa_v1，不表示系统里所有提示词都是版本 1。
调用链应使用 prompt_builder.build_answer_prompt(...) 返回的 version 写入该字段。
如果本次没有实际构建主回答 prompt，例如 use_llm=false 或无召回内容直接拒答，则 answer_prompt_version 和 answer_prompt_text 都应为空。
```

---

## 6.5 rag_query_candidates

表用途：

```txt
记录每次问题检索到的候选 chunk。
用于调试、失败分析和检索效果评估。
```

```sql
CREATE TABLE rag_query_candidates (
  id BIGSERIAL PRIMARY KEY,

  query_log_id BIGINT NOT NULL,

  chunk_id BIGINT,
  parent_chunk_id BIGINT,
  document_id BIGINT,
  document_version_id BIGINT,

  rank INT,
  vector_rank INT,
  keyword_rank INT,
  trgm_rank INT,

  vector_score FLOAT,
  keyword_score FLOAT,
  trgm_score FLOAT,
  final_score FLOAT,

  selected_for_prompt BOOLEAN DEFAULT false,

  document_name_snapshot TEXT,
  section_title_snapshot TEXT,
  content_snapshot TEXT,

  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_query_candidates IS '查询候选 chunk 表，保存每次检索命中的 chunk 快照';
COMMENT ON COLUMN rag_query_candidates.id IS '候选记录主键 ID';
COMMENT ON COLUMN rag_query_candidates.query_log_id IS '所属查询日志 ID';
COMMENT ON COLUMN rag_query_candidates.chunk_id IS '命中的 child chunk ID';
COMMENT ON COLUMN rag_query_candidates.parent_chunk_id IS '命中 child 对应的 parent chunk ID';
COMMENT ON COLUMN rag_query_candidates.document_id IS '所属文档 ID';
COMMENT ON COLUMN rag_query_candidates.document_version_id IS '所属文档版本 ID';
COMMENT ON COLUMN rag_query_candidates.rank IS '融合排序后的排名';
COMMENT ON COLUMN rag_query_candidates.vector_rank IS '向量检索排名';
COMMENT ON COLUMN rag_query_candidates.keyword_rank IS '全文检索排名';
COMMENT ON COLUMN rag_query_candidates.trgm_rank IS '模糊检索排名';
COMMENT ON COLUMN rag_query_candidates.vector_score IS '向量相似度分数';
COMMENT ON COLUMN rag_query_candidates.keyword_score IS '关键词检索分数';
COMMENT ON COLUMN rag_query_candidates.trgm_score IS '模糊匹配分数';
COMMENT ON COLUMN rag_query_candidates.final_score IS '融合后的最终分数';
COMMENT ON COLUMN rag_query_candidates.selected_for_prompt IS '是否最终进入 prompt';
COMMENT ON COLUMN rag_query_candidates.document_name_snapshot IS '当时的文档名快照，避免后续文档改名影响历史记录';
COMMENT ON COLUMN rag_query_candidates.section_title_snapshot IS '当时的章节标题快照';
COMMENT ON COLUMN rag_query_candidates.content_snapshot IS '当时命中的 chunk 内容快照';
COMMENT ON COLUMN rag_query_candidates.created_at IS '候选记录创建时间';
```

字段说明：

| 字段                     | 类型        | 说明          |
| ---------------------- | --------- | ----------- |
| id                     | BIGSERIAL | 主键          |
| query_log_id           | BIGINT    | 查询日志        |
| chunk_id               | BIGINT    | 命中 chunk    |
| parent_chunk_id        | BIGINT    | 父 chunk     |
| document_id            | BIGINT    | 文档          |
| document_version_id    | BIGINT    | 文档版本        |
| rank                   | INT       | 最终排名        |
| vector_rank            | INT       | 向量排名        |
| keyword_rank           | INT       | 关键词排名       |
| trgm_rank              | INT       | 模糊匹配排名      |
| vector_score           | FLOAT     | 向量分数        |
| keyword_score          | FLOAT     | 关键词分数       |
| trgm_score             | FLOAT     | 模糊分数        |
| final_score            | FLOAT     | 综合分数        |
| selected_for_prompt    | BOOLEAN   | 是否进入 prompt |
| document_name_snapshot | TEXT      | 文档名快照       |
| section_title_snapshot | TEXT      | 章节快照        |
| content_snapshot       | TEXT      | 内容快照        |
| created_at             | TIMESTAMP | 创建时间        |

---

## 6.6 rag_feedback

表用途：

```txt
记录用户对回答的反馈。
用户点踩时，可自动生成失败案例。
```

```sql
CREATE TABLE rag_feedback (
  id BIGSERIAL PRIMARY KEY,

  query_log_id BIGINT NOT NULL,

  rating TEXT NOT NULL,
  reason TEXT,
  comment TEXT,

  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_feedback IS '用户反馈表，记录用户对回答是否满意及原因';
COMMENT ON COLUMN rag_feedback.id IS '反馈主键 ID';
COMMENT ON COLUMN rag_feedback.query_log_id IS '所属查询日志 ID';
COMMENT ON COLUMN rag_feedback.rating IS '反馈结果，HELPFUL 或 NOT_HELPFUL';
COMMENT ON COLUMN rag_feedback.reason IS '反馈原因，例如 WRONG_SOURCE、INCOMPLETE、TOO_VERBOSE';
COMMENT ON COLUMN rag_feedback.comment IS '用户补充说明';
COMMENT ON COLUMN rag_feedback.created_at IS '反馈创建时间';
```

字段说明：

| 字段           | 类型        | 说明                    |
| ------------ | --------- | --------------------- |
| id           | BIGSERIAL | 反馈 ID                 |
| query_log_id | BIGINT    | 查询日志                  |
| rating       | TEXT      | HELPFUL / NOT_HELPFUL |
| reason       | TEXT      | 反馈原因                  |
| comment      | TEXT      | 补充说明                  |
| created_at   | TIMESTAMP | 创建时间                  |

rating 枚举：

```txt
HELPFUL
NOT_HELPFUL
```

reason 枚举：

```txt
WRONG_ANSWER
WRONG_SOURCE
INCOMPLETE
TOO_VERBOSE
NOT_FOUND
OTHER
```

---

## 6.7 rag_failure_cases

表用途：

```txt
统一失败案例池。
所有来源的失败最终进入该表。
来源包括用户反馈、人工调试、测试集失败、自动规则。
```

```sql
CREATE TABLE rag_failure_cases (
  id BIGSERIAL PRIMARY KEY,

  query_log_id BIGINT,

  source_type TEXT NOT NULL,
  source_ref_id BIGINT,
  source_reason TEXT,
  source_payload JSONB,

  primary_failure_type TEXT,

  analysis_note TEXT,
  fix_plan TEXT,

  status TEXT NOT NULL DEFAULT 'OPEN',
  priority INT DEFAULT 3,

  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  fixed_at TIMESTAMP
);

COMMENT ON TABLE rag_failure_cases IS '统一失败案例表，用于沉淀和跟踪 RAG 失败问题';
COMMENT ON COLUMN rag_failure_cases.id IS '失败案例主键 ID';
COMMENT ON COLUMN rag_failure_cases.query_log_id IS '关联的查询日志 ID，可为空，日志归档后失败案例仍需保留';
COMMENT ON COLUMN rag_failure_cases.source_type IS '失败来源，USER_FEEDBACK、MANUAL_DEBUG、EVAL_RUN、AUTO_RULE';
COMMENT ON COLUMN rag_failure_cases.source_ref_id IS '来源记录 ID，逻辑外键；USER_FEEDBACK=rag_feedback.id，EVAL_RUN=rag_eval_results.id，MANUAL_DEBUG/AUTO_RULE 通常为空';
COMMENT ON COLUMN rag_failure_cases.source_reason IS '来源给出的原始原因';
COMMENT ON COLUMN rag_failure_cases.source_payload IS '来源数据快照，JSON 格式';
COMMENT ON COLUMN rag_failure_cases.primary_failure_type IS '人工确认后的主要失败类型';
COMMENT ON COLUMN rag_failure_cases.analysis_note IS '人工分析备注';
COMMENT ON COLUMN rag_failure_cases.fix_plan IS '修复计划';
COMMENT ON COLUMN rag_failure_cases.status IS '处理状态，OPEN、ANALYZING、FIXED、WONT_FIX';
COMMENT ON COLUMN rag_failure_cases.priority IS '优先级，1 最高，5 最低';
COMMENT ON COLUMN rag_failure_cases.created_at IS '失败案例创建时间';
COMMENT ON COLUMN rag_failure_cases.updated_at IS '失败案例更新时间';
COMMENT ON COLUMN rag_failure_cases.fixed_at IS '修复完成时间';
```

字段说明：

| 字段                   | 类型        | 说明      |
| -------------------- | --------- | ------- |
| id                   | BIGSERIAL | 失败案例 ID |
| query_log_id         | BIGINT    | 查询日志，可为空 |
| source_type          | TEXT      | 来源类型    |
| source_ref_id        | BIGINT    | 来源记录 ID，含义由 source_type 决定 |
| source_reason        | TEXT      | 来源原因    |
| source_payload       | JSONB     | 来源快照    |
| primary_failure_type | TEXT      | 失败类型    |
| analysis_note        | TEXT      | 分析备注    |
| fix_plan             | TEXT      | 修复计划    |
| status               | TEXT      | 状态      |
| priority             | INT       | 优先级     |
| created_at           | TIMESTAMP | 创建时间    |
| updated_at           | TIMESTAMP | 更新时间    |
| fixed_at             | TIMESTAMP | 修复时间    |

source_type 枚举：

```txt
USER_FEEDBACK：用户反馈触发，source_ref_id=rag_feedback.id。
MANUAL_DEBUG：人工调试触发，source_ref_id 通常为空，query_log_id 记录关联查询。
EVAL_RUN：测试集失败触发，source_ref_id=rag_eval_results.id。
AUTO_RULE：系统规则触发，source_ref_id 通常为空，规则详情写入 source_payload。
```

primary_failure_type 枚举：

```txt
RETRIEVAL_NO_RECALL
RETRIEVAL_LOW_RANK
CHUNK_INCOMPLETE
CONTEXT_MISSING
PROMPT_SELECTION_WRONG
GENERATION_WRONG
HALLUCINATION
OUTDATED_DOCUMENT
AMBIGUOUS_QUESTION
UX_BAD_FORMAT
LOW_CONFIDENCE_RETRIEVAL
LLM_ERROR
```

status 枚举：

```txt
OPEN
ANALYZING
FIXED
WONT_FIX
```

---

## 6.8 rag_eval_cases

表用途：

```txt
保存测试问题。
自动生成或转入的问题先进入草稿状态。
只有人工审核通过的 ACTIVE 用例才参与评测。
用于评估不同切片策略、检索策略、prompt 策略的效果。
```

```sql
CREATE TABLE rag_eval_cases (
  id BIGSERIAL PRIMARY KEY,

  question TEXT NOT NULL,
  expected_answer TEXT,

  case_type TEXT NOT NULL DEFAULT 'CORE_RULE',
  status TEXT NOT NULL DEFAULT 'DRAFT',
  priority INT DEFAULT 3,

  created_from TEXT NOT NULL DEFAULT 'MANUAL',
  source_ref_id BIGINT,
  source_payload JSONB,

  created_by TEXT,
  reviewed_by TEXT,
  review_note TEXT,
  reviewed_at TIMESTAMP,
  activated_at TIMESTAMP,

  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),

  CONSTRAINT chk_rag_eval_cases_status
    CHECK (status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'REJECTED')),

  CONSTRAINT chk_rag_eval_cases_created_from
    CHECK (created_from IN (
      'MANUAL',
      'DOCUMENT_GENERATED',
      'QUERY_LOG',
      'USER_FEEDBACK',
      'FAILURE_CASE',
      'CSV_IMPORT'
    ))
);

COMMENT ON TABLE rag_eval_cases IS 'RAG 测试问题集表，包含草稿、审核、启用和停用状态';
COMMENT ON COLUMN rag_eval_cases.id IS '测试用例主键 ID';
COMMENT ON COLUMN rag_eval_cases.question IS '测试问题，来自人工维护、线上查询或失败案例转入';
COMMENT ON COLUMN rag_eval_cases.expected_answer IS '期望答案要点，人工根据权威资料填写；可为空，空值表示只评估检索命中';
COMMENT ON COLUMN rag_eval_cases.case_type IS '测试类型，CORE_RULE、FREQUENT_QUERY、EDGE_CASE、FAILURE_REGRESSION';
COMMENT ON COLUMN rag_eval_cases.status IS '状态，DRAFT 待审核，ACTIVE 参与评测，INACTIVE 停用，REJECTED 拒绝入库';
COMMENT ON COLUMN rag_eval_cases.priority IS '优先级，1 最高，5 最低';
COMMENT ON COLUMN rag_eval_cases.created_from IS '来源，MANUAL、DOCUMENT_GENERATED、QUERY_LOG、USER_FEEDBACK、FAILURE_CASE、CSV_IMPORT';
COMMENT ON COLUMN rag_eval_cases.source_ref_id IS '来源记录 ID，逻辑外键；QUERY_LOG=rag_query_logs.id，USER_FEEDBACK=rag_feedback.id，FAILURE_CASE=rag_failure_cases.id，DOCUMENT_GENERATED=rag_chunks.id(PARENT)，MANUAL/CSV_IMPORT 通常为空';
COMMENT ON COLUMN rag_eval_cases.source_payload IS '来源快照，例如原始 query、failure case、生成依据 chunk、候选答案';
COMMENT ON COLUMN rag_eval_cases.created_by IS '创建人或导入任务标识，可为空';
COMMENT ON COLUMN rag_eval_cases.reviewed_by IS '审核人，可为空';
COMMENT ON COLUMN rag_eval_cases.review_note IS '审核备注或拒绝原因';
COMMENT ON COLUMN rag_eval_cases.reviewed_at IS '审核时间';
COMMENT ON COLUMN rag_eval_cases.activated_at IS '首次启用时间';
COMMENT ON COLUMN rag_eval_cases.created_at IS '创建时间';
COMMENT ON COLUMN rag_eval_cases.updated_at IS '更新时间';
```

字段说明：

| 字段              | 类型        | 说明      |
| --------------- | --------- | ------- |
| id              | BIGSERIAL | 测试用例 ID |
| question        | TEXT      | 测试问题，来自人工维护、线上查询或失败案例转入 |
| expected_answer | TEXT      | 期望答案要点，人工根据权威资料填写，可为空 |
| case_type       | TEXT      | 用例类型    |
| status          | TEXT      | 状态      |
| priority        | INT       | 优先级     |
| created_from    | TEXT      | 创建来源    |
| source_ref_id   | BIGINT    | 来源记录 ID，含义由 created_from 决定，见下方对照表 |
| source_payload  | JSONB     | 来源快照    |
| created_by      | TEXT      | 创建人或任务 |
| reviewed_by     | TEXT      | 审核人     |
| review_note     | TEXT      | 审核备注    |
| reviewed_at     | TIMESTAMP | 审核时间    |
| activated_at    | TIMESTAMP | 首次启用时间 |
| created_at      | TIMESTAMP | 创建时间    |
| updated_at      | TIMESTAMP | 更新时间    |

case_type 枚举：

```txt
CORE_RULE
FREQUENT_QUERY
EDGE_CASE
FAILURE_REGRESSION
```

created_from 枚举：

```txt
MANUAL：人工直接录入，source_ref_id 为空。
QUERY_LOG：从线上查询日志转入，source_ref_id=rag_query_logs.id。
USER_FEEDBACK：从用户反馈转入，source_ref_id=rag_feedback.id。
FAILURE_CASE：从失败案例转入，source_ref_id=rag_failure_cases.id。
CSV_IMPORT：通过 CSV/JSON 批量导入，source_ref_id 为空。
DOCUMENT_GENERATED：从文档版本或父 chunk 自动生成候选问题，source_ref_id=rag_chunks.id，且该 chunk 应为 PARENT。
```

source_ref_id 对照：

| created_from       | source_ref_id 含义             | 说明 |
| ------------------ | ---------------------------- | ---- |
| MANUAL             | NULL                         | 人工直接创建，没有上游记录 |
| QUERY_LOG          | rag_query_logs.id            | 从某次查询日志转成测试用例草稿 |
| USER_FEEDBACK      | rag_feedback.id              | 从某条用户反馈转成测试用例草稿 |
| FAILURE_CASE       | rag_failure_cases.id         | 从某个失败案例转成回归测试草稿 |
| CSV_IMPORT         | NULL                         | MVP 不设计导入任务表，导入批次信息放 source_payload |
| DOCUMENT_GENERATED | rag_chunks.id                | 指生成依据的 PARENT chunk；如果不是按单个 chunk 生成，则为空，详情放 source_payload |

status 枚举：

```txt
DRAFT：草稿，自动生成、失败案例转入、线上问题转入后默认状态，不参与评测。
ACTIVE：审核通过，正式参与评测。
INACTIVE：曾经启用过，后来停用，不参与评测。
REJECTED：候选被拒绝，不参与评测。
```

question 来源：

```txt
question 不是从文档自动稳定生成的字段。
MVP 阶段主要来自人工维护，也可以从 rag_query_logs、用户反馈、rag_failure_cases 中挑选后转入。
从线上数据转入时，可以先复制原始用户问题，再由人工改写成稳定、可重复评测的问题。
从文档自动生成时，只生成 DRAFT 候选，不直接参与评测。
```

expected_answer 来源：

```txt
expected_answer 是人工根据权威文档整理的期望答案要点，不是线上 LLM 的回答。
它用于评估最终回答是否覆盖关键事实，不要求和模型输出逐字一致。
如果该用例只评估检索效果，可以不填 expected_answer，只维护 expected_sources。
当 use_llm=true 且 expected_answer 不为空时，才参与回答质量评估。
```

录入方式：

```txt
1. 人工在后台页面或通过 POST /api/v1/rag/eval-cases 创建 DRAFT。
2. 从 query log 详情页转入 DRAFT：默认带入 rag_query_logs.question，人工补充 expected_answer 和 expected_sources。
3. 从 failure case 转入 DRAFT：用于回归测试，修复后持续验证同类问题不再失败。
4. 从文档章节或 parent chunk 自动生成 DRAFT：系统起草 question、expected_answer 和 expected_sources。
5. 批量导入 CSV/JSON：导入后仍建议人工校对 expected_answer 和 expected_sources。
6. 人工审核通过后 status 改为 ACTIVE，才参与测试集运行。
```

---

## 6.9 rag_eval_expected_sources

表用途：

```txt
保存测试问题期望命中的来源。
不强依赖 chunk_id，因为文档更新后 chunk_id 可能变化。
优先使用 document_id、section_title、expected_keywords 判断命中。
```

```sql
CREATE TABLE rag_eval_expected_sources (
  id BIGSERIAL PRIMARY KEY,

  eval_case_id BIGINT NOT NULL,

  document_id BIGINT,
  document_version_id BIGINT,

  expected_section_title TEXT,
  expected_keywords TEXT[],

  expected_chunk_id BIGINT,

  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_eval_expected_sources IS '测试用例期望来源表，用于判断检索是否命中正确文档或章节';
COMMENT ON COLUMN rag_eval_expected_sources.id IS '期望来源主键 ID';
COMMENT ON COLUMN rag_eval_expected_sources.eval_case_id IS '所属测试用例 ID';
COMMENT ON COLUMN rag_eval_expected_sources.document_id IS '期望命中的文档 ID';
COMMENT ON COLUMN rag_eval_expected_sources.document_version_id IS '期望命中的文档版本 ID，可为空';
COMMENT ON COLUMN rag_eval_expected_sources.expected_section_title IS '期望命中的章节标题';
COMMENT ON COLUMN rag_eval_expected_sources.expected_keywords IS '期望命中的关键词数组';
COMMENT ON COLUMN rag_eval_expected_sources.expected_chunk_id IS '期望命中的 chunk ID，可选，不建议强依赖';
COMMENT ON COLUMN rag_eval_expected_sources.created_at IS '创建时间';
```

字段说明：

| 字段                     | 类型        | 说明       |
| ---------------------- | --------- | -------- |
| id                     | BIGSERIAL | 主键       |
| eval_case_id           | BIGINT    | 测试用例     |
| document_id            | BIGINT    | 期望文档     |
| document_version_id    | BIGINT    | 期望版本     |
| expected_section_title | TEXT      | 期望章节     |
| expected_keywords      | TEXT[]    | 期望关键词    |
| expected_chunk_id      | BIGINT    | 期望 chunk |
| created_at             | TIMESTAMP | 创建时间     |

---

## 6.10 rag_eval_runs

表用途：

```txt
记录一次测试集运行。
每次调整 chunk 策略、检索权重、prompt 后，都可以运行一次测试集。
```

```sql
CREATE TABLE rag_eval_runs (
  id BIGSERIAL PRIMARY KEY,

  name TEXT,

  search_profile_id BIGINT,
  search_profile_snapshot JSONB,

  search_mode TEXT,
  chunk_strategy TEXT,
  embedding_model TEXT,
  llm_model TEXT,
  use_llm BOOLEAN NOT NULL DEFAULT false,
  run_status TEXT NOT NULL DEFAULT 'RUNNING',
  eval_config JSONB,

  total_cases INT DEFAULT 0,
  passed_cases INT DEFAULT 0,
  failed_cases INT DEFAULT 0,

  created_at TIMESTAMP DEFAULT now(),
  finished_at TIMESTAMP,

  CONSTRAINT chk_rag_eval_runs_status
    CHECK (run_status IN ('RUNNING', 'COMPLETED', 'FAILED'))
);

COMMENT ON TABLE rag_eval_runs IS '测试集运行记录表，保存一次评估运行的整体结果';
COMMENT ON COLUMN rag_eval_runs.id IS '评估运行主键 ID';
COMMENT ON COLUMN rag_eval_runs.name IS '评估运行名称';
COMMENT ON COLUMN rag_eval_runs.search_profile_id IS '使用的搜索配置 ID';
COMMENT ON COLUMN rag_eval_runs.search_profile_snapshot IS '运行时搜索配置快照';
COMMENT ON COLUMN rag_eval_runs.search_mode IS '检索模式';
COMMENT ON COLUMN rag_eval_runs.chunk_strategy IS 'chunk 策略说明';
COMMENT ON COLUMN rag_eval_runs.embedding_model IS 'embedding 模型';
COMMENT ON COLUMN rag_eval_runs.llm_model IS 'LLM 模型';
COMMENT ON COLUMN rag_eval_runs.use_llm IS '本次评估是否调用 LLM';
COMMENT ON COLUMN rag_eval_runs.run_status IS '运行状态，RUNNING、COMPLETED、FAILED';
COMMENT ON COLUMN rag_eval_runs.eval_config IS '评估规则快照，例如通过标准、answer judge 类型';
COMMENT ON COLUMN rag_eval_runs.total_cases IS '总测试用例数';
COMMENT ON COLUMN rag_eval_runs.passed_cases IS '通过数量';
COMMENT ON COLUMN rag_eval_runs.failed_cases IS '失败数量';
COMMENT ON COLUMN rag_eval_runs.created_at IS '创建时间';
COMMENT ON COLUMN rag_eval_runs.finished_at IS '运行结束时间';
```

字段说明：

| 字段                | 类型        | 说明           |
| ----------------- | --------- | ------------ |
| id                | BIGSERIAL | 运行 ID        |
| name              | TEXT      | 运行名称         |
| search_profile_id | BIGINT    | 搜索配置         |
| search_profile_snapshot | JSONB | 搜索配置快照      |
| search_mode       | TEXT      | 检索模式         |
| chunk_strategy    | TEXT      | chunk 策略     |
| embedding_model   | TEXT      | embedding 模型 |
| llm_model         | TEXT      | LLM 模型       |
| use_llm           | BOOLEAN   | 是否调用 LLM     |
| run_status        | TEXT      | 运行状态         |
| eval_config       | JSONB     | 评估配置快照       |
| total_cases       | INT       | 总数           |
| passed_cases      | INT       | 通过数          |
| failed_cases      | INT       | 失败数          |
| created_at        | TIMESTAMP | 创建时间         |
| finished_at       | TIMESTAMP | 结束时间         |

---

## 6.11 rag_eval_results

表用途：

```txt
记录每个测试用例在某次运行中的结果。
如果测试失败，可自动生成失败案例。
```

```sql
CREATE TABLE rag_eval_results (
  id BIGSERIAL PRIMARY KEY,

  eval_run_id BIGINT NOT NULL,
  eval_case_id BIGINT NOT NULL,
  query_log_id BIGINT,

  top1_hit BOOLEAN DEFAULT false,
  top5_hit BOOLEAN DEFAULT false,
  retrieval_pass BOOLEAN DEFAULT false,
  answer_pass BOOLEAN,
  answer_score FLOAT,
  answer_eval_detail JSONB,

  failure_reason TEXT,
  failure_created BOOLEAN DEFAULT false,
  failure_case_id BIGINT,

  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_eval_results IS '测试用例运行结果表，保存每个测试问题的命中情况和回答结果';
COMMENT ON COLUMN rag_eval_results.id IS '评估结果主键 ID';
COMMENT ON COLUMN rag_eval_results.eval_run_id IS '所属评估运行 ID';
COMMENT ON COLUMN rag_eval_results.eval_case_id IS '所属测试用例 ID';
COMMENT ON COLUMN rag_eval_results.query_log_id IS '本次测试对应的查询日志 ID';
COMMENT ON COLUMN rag_eval_results.top1_hit IS '期望来源是否命中 Top 1';
COMMENT ON COLUMN rag_eval_results.top5_hit IS '期望来源是否命中 Top 5';
COMMENT ON COLUMN rag_eval_results.retrieval_pass IS '检索是否通过评估';
COMMENT ON COLUMN rag_eval_results.answer_pass IS '回答是否通过评估，未启用 LLM 或无 expected_answer 时可为空';
COMMENT ON COLUMN rag_eval_results.answer_score IS '回答质量评分，可由规则或 LLM judge 生成';
COMMENT ON COLUMN rag_eval_results.answer_eval_detail IS '回答评估详情快照';
COMMENT ON COLUMN rag_eval_results.failure_reason IS '失败原因';
COMMENT ON COLUMN rag_eval_results.failure_created IS '是否已生成失败案例';
COMMENT ON COLUMN rag_eval_results.failure_case_id IS '关联生成的失败案例 ID';
COMMENT ON COLUMN rag_eval_results.created_at IS '创建时间';
```

字段说明：

| 字段              | 类型        | 说明       |
| --------------- | --------- | -------- |
| id              | BIGSERIAL | 主键       |
| eval_run_id     | BIGINT    | 运行 ID    |
| eval_case_id    | BIGINT    | 测试用例     |
| query_log_id    | BIGINT    | 查询日志     |
| top1_hit        | BOOLEAN   | Top1 命中  |
| top5_hit        | BOOLEAN   | Top5 命中  |
| retrieval_pass  | BOOLEAN   | 检索通过     |
| answer_pass     | BOOLEAN   | 回答通过     |
| answer_score    | FLOAT     | 回答评分     |
| answer_eval_detail | JSONB  | 回答评估详情   |
| failure_reason  | TEXT      | 失败原因     |
| failure_created | BOOLEAN   | 是否生成失败案例 |
| failure_case_id | BIGINT    | 失败案例 ID   |
| created_at      | TIMESTAMP | 创建时间     |

---

## 6.12 rag_search_profiles

表用途：

```txt
保存检索配置。
用于调试不同搜索权重和 top_k 参数。
```

```sql
CREATE TABLE rag_search_profiles (
  id BIGSERIAL PRIMARY KEY,

  name TEXT NOT NULL,
  description TEXT,

  search_mode TEXT NOT NULL DEFAULT 'HYBRID',

  vector_top_k INT DEFAULT 20,
  keyword_top_k INT DEFAULT 20,
  trgm_top_k INT DEFAULT 20,
  final_top_k INT DEFAULT 5,

  vector_weight FLOAT DEFAULT 0.65,
  keyword_weight FLOAT DEFAULT 0.25,
  trgm_weight FLOAT DEFAULT 0.10,

  min_final_score FLOAT DEFAULT 0.55,

  is_default BOOLEAN DEFAULT false,

  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),

  CONSTRAINT chk_rag_search_profiles_mode
    CHECK (search_mode IN ('VECTOR', 'KEYWORD', 'TRIGRAM', 'HYBRID')),
  CONSTRAINT chk_rag_search_profiles_top_k
    CHECK (
      vector_top_k >= 0
      AND keyword_top_k >= 0
      AND trgm_top_k >= 0
      AND final_top_k > 0
    ),
  CONSTRAINT chk_rag_search_profiles_weights
    CHECK (
      vector_weight >= 0
      AND keyword_weight >= 0
      AND trgm_weight >= 0
    ),
  CONSTRAINT chk_rag_search_profiles_min_score
    CHECK (min_final_score >= 0 AND min_final_score <= 1)
);

COMMENT ON TABLE rag_search_profiles IS '搜索配置表，用于配置混合检索权重、top_k、阈值等参数';
COMMENT ON COLUMN rag_search_profiles.id IS '搜索配置主键 ID';
COMMENT ON COLUMN rag_search_profiles.name IS '配置名称';
COMMENT ON COLUMN rag_search_profiles.description IS '配置说明';
COMMENT ON COLUMN rag_search_profiles.search_mode IS '检索模式，VECTOR、KEYWORD、TRIGRAM、HYBRID';
COMMENT ON COLUMN rag_search_profiles.vector_top_k IS '向量检索候选数量';
COMMENT ON COLUMN rag_search_profiles.keyword_top_k IS '全文检索候选数量';
COMMENT ON COLUMN rag_search_profiles.trgm_top_k IS '模糊检索候选数量';
COMMENT ON COLUMN rag_search_profiles.final_top_k IS '最终进入 prompt 的 chunk 数量';
COMMENT ON COLUMN rag_search_profiles.vector_weight IS '向量分数权重';
COMMENT ON COLUMN rag_search_profiles.keyword_weight IS '关键词分数权重';
COMMENT ON COLUMN rag_search_profiles.trgm_weight IS '模糊匹配分数权重';
COMMENT ON COLUMN rag_search_profiles.min_final_score IS '最低可信分数，低于该值可拒答';
COMMENT ON COLUMN rag_search_profiles.is_default IS '是否默认配置';
COMMENT ON COLUMN rag_search_profiles.created_at IS '创建时间';
COMMENT ON COLUMN rag_search_profiles.updated_at IS '更新时间';
```

字段说明：

| 字段              | 类型        | 说明     |
| --------------- | --------- | ------ |
| id              | BIGSERIAL | 配置 ID  |
| name            | TEXT      | 配置名称   |
| description     | TEXT      | 说明     |
| search_mode     | TEXT      | 检索模式   |
| vector_top_k    | INT       | 向量候选数  |
| keyword_top_k   | INT       | 关键词候选数 |
| trgm_top_k      | INT       | 模糊候选数  |
| final_top_k     | INT       | 最终数量   |
| vector_weight   | FLOAT     | 向量权重   |
| keyword_weight  | FLOAT     | 关键词权重  |
| trgm_weight     | FLOAT     | 模糊权重   |
| min_final_score | FLOAT     | 最低可信分  |
| is_default      | BOOLEAN   | 是否默认   |
| created_at      | TIMESTAMP | 创建时间   |
| updated_at      | TIMESTAMP | 更新时间   |

索引与默认配置约束：

```sql
CREATE UNIQUE INDEX uq_rag_search_profiles_default
ON rag_search_profiles(is_default)
WHERE is_default = true;
```

说明：

```txt
同一时间只允许一个默认搜索配置。
权重可以不强制相加等于 1，但服务层应在使用时归一化，避免配置错误影响分数。
```

---

# 7. 接口设计

## 7.1 文档上传

```http
POST /api/v1/documents/upload
```

功能：

```txt
上传新文档。
如果是第一次上传，创建 rag_documents 和 rag_document_versions。
处理成功后，current_version_id 指向该版本。
```

请求：

```txt
multipart/form-data
file: 文件
```

响应：

```json
{
  "document_id": 1,
  "version_id": 1,
  "status": "COMPLETED",
  "chunk_count": 36
}
```

---

## 7.2 文档更新

```http
POST /api/v1/documents/{document_id}/versions/upload
```

功能：

```txt
为已有文档上传新版本。
新版本处理成功后才切换 current_version_id。
```

响应：

```json
{
  "document_id": 1,
  "version_id": 2,
  "status": "COMPLETED",
  "chunk_count": 42,
  "current_version_id": 2
}
```

---

## 7.3 文档列表

```http
GET /api/v1/documents
```

响应：

```json
{
  "items": [
    {
      "id": 1,
      "name": "公司报销制度.pdf",
      "file_type": "pdf",
      "file_size": 102400,
      "current_version_id": 2,
      "status": "ACTIVE",
      "created_at": "2026-06-01T10:00:00",
      "updated_at": "2026-06-01T11:00:00"
    }
  ]
}
```

---

## 7.4 文档详情

```http
GET /api/v1/documents/{document_id}
```

响应：

```json
{
  "id": 1,
  "name": "公司报销制度.pdf",
  "file_type": "pdf",
  "current_version_id": 2,
  "versions": [
    {
      "id": 1,
      "version_no": 1,
      "status": "COMPLETED",
      "chunk_count": 36
    },
    {
      "id": 2,
      "version_no": 2,
      "status": "COMPLETED",
      "chunk_count": 42
    }
  ]
}
```

---

## 7.5 文档 chunk 列表

```http
GET /api/v1/documents/{document_id}/chunks?version=current&chunk_type=CHILD
```

响应：

```json
{
  "items": [
    {
      "id": 12,
      "chunk_type": "CHILD",
      "parent_chunk_id": 3,
      "chunk_index": 1,
      "child_index": 0,
      "section_title": "差旅报销",
      "content": "差旅报销需要提供发票、行程单、审批记录。"
    }
  ]
}
```

---

## 7.6 删除文档

```http
DELETE /api/v1/documents/{document_id}
```

说明：

```txt
MVP 可以软删除，将 rag_documents.status 改为 DELETED。
正常检索时过滤 DELETED 文档。
```

响应：

```json
{
  "success": true
}
```

---

## 7.7 RAG 调试查询

```http
POST /api/v1/rag/debug-query
```

功能：

```txt
统一调试接口。
use_llm=false 时，只返回检索结果。
use_llm=true 时，返回检索结果、prompt、LLM 回答。
```

请求：

```json
{
  "question": "差旅报销需要什么材料？",
  "search_profile_id": 1,
  "use_llm": true
}
```

响应：

```json
{
  "query_log_id": 1001,
  "question": "差旅报销需要什么材料？",
  "search": {
    "search_mode": "HYBRID",
    "candidates": [],
    "selected_chunks": []
  },
  "llm": {
    "used": true,
    "prompt": "你是一个知识库问答助手……",
    "answer": "差旅报销需要提供发票、行程单、审批记录。",
    "model": "zhipu-configured-model",
    "latency_ms": 2300,
    "error": null
  }
}
```

---

## 7.8 查询历史

```http
GET /api/v1/rag/query-logs
```

查询参数：

```txt
keyword
use_llm
start_date
end_date
page
page_size
```

响应：

```json
{
  "items": [
    {
      "id": 1001,
      "question": "差旅报销需要什么材料？",
      "answer": "差旅报销需要提供……",
      "max_score": 0.86,
      "total_latency_ms": 3200,
      "created_at": "2026-06-01T12:00:00"
    }
  ]
}
```

---

## 7.9 查询详情

```http
GET /api/v1/rag/query-logs/{query_log_id}
```

功能：

```txt
展示某次查询的完整链路。
包括 question、candidates、selected chunks、prompt、answer、feedback、failure_case。
```

---

## 7.10 用户反馈

```http
POST /api/v1/rag/query-logs/{query_log_id}/feedback
```

请求：

```json
{
  "rating": "NOT_HELPFUL",
  "reason": "WRONG_SOURCE",
  "comment": "引用来源不对"
}
```

响应：

```json
{
  "feedback_id": 12,
  "failure_case_id": 5
}
```

说明：

```txt
如果 rating=NOT_HELPFUL，自动创建 rag_failure_cases。
source_type=USER_FEEDBACK。
```

---

## 7.11 手动创建失败案例

```http
POST /api/v1/rag/query-logs/{query_log_id}/failure-case
```

请求：

```json
{
  "source_reason": "调试时发现没有召回正确 chunk",
  "primary_failure_type": "RETRIEVAL_NO_RECALL",
  "analysis_note": "问题应该命中差旅报销章节，但返回了餐饮报销"
}
```

响应：

```json
{
  "failure_case_id": 6
}
```

---

## 7.12 失败案例列表

```http
GET /api/v1/rag/failure-cases
```

查询参数：

```txt
source_type
primary_failure_type
status
priority
page
page_size
```

---

## 7.13 更新失败案例

```http
PATCH /api/v1/rag/failure-cases/{failure_case_id}
```

请求：

```json
{
  "primary_failure_type": "CHUNK_INCOMPLETE",
  "analysis_note": "chunk 被切断，缺少后半句",
  "fix_plan": "调整 child chunk_size 至 500，overlap 调整为 100",
  "status": "ANALYZING",
  "priority": 2
}
```

---

## 7.14 测试用例列表

```http
GET /api/v1/rag/eval-cases
```

查询参数：

```txt
status
created_from
case_type
priority
needs_review
page
page_size
```

---

## 7.15 创建测试用例

```http
POST /api/v1/rag/eval-cases
```

请求：

```json
{
  "question": "差旅报销需要什么材料？",
  "expected_answer": "需要发票、行程单、审批记录。",
  "case_type": "CORE_RULE",
  "status": "DRAFT",
  "priority": 1,
  "created_from": "MANUAL",
  "source_ref_id": null,
  "source_payload": null,
  "expected_sources": [
    {
      "document_id": 1,
      "expected_section_title": "差旅报销",
      "expected_keywords": ["发票", "行程单", "审批记录"]
    }
  ]
}
```

说明：

```txt
question 由人工录入，或者从 query log / failure case 转入后人工确认。
expected_answer 由人工根据权威文档填写答案要点，不直接使用线上 LLM 回答。
如果只做检索评估，expected_answer 可以为空，但应填写 expected_sources。
创建接口默认只创建 DRAFT，不直接进入 ACTIVE。
created_from=MANUAL 时 source_ref_id 可以为空。
从 query log 转入时 created_from=QUERY_LOG，source_ref_id=rag_query_logs.id。
从 failure case 转入时 created_from=FAILURE_CASE，source_ref_id=rag_failure_cases.id。
```

---

## 7.16 更新测试用例

```http
PATCH /api/v1/rag/eval-cases/{eval_case_id}
```

请求：

```json
{
  "question": "差旅报销需要什么材料？",
  "expected_answer": "需要发票、行程单、审批记录。",
  "case_type": "CORE_RULE",
  "status": "DRAFT",
  "priority": 1,
  "created_from": "MANUAL",
  "source_ref_id": null,
  "source_payload": null,
  "expected_sources": [
    {
      "document_id": 1,
      "expected_section_title": "差旅报销",
      "expected_keywords": ["发票", "行程单", "审批记录"]
    }
  ]
}
```

说明：

```txt
更新 expected_sources 时建议整体替换该 case 的期望来源列表。
编辑 DRAFT 时可以修改 question、expected_answer、expected_sources。
ACTIVE 用例原则上不直接改标准答案，建议复制为新 DRAFT 或先停用旧用例。
停用用例时只修改 status=INACTIVE，不直接删除历史用例。
```

---

## 7.17 从查询日志创建测试用例草稿

```http
POST /api/v1/rag/query-logs/{query_log_id}/eval-case-draft
```

请求：

```json
{
  "case_type": "FREQUENT_QUERY",
  "priority": 3
}
```

说明：

```txt
该接口只创建 DRAFT。
默认带入 rag_query_logs.question。
expected_answer 和 expected_sources 需要人工补充或确认。
created_from=QUERY_LOG。
source_ref_id=rag_query_logs.id。
source_payload 保存原始 query、检索摘要、回答摘要和用户反馈摘要。
```

---

## 7.18 从失败案例创建测试用例草稿

```http
POST /api/v1/rag/failure-cases/{failure_case_id}/eval-case-draft
```

请求：

```json
{
  "question": "差旅报销需要什么材料？",
  "case_type": "FAILURE_REGRESSION",
  "priority": 2
}
```

说明：

```txt
该接口只创建 DRAFT。
用于把已确认的问题沉淀为回归测试。
如果 failure case 关联了 query_log，则默认带入 query_log.question。
如果 failure case 没有关联 query_log，则请求体必须提供 question。
expected_answer 和 expected_sources 必须人工补充或确认。
created_from=FAILURE_CASE。
source_ref_id=rag_failure_cases.id。
source_payload 保存失败类型、失败原因、分析备注和修复计划。
```

---

## 7.19 从文档生成测试用例草稿

```http
POST /api/v1/rag/document-versions/{document_version_id}/eval-case-drafts
```

请求：

```json
{
  "case_type": "CORE_RULE",
  "max_cases_per_parent_chunk": 2,
  "priority": 3
}
```

说明：

```txt
该接口只生成 DRAFT 候选。
系统可以基于 PARENT chunk 起草 question、expected_answer 和 expected_sources。
expected_answer 必须能回到原文依据，不能直接信任生成结果。
人工审核时需要确认问题稳定、答案要点正确、expected_sources 可用于检索命中判断。
created_from=DOCUMENT_GENERATED。
source_ref_id=rag_chunks.id，且该 chunk 应为 PARENT；如果一次生成多个 chunk 的候选，则详细来源写入 source_payload。
```

---

## 7.20 审核测试用例

```http
POST /api/v1/rag/eval-cases/{eval_case_id}/review
```

请求：

```json
{
  "action": "APPROVE",
  "review_note": "答案要点和来源已核对",
  "reviewed_by": "admin"
}
```

说明：

```txt
action=APPROVE 时，status 改为 ACTIVE，写入 reviewed_by、reviewed_at、activated_at。
action=REJECT 时，status 改为 REJECTED，review_note 必填。
审核通过前必须确认 question、expected_answer、expected_sources。
如果 expected_answer 为空，则表示该用例只做检索评估，但 expected_sources 必须存在。
```

---

## 7.21 运行测试集

```http
POST /api/v1/rag/eval-runs
```

请求：

```json
{
  "name": "调整混合检索权重后的测试",
  "search_profile_id": 1,
  "use_llm": false
}
```

响应：

```json
{
  "eval_run_id": 10,
  "run_status": "COMPLETED",
  "total_cases": 20,
  "passed_cases": 16,
  "failed_cases": 4
}
```

---

## 7.22 测试运行列表

```http
GET /api/v1/rag/eval-runs
```

查询参数：

```txt
start_date
end_date
search_profile_id
use_llm
page
page_size
```

响应：

```json
{
  "items": [
    {
      "id": 10,
      "name": "调整混合检索权重后的测试",
      "run_status": "COMPLETED",
      "total_cases": 20,
      "passed_cases": 16,
      "failed_cases": 4,
      "created_at": "2026-06-01T12:00:00",
      "finished_at": "2026-06-01T12:01:10"
    }
  ]
}
```

---

## 7.23 测试运行详情

```http
GET /api/v1/rag/eval-runs/{eval_run_id}
```

响应：

```json
{
  "id": 10,
  "name": "调整混合检索权重后的测试",
  "search_profile_snapshot": {},
  "total_cases": 20,
  "passed_cases": 16,
  "failed_cases": 4,
  "results": [
    {
      "eval_case_id": 1,
      "question": "差旅报销需要什么材料？",
      "top1_hit": true,
      "top5_hit": true,
      "retrieval_pass": true,
      "answer_pass": true,
      "failure_reason": null,
      "query_log_id": 1001,
      "failure_case_id": null
    }
  ]
}
```

---

## 7.24 搜索配置列表

```http
GET /api/v1/rag/search-profiles
```

---

## 7.25 创建搜索配置

```http
POST /api/v1/rag/search-profiles
```

请求：

```json
{
  "name": "默认混合检索",
  "search_mode": "HYBRID",
  "vector_top_k": 20,
  "keyword_top_k": 20,
  "trgm_top_k": 20,
  "final_top_k": 5,
  "vector_weight": 0.65,
  "keyword_weight": 0.25,
  "trgm_weight": 0.1,
  "min_final_score": 0.55,
  "is_default": true
}
```

---

## 7.26 更新搜索配置

```http
PATCH /api/v1/rag/search-profiles/{search_profile_id}
```

请求字段同创建接口，全部可选。

说明：

```txt
如果修改了历史评估使用过的搜索配置，不影响旧 eval_run 的 search_profile_snapshot。
设置 is_default=true 时，服务层需要在同一事务内取消其他默认配置，配合唯一索引保证只有一个默认配置。
```

---

## 7.27 设置默认搜索配置

```http
POST /api/v1/rag/search-profiles/{search_profile_id}/set-default
```

响应：

```json
{
  "success": true
}
```

---

# 8. 文档入库实现方案

## 8.1 入库主流程

```python
async def ingest_document(file, db, document_id=None):
    file_bytes = await file.read()
    file_hash = sha256(file_bytes)

    if document_id is None:
        document = document_repo.create(
            name=file.filename,
            file_type=detect_file_type(file.filename),
            file_size=len(file_bytes),
        )
    else:
        document = document_repo.get(document_id)

    version_no = document_repo.next_version_no(document.id)

    version = document_repo.create_version(
        document_id=document.id,
        version_no=version_no,
        file_hash=file_hash,
        original_filename=file.filename,
        parser_version=document_parser.version,
        parser_config_snapshot=document_parser.config_snapshot(),
        chunk_strategy_name=chunker.strategy_name,
        chunk_config_snapshot=chunker.config_snapshot(),
        status="PROCESSING",
    )

    try:
        blocks = document_parser.parse(file.filename, file_bytes)

        chunk_groups = chunker.build_parent_child_chunks(
            document=document,
            version=version,
            blocks=blocks,
        )

        for group in chunk_groups:
            group.parent.search_text = build_search_text(group.parent)
            group.parent.search_tsv = build_search_tsv(group.parent.search_text)

            for child in group.children:
                child.embedding = await embedding_service.embed(
                    child.content_with_context
                )
                child.search_text = build_search_text(child)
                child.search_tsv = build_search_tsv(child.search_text)

        created_chunk_count = 0

        with db.transaction():
            for group in chunk_groups:
                parent = chunk_repo.create(group.parent)
                created_chunk_count += 1

                for child in group.children:
                    child.parent_chunk_id = parent.id
                    chunk_repo.create(child)
                    created_chunk_count += 1

            document_repo.mark_version_completed(
                version_id=version.id,
                chunk_count=created_chunk_count,
            )

            document_repo.set_current_version(
                document_id=document.id,
                version_id=version.id,
            )

        return {
            "document_id": document.id,
            "version_id": version.id,
            "status": "COMPLETED",
            "chunk_count": created_chunk_count,
        }

    except Exception as exc:
        document_repo.mark_version_failed(
            version_id=version.id,
            error_message=str(exc),
        )
        chunk_repo.delete_by_version(version.id)
        raise
```

关键点：

```txt
新版本全部处理成功后，才切换 current_version_id。
处理失败时，旧版本仍然可用。
不要在长事务里等待外部 embedding API；先完成解析和向量生成，再用短事务写入 chunks、标记版本完成、切换 current_version_id。
如果处理失败，需要清理该失败版本已写入的临时 chunks，或保证正常检索永远只过滤 current_version_id。
```

---

# 9. Chunk 生成实现方案

## 9.1 Parser 输出 blocks

统一文档解析结果：

```python
@dataclass
class TextBlock:
    text: str
    page_number: int | None
    heading_level: int | None
    is_heading: bool
    start_char: int | None
    end_char: int | None
```

Markdown：

```txt
根据 #、##、### 解析 heading_level。
```

PDF：

```txt
MVP 阶段按页提取文本。
通过正则识别标题。
```

TXT：

```txt
根据空行和中文标题正则识别段落和标题。
```

---

## 9.2 Parent chunk 生成规则

```txt
优先按标题分组。
一个标题下的内容组成一个 parent chunk。
如果 parent 太长，按段落继续拆分。
```

推荐参数：

```txt
parent_chunk_size = 1200 ~ 2000 中文字
```

---

## 9.3 Child chunk 生成规则

```txt
在 parent chunk 内继续切 child chunk。
child chunk 用于 embedding 和检索。
```

推荐参数：

```txt
child_chunk_size = 300 ~ 600 中文字
child_overlap = 60 ~ 100 中文字
```

---

## 9.4 Chunker 伪代码

```python
@dataclass
class ChunkGroup:
    parent: RagChunkCreate
    children: list[RagChunkCreate]


def build_parent_child_chunks(document, version, blocks):
    sections = split_blocks_by_heading(blocks)

    chunk_groups = []
    parent_index = 0
    child_global_index = 0

    for section in sections:
        parent_texts = split_large_section(
            section.text,
            max_size=1600,
        )

        for parent_text in parent_texts:
            parent_chunk = RagChunkCreate(
                document_id=document.id,
                document_version_id=version.id,
                parent_chunk_id=None,
                chunk_type="PARENT",
                chunk_index=parent_index,
                section_title=section.title,
                heading_path=section.heading_path,
                page_start=section.page_start,
                page_end=section.page_end,
                content=parent_text,
                content_with_context=None,
                content_hash=hash_text(parent_text),
                token_count=estimate_tokens(parent_text),
            )

            child_texts = split_with_overlap(
                parent_text,
                chunk_size=500,
                overlap=80,
            )

            children = []

            for child_index, child_text in enumerate(child_texts):
                child_chunk = RagChunkCreate(
                    document_id=document.id,
                    document_version_id=version.id,
                    parent_chunk_id=None,
                    chunk_type="CHILD",
                    chunk_index=child_global_index,
                    child_index=child_index,
                    section_title=section.title,
                    heading_path=section.heading_path,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    content=child_text,
                    content_with_context=build_context_text(
                        document_name=document.name,
                        heading_path=section.heading_path,
                        page_start=section.page_start,
                        content=child_text,
                    ),
                    content_hash=hash_text(child_text),
                    token_count=estimate_tokens(child_text),
                )

                children.append(child_chunk)
                child_global_index += 1

            chunk_groups.append(
                ChunkGroup(
                    parent=parent_chunk,
                    children=children,
                )
            )
            parent_index += 1

    return chunk_groups
```

说明：

```txt
chunker 不生成临时 parent_chunk_id。
parent_chunk_id 只能在 parent chunk 落库拿到真实 ID 后回填。
写入 child 前，repo 层必须校验 parent_chunk_id 指向同一 document_version 下的 PARENT 行。
```

---

# 10. 混合检索实现方案

## 10.1 向量检索 SQL

```sql
SELECT
  c.id AS chunk_id,
  c.parent_chunk_id,
  c.document_id,
  c.document_version_id,
  d.name AS document_name,
  c.section_title,
  c.content,
  1 - (c.embedding <=> :query_embedding) AS vector_score
FROM rag_chunks c
JOIN rag_documents d ON d.id = c.document_id
WHERE c.chunk_type = 'CHILD'
  AND c.embedding IS NOT NULL
  AND d.status = 'ACTIVE'
  AND c.document_version_id = d.current_version_id
ORDER BY c.embedding <=> :query_embedding
LIMIT :vector_top_k;
```

---

## 10.2 全文检索 SQL

```sql
SELECT
  c.id AS chunk_id,
  c.parent_chunk_id,
  c.document_id,
  c.document_version_id,
  d.name AS document_name,
  c.section_title,
  c.content,
  ts_rank_cd(c.search_tsv, plainto_tsquery('simple', :query)) AS keyword_score
FROM rag_chunks c
JOIN rag_documents d ON d.id = c.document_id
WHERE c.chunk_type = 'CHILD'
  AND d.status = 'ACTIVE'
  AND c.document_version_id = d.current_version_id
  AND c.search_tsv @@ plainto_tsquery('simple', :query)
ORDER BY keyword_score DESC
LIMIT :keyword_top_k;
```

中文检索说明：

```txt
plainto_tsquery('simple', :query) 对中文没有真正分词能力。
如果知识库以中文为主，MVP 可以先把全文检索作为辅助召回；正式版本应接入中文分词方案，例如 pg_jieba、外部分词后写入 search_tsv，或使用关键词抽取结果构造 tsquery。
```

---

## 10.3 模糊检索 SQL

```sql
SELECT
  c.id AS chunk_id,
  c.parent_chunk_id,
  c.document_id,
  c.document_version_id,
  d.name AS document_name,
  c.section_title,
  c.content,
  similarity(c.search_text, :query) AS trgm_score
FROM rag_chunks c
JOIN rag_documents d ON d.id = c.document_id
WHERE c.chunk_type = 'CHILD'
  AND d.status = 'ACTIVE'
  AND c.document_version_id = d.current_version_id
  AND c.search_text % :query
ORDER BY trgm_score DESC
LIMIT :trgm_top_k;
```

---

## 10.4 分数融合

```python
def rrf(rank, k=60):
    return 1 / (k + rank)


def search(question, query_embedding, profile):
    vector_rows = []
    keyword_rows = []
    trgm_rows = []

    if profile.search_mode in ("VECTOR", "HYBRID"):
        vector_rows = vector_search(
            question,
            query_embedding,
            profile.vector_top_k,
        )

    if profile.search_mode in ("KEYWORD", "HYBRID"):
        keyword_rows = keyword_search(question, profile.keyword_top_k)

    if profile.search_mode in ("TRIGRAM", "HYBRID"):
        trgm_rows = trigram_search(question, profile.trgm_top_k)

    candidates = {}

    for rank, row in enumerate(vector_rows, start=1):
        cid = row.chunk_id
        candidates.setdefault(cid, row_to_candidate(row))
        candidates[cid].vector_score = row.vector_score
        candidates[cid].vector_rank = rank
        candidates[cid].raw_fusion_score += profile.vector_weight * rrf(rank)

    for rank, row in enumerate(keyword_rows, start=1):
        cid = row.chunk_id
        candidates.setdefault(cid, row_to_candidate(row))
        candidates[cid].keyword_score = row.keyword_score
        candidates[cid].keyword_rank = rank
        candidates[cid].raw_fusion_score += profile.keyword_weight * rrf(rank)

    for rank, row in enumerate(trgm_rows, start=1):
        cid = row.chunk_id
        candidates.setdefault(cid, row_to_candidate(row))
        candidates[cid].trgm_score = row.trgm_score
        candidates[cid].trgm_rank = rank
        candidates[cid].raw_fusion_score += profile.trgm_weight * rrf(rank)

    result = []
    max_raw_score = max(
        [c.raw_fusion_score for c in candidates.values()],
        default=0,
    )

    for candidate in candidates.values():
        candidate.final_score = (
            candidate.raw_fusion_score / max_raw_score
            if max_raw_score > 0
            else 0
        )
        result.append(candidate)

    result.sort(key=lambda x: x.final_score, reverse=True)

    return result
```

说明：

```txt
不要直接把 vector_score、ts_rank_cd、trgm_score 相加。
三种分数分布不同，直接加权会导致 min_final_score 没有稳定含义。
MVP 建议使用 RRF 这类 rank fusion，再把最终分归一化到 0~1，便于统一阈值。
如果只选择 KEYWORD 或 TRIGRAM 模式，不应生成 query embedding。
row_to_candidate 需要把 raw_fusion_score 初始化为 0，并把缺失的各路分数按 0 或 null 明确保存，避免 None 参与计算。
```

---

## 10.5 选择最终 chunks

```python
def select_final_chunks(candidates, final_top_k, min_final_score):
    selected = []

    seen_parent_ids = set()

    for item in candidates:
        if item.final_score < min_final_score:
            continue

        parent_id = item.parent_chunk_id or item.chunk_id

        if parent_id in seen_parent_ids:
            continue

        selected.append(item)
        seen_parent_ids.add(parent_id)

        if len(selected) >= final_top_k:
            break

    return selected
```

说明：

```txt
通过 parent_id 去重，避免同一个父 chunk 下多个 child 重复进入 prompt。
```

---

# 11. Prompt 构建方案

MVP 提示词策略：

```txt
MVP 阶段不单独设计提示词表。
当前系统只落地一种提示词：RAG_QA 主回答提示词。
主回答 prompt 版本由代码里的常量维护，例如 ANSWER_PROMPT_VERSION = "rag_qa_v1"。
rag_query_logs.answer_prompt_version 只表示本次生成最终回答使用的主回答 prompt 版本，不表示所有提示词的统一版本。
rag_query_logs.answer_prompt_text 保存本次实际渲染后发送给 LLM 的完整主回答 prompt 快照。
```

版本维护规则：

```txt
只要修改会影响回答行为的主回答 prompt，就升级 answer_prompt_version。
例如修改拒答规则、引用格式、回答结构、context 拼接方式、资料排序方式，都应从 rag_qa_v1 升级到 rag_qa_v2。
不要让同一个版本标签对应多套不同的提示词逻辑。
```

暂不设计提示词表的原因：

```txt
当前只有主回答 prompt 一种已落地场景。
提示词由代码维护，更简单，也便于和 prompt_builder 的代码变更一起发布。
query log 已保存 answer_prompt_text 快照，足够支持调试和历史复现。
```

后续扩展条件：

```txt
当系统需要多 Agent、多用途提示词、后台编辑、A/B test、灰度发布、回滚、非开发人员维护提示词时，再新增 rag_prompt_templates 和 rag_prompt_runs。
```

未来可扩展的提示词类型：

```txt
RAG_QA：主回答提示词
QUERY_REWRITE：查询改写提示词
ANSWER_JUDGE：回答评估提示词
CITATION_CHECK：引用校验提示词
FAILURE_CLASSIFY：失败原因分类提示词
```

answer_prompt_version 定义规则和定义位置：

```txt
answer_prompt_version 的值定义在代码里，不来自数据库表。
建议命名格式为 rag_qa_v{number}，只用于 RAG_QA 主回答 prompt。
建议放在 app/services/prompt_builder.py 中，和主回答 prompt 模板代码放在一起维护。
调用方不直接手写版本号，而是使用 prompt_builder.build_answer_prompt(...) 返回的 version。
没有实际构建主回答 prompt 时，不写入版本号。
```

```python
@dataclass
class PromptBuildResult:
    prompt_type: str
    version: str
    text: str


ANSWER_PROMPT_TYPE = "RAG_QA"
ANSWER_PROMPT_VERSION = "rag_qa_v1"


def build_answer_prompt(question, selected_parent_chunks):
    context_parts = []

    for index, chunk in enumerate(selected_parent_chunks, start=1):
        context_parts.append(f"""
[片段{index}]
文档：{chunk.document_name}
章节：{chunk.heading_path or chunk.section_title or "未知章节"}
页码：{chunk.page_start or "未知"}

内容：
{chunk.content}
""".strip())

    context = "\n\n".join(context_parts)

    prompt_text = f"""
你是一个知识库问答助手。
请只根据下面提供的资料回答用户问题。

要求：
1. 如果资料中没有答案，请回答“根据当前资料无法确定”。
2. 不要编造资料中没有的信息。
3. 回答要先给结论，再给补充说明。
4. 最后列出依据来自哪些片段。

资料：
{context}

用户问题：
{question}

请给出回答：
""".strip()

    return PromptBuildResult(
        prompt_type=ANSWER_PROMPT_TYPE,
        version=ANSWER_PROMPT_VERSION,
        text=prompt_text,
    )
```

---

# 12. Debug Query 主流程

```python
def build_model_config_snapshot(settings, embedding_service, llm_service):
    return {
        "embedding": {
            "provider": settings.embedding_provider,
            "model": embedding_service.model_name,
            "dimension": embedding_service.dimension,
        },
        "llm": {
            "provider": settings.llm_provider,
            "model": llm_service.model_name,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
        },
    }


async def debug_query(payload, db):
    started_at = now_ms()

    settings = get_settings()
    profile = search_profile_repo.get_or_default(payload.search_profile_id)

    query_log = query_log_repo.create(
        question=payload.question,
        search_mode=profile.search_mode,
        use_llm=payload.use_llm,
        search_profile_id=profile.id,
        top_k=max(
            profile.vector_top_k,
            profile.keyword_top_k,
            profile.trgm_top_k,
        ),
        final_top_k=profile.final_top_k,
    )

    query_embedding = None

    if profile.search_mode in ("VECTOR", "HYBRID"):
        query_embedding = await embedding_service.embed(payload.question)

    search_started = now_ms()

    candidates = hybrid_search_service.search(
        question=payload.question,
        query_embedding=query_embedding,
        profile=profile,
    )

    selected_child_chunks = select_final_chunks(
        candidates=candidates,
        final_top_k=profile.final_top_k,
        min_final_score=profile.min_final_score,
    )

    selected_parent_chunks = chunk_repo.get_parent_chunks(
        selected_child_chunks
    )

    search_latency_ms = now_ms() - search_started

    query_log_repo.update_search_result(
        query_log_id=query_log.id,
        search_profile_snapshot=profile.to_snapshot(),
        model_config_snapshot=build_model_config_snapshot(
            settings=settings,
            embedding_service=embedding_service,
            llm_service=llm_service,
        ),
        max_score=max([c.final_score for c in candidates], default=None),
        min_score=min([c.final_score for c in candidates], default=None),
        search_latency_ms=search_latency_ms,
        total_latency_ms=now_ms() - started_at,
    )

    query_candidate_repo.save_all(
        query_log_id=query_log.id,
        candidates=candidates,
        selected_ids=[c.chunk_id for c in selected_child_chunks],
    )

    llm_result = {
        "used": False,
        "prompt": None,
        "answer": None,
        "model": None,
        "latency_ms": None,
        "error": None,
    }

    should_call_llm = payload.use_llm and bool(selected_parent_chunks)

    if should_call_llm:
        prompt_result = prompt_builder.build_answer_prompt(
            question=payload.question,
            selected_parent_chunks=selected_parent_chunks,
        )
        prompt_text = prompt_result.text

        llm_started = now_ms()

        try:
            answer = await llm_service.chat(prompt_text)

            llm_latency_ms = now_ms() - llm_started

            query_log_repo.update_answer(
                query_log_id=query_log.id,
                answer_prompt_version=prompt_result.version,
                answer_prompt_text=prompt_text,
                answer=answer,
                llm_model=llm_service.model_name,
                search_latency_ms=search_latency_ms,
                llm_latency_ms=llm_latency_ms,
                total_latency_ms=now_ms() - started_at,
            )

            llm_result = {
                "used": True,
                "prompt": prompt_text,
                "answer": answer,
                "model": llm_service.model_name,
                "latency_ms": llm_latency_ms,
                "error": None,
            }

        except Exception as exc:
            query_log_repo.update_llm_error(
                query_log_id=query_log.id,
                error=str(exc),
            )

            create_failure_case(
                query_log_id=query_log.id,
                source_type="AUTO_RULE",
                source_reason=str(exc),
                primary_failure_type="LLM_ERROR",
            )

            llm_result = {
                "used": True,
                "prompt": prompt_text,
                "answer": None,
                "model": llm_service.model_name,
                "latency_ms": None,
                "error": str(exc),
            }

    elif payload.use_llm:
        refusal_answer = "根据当前资料无法确定"

        query_log_repo.update_answer(
            query_log_id=query_log.id,
            answer_prompt_version=None,
            answer_prompt_text=None,
            answer=refusal_answer,
            llm_model=None,
            search_latency_ms=search_latency_ms,
            llm_latency_ms=0,
            total_latency_ms=now_ms() - started_at,
        )

        llm_result = {
            "used": False,
            "prompt": None,
            "answer": refusal_answer,
            "model": None,
            "latency_ms": 0,
            "error": None,
        }

    maybe_create_auto_failure_by_score(
        query_log_id=query_log.id,
        candidates=candidates,
        selected_chunks=selected_child_chunks,
        min_score=profile.min_final_score,
    )

    return build_debug_response(
        query_log_id=query_log.id,
        question=payload.question,
        candidates=candidates,
        selected_chunks=selected_child_chunks,
        selected_parent_chunks=selected_parent_chunks,
        llm_result=llm_result,
    )
```

---

# 13. 失败案例生成方案

失败案例来源：

```txt
USER_FEEDBACK：用户点踩自动生成
MANUAL_DEBUG：开发者在调试页手动生成
EVAL_RUN：测试集失败自动生成
AUTO_RULE：系统规则自动生成
```

统一生成函数：

```python
def create_failure_case(
    query_log_id,
    source_type,
    source_ref_id=None,
    source_reason=None,
    source_payload=None,
    primary_failure_type=None,
):
    return failure_repo.create(
        query_log_id=query_log_id,
        source_type=source_type,
        source_ref_id=source_ref_id,
        source_reason=source_reason,
        source_payload=source_payload,
        primary_failure_type=primary_failure_type,
        status="OPEN",
    )
```

用户反馈触发：

```python
def submit_feedback(query_log_id, rating, reason, comment):
    feedback = feedback_repo.create(
        query_log_id=query_log_id,
        rating=rating,
        reason=reason,
        comment=comment,
    )

    if rating == "NOT_HELPFUL":
        failure = create_failure_case(
            query_log_id=query_log_id,
            source_type="USER_FEEDBACK",
            source_ref_id=feedback.id,
            source_reason=reason,
            source_payload={
                "rating": rating,
                "reason": reason,
                "comment": comment,
            },
        )
        return feedback, failure

    return feedback, None
```

自动规则触发：

```python
def maybe_create_auto_failure_by_score(
    query_log_id,
    candidates,
    selected_chunks,
    min_score,
):
    if not candidates:
        create_failure_case(
            query_log_id=query_log_id,
            source_type="AUTO_RULE",
            source_reason="没有检索到任何候选 chunk",
            primary_failure_type="RETRIEVAL_NO_RECALL",
        )
        return

    max_score = max(c.final_score for c in candidates)

    if max_score < min_score:
        create_failure_case(
            query_log_id=query_log_id,
            source_type="AUTO_RULE",
            source_reason="最高分低于最低可信阈值",
            source_payload={
                "max_score": max_score,
                "min_score": min_score,
            },
            primary_failure_type="LOW_CONFIDENCE_RETRIEVAL",
        )
        return

    if not selected_chunks:
        create_failure_case(
            query_log_id=query_log_id,
            source_type="AUTO_RULE",
            source_reason="没有 chunk 被选入 prompt",
            primary_failure_type="PROMPT_SELECTION_WRONG",
        )
```

---

# 14. 测试用例录入与审核流程

核心原则：

```txt
自动产生的是候选草稿，不是正式测试用例。
失败案例、线上 query、文档生成结果都只能进入 DRAFT。
人工审核通过后，status 才能变成 ACTIVE。
测试集运行只读取 ACTIVE 用例。
```

从查询日志转入：

```python
def create_eval_case_draft_from_query_log(query_log_id, case_type, priority):
    query_log = query_log_repo.get(query_log_id)

    return eval_case_repo.create(
        question=query_log.question,
        expected_answer=None,
        case_type=case_type,
        status="DRAFT",
        priority=priority,
        created_from="QUERY_LOG",
        source_ref_id=query_log.id,
        source_payload={
            "question": query_log.question,
            "answer": query_log.answer,
            "search_mode": query_log.search_mode,
            "max_score": query_log.max_score,
            "min_score": query_log.min_score,
        },
    )
```

从失败案例转入：

```python
def create_eval_case_draft_from_failure_case(failure_case_id, question=None):
    failure = failure_repo.get(failure_case_id)
    query_log = (
        query_log_repo.get(failure.query_log_id)
        if failure.query_log_id
        else None
    )
    draft_question = query_log.question if query_log else question

    if not draft_question:
        raise ValueError("失败案例没有关联 query_log 时必须手动提供 question")

    return eval_case_repo.create(
        question=draft_question,
        expected_answer=None,
        case_type="FAILURE_REGRESSION",
        status="DRAFT",
        priority=failure.priority,
        created_from="FAILURE_CASE",
        source_ref_id=failure.id,
        source_payload={
            "primary_failure_type": failure.primary_failure_type,
            "source_reason": failure.source_reason,
            "analysis_note": failure.analysis_note,
            "fix_plan": failure.fix_plan,
        },
    )
```

从文档生成候选：

```python
async def generate_eval_case_drafts_from_document_version(
    document_version_id,
    max_cases_per_parent_chunk,
):
    parent_chunks = chunk_repo.list_parent_chunks(document_version_id)
    drafts = []

    for parent_chunk in parent_chunks:
        candidates = await eval_case_generator.generate(
            content=parent_chunk.content,
            heading_path=parent_chunk.heading_path,
            max_cases=max_cases_per_parent_chunk,
        )

        for candidate in candidates:
            draft = eval_case_repo.create(
                question=candidate.question,
                expected_answer=candidate.expected_answer,
                case_type="CORE_RULE",
                status="DRAFT",
                priority=3,
                created_from="DOCUMENT_GENERATED",
                source_ref_id=parent_chunk.id,
                source_payload={
                    "document_version_id": document_version_id,
                    "parent_chunk_id": parent_chunk.id,
                    "heading_path": parent_chunk.heading_path,
                    "generated_expected_keywords": candidate.expected_keywords,
                },
            )
            drafts.append(draft)

    return drafts
```

人工审核：

```python
def review_eval_case(eval_case_id, action, reviewer, review_note):
    case = eval_case_repo.get(eval_case_id)

    if action == "APPROVE":
        expected_sources = eval_repo.get_expected_sources(case.id)

        if not case.question:
            raise ValueError("question 不能为空")

        if not expected_sources:
            raise ValueError("审核通过前必须配置 expected_sources")

        return eval_case_repo.update_review_status(
            eval_case_id=case.id,
            status="ACTIVE",
            reviewed_by=reviewer,
            review_note=review_note,
            reviewed_at=now(),
            activated_at=case.activated_at or now(),
        )

    if action == "REJECT":
        if not review_note:
            raise ValueError("拒绝时必须填写 review_note")

        return eval_case_repo.update_review_status(
            eval_case_id=case.id,
            status="REJECTED",
            reviewed_by=reviewer,
            review_note=review_note,
            reviewed_at=now(),
        )

    raise ValueError("不支持的审核动作")
```

审核规则：

```txt
question 必须稳定、可重复，不依赖临时上下文。
expected_answer 必须来自权威文档，不直接采用线上 LLM 回答。
expected_sources 必须足够支撑检索命中判断。
只做检索评估的用例可以不填 expected_answer，但不能缺 expected_sources。
ACTIVE 用例参与历史评估后，不建议直接修改 question / expected_answer / expected_sources。
需要调整标准答案时，建议停用旧用例，再创建新的 DRAFT 重新审核。
```

---

# 15. 测试集运行方案

```python
async def run_eval(eval_run_payload):
    profile = search_profile_repo.get_or_default(
        eval_run_payload.search_profile_id
    )
    cases = eval_repo.list_cases_by_status(status="ACTIVE")

    eval_run = eval_repo.create_run(
        name=eval_run_payload.name,
        search_profile_id=eval_run_payload.search_profile_id,
        search_profile_snapshot=profile.to_snapshot(),
        use_llm=eval_run_payload.use_llm,
        run_status="RUNNING",
        eval_config={
            "retrieval_pass": "top5_hit",
            "answer_pass": "simple_answer_check",
            "case_pass_when_use_llm": "top5_hit AND answer_pass",
        },
        total_cases=len(cases),
    )

    passed = 0
    failed = 0

    for case in cases:
        result = await rag_service.debug_query(
            question=case.question,
            search_profile_id=eval_run_payload.search_profile_id,
            use_llm=eval_run_payload.use_llm,
        )

        expected_sources = eval_repo.get_expected_sources(case.id)

        top1_hit = check_top1_hit(
            candidates=result.search.candidates,
            expected_sources=expected_sources,
        )

        top5_hit = check_top5_hit(
            candidates=result.search.candidates,
            expected_sources=expected_sources,
        )

        retrieval_pass = top5_hit
        answer_pass = None
        answer_eval_detail = None

        if eval_run_payload.use_llm and case.expected_answer:
            answer_eval = simple_answer_check(
                answer=result.llm.answer,
                expected_answer=case.expected_answer,
            )
            answer_pass = answer_eval.passed
            answer_eval_detail = answer_eval.to_dict()

        eval_result = eval_repo.create_result(
            eval_run_id=eval_run.id,
            eval_case_id=case.id,
            query_log_id=result.query_log_id,
            top1_hit=top1_hit,
            top5_hit=top5_hit,
            retrieval_pass=retrieval_pass,
            answer_pass=answer_pass,
            answer_score=answer_eval_detail.get("score") if answer_eval_detail else None,
            answer_eval_detail=answer_eval_detail,
        )

        case_pass = (
            retrieval_pass
            if not eval_run_payload.use_llm
            else retrieval_pass and answer_pass is not False
        )

        if case_pass:
            passed += 1
        else:
            failed += 1
            failure_type = (
                "RETRIEVAL_NO_RECALL"
                if not retrieval_pass
                else "GENERATION_WRONG"
            )
            failure_reason = (
                "测试集未命中期望来源"
                if not retrieval_pass
                else "检索命中但回答未通过评估"
            )

            failure = create_failure_case(
                query_log_id=result.query_log_id,
                source_type="EVAL_RUN",
                source_ref_id=eval_result.id,
                source_reason=failure_reason,
                primary_failure_type=failure_type,
            )

            eval_repo.mark_result_failed(
                eval_result_id=eval_result.id,
                failure_reason=failure_reason,
                failure_created=True,
                failure_case_id=failure.id,
            )

    eval_repo.update_run_counts(
        eval_run_id=eval_run.id,
        passed_cases=passed,
        failed_cases=failed,
        run_status="COMPLETED",
        finished_at=now(),
    )

    return eval_run
```

---

# 16. 费用说明

## 16.1 Neon

MVP 阶段可以先使用 Neon 免费额度。

主要消耗：

```txt
数据库存储
向量字段存储
索引空间
查询计算资源
```

需要注意：

```txt
embedding VECTOR(N) 会占用空间，N 必须等于实际 embedding 模型输出维度。
调试日志和 query_candidates 会持续增长，需要定期清理。
```

建议：

```txt
MVP 控制文档数量在 20 个以内。
chunk 数量控制在 5000 以内。
只保留最近 2~3 个文档版本。
query_logs 可定期归档。
```

---

## 16.2 Embedding

如果使用第三方 API，通常按 token 付费。

省钱策略：

```txt
只对 child chunk 生成 embedding。
parent chunk 不生成 embedding。
content_hash 相同则不重新生成 embedding。
文档处理失败不切换 current_version_id。
```

---

## 16.3 LLM

LLM 回答通常按输入输出 token 收费。

省钱策略：

```txt
调试检索时 use_llm=false。
低置信度时不调用 LLM。
final_top_k 控制为 3~5。
parent chunk 不要过大。
```

---

# 17. MVP 开发顺序

## 阶段一：基础入库

```txt
1. Neon 连接
2. pgvector / pg_trgm 扩展
3. Alembic 建表
4. 文档上传
5. 文本解析
6. parent / child chunk 生成
7. chunk 入库
```

---

## 阶段二：向量检索

```txt
1. child chunk embedding
2. vector search
3. debug-query use_llm=false
4. 调试页能看到 candidates
```

---

## 阶段三：问答生成

```txt
1. 获取 parent chunks
2. prompt_builder
3. LLM 调用
4. debug-query use_llm=true
5. 回答和来源展示
```

---

## 阶段四：混合检索

```txt
1. search_text
2. search_tsv
3. Full Text Search
4. pg_trgm
5. hybrid score fusion
6. search_profile 配置
```

---

## 阶段五：优化闭环

```txt
1. 用户反馈
2. 失败案例
3. 人工分类
4. 测试用例草稿生成
5. 测试用例人工审核
6. eval run
7. 质量看板
```

---

# 18. 后端验收标准

## 18.1 文档入库验收

```txt
可以上传 txt/md/pdf。
可以生成 document 和 version。
可以生成 parent / child chunks。
child chunks 有 embedding。
当前版本处理成功后才切换 current_version_id。
旧版本不会被正常检索命中。
```

---

## 18.2 检索验收

```txt
debug-query use_llm=false 能返回 candidates。
candidates 包含 vector_score、keyword_score、trgm_score、final_score。
selected_for_prompt 正确标记。
只检索当前版本 chunk。
```

---

## 18.3 问答验收

```txt
debug-query use_llm=true 能返回 prompt 和 answer。
answer 基于 selected parent chunks。
sources 可以追溯到 document、version、chunk。
低置信度时可以拒答。
```

---

## 18.4 调试验收

```txt
每次查询生成 rag_query_logs。
每个候选 chunk 生成 rag_query_candidates。
可以查看完整 prompt。
可以查看 LLM answer。
可以手动生成失败案例。
```

---

## 18.5 优化验收

```txt
用户点踩可以生成 failure_case。
测试集失败可以生成 failure_case。
失败案例可以分类、填写分析和修复计划。
query_log 和 failure_case 可以转成 eval case DRAFT。
文档版本可以生成 eval case DRAFT 候选。
DRAFT / REJECTED / INACTIVE 用例不会参与 eval_run。
审核通过后 eval case 才会变成 ACTIVE 并参与 eval_run。
搜索配置可以调整权重和 top_k。
eval_run 可以保存搜索配置快照。
eval_result 可以区分 retrieval_pass 和 answer_pass。
use_llm=false 时按检索命中评估。
use_llm=true 时按检索命中 + 回答质量评估。
```
