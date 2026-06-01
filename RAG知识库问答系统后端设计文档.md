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
12. 测试集与评估方案
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
Embedding：OpenAI / 通义 / bge-m3 / 其他 embedding API
LLM：OpenAI / DeepSeek / 通义 / Claude
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

测试集不需要覆盖所有 chunk，而是覆盖：

```txt
核心规则问题
高频用户问题
边界问题
历史失败问题
```

---

# 6. 数据库表设计

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
  document_id BIGINT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
  version_no INT NOT NULL,
  file_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PROCESSING',
  chunk_count INT DEFAULT 0,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_document_versions IS '文档版本表，每次上传或更新文档都会创建新版本';
COMMENT ON COLUMN rag_document_versions.id IS '文档版本主键 ID';
COMMENT ON COLUMN rag_document_versions.document_id IS '所属文档 ID';
COMMENT ON COLUMN rag_document_versions.version_no IS '版本号，从 1 开始递增';
COMMENT ON COLUMN rag_document_versions.file_hash IS '文件内容 hash，用于判断文件是否变化';
COMMENT ON COLUMN rag_document_versions.status IS '版本处理状态，PROCESSING、COMPLETED、FAILED';
COMMENT ON COLUMN rag_document_versions.chunk_count IS '该版本生成的 chunk 数量';
COMMENT ON COLUMN rag_document_versions.error_message IS '处理失败时的错误信息';
COMMENT ON COLUMN rag_document_versions.created_at IS '版本创建时间';
```

字段说明：

| 字段            | 类型        | 说明       |
| ------------- | --------- | -------- |
| id            | BIGSERIAL | 版本主键     |
| document_id   | BIGINT    | 所属文档     |
| version_no    | INT       | 版本号      |
| file_hash     | TEXT      | 文件 hash  |
| status        | TEXT      | 处理状态     |
| chunk_count   | INT       | chunk 数量 |
| error_message | TEXT      | 错误信息     |
| created_at    | TIMESTAMP | 创建时间     |

状态枚举：

```txt
PROCESSING
COMPLETED
FAILED
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

  document_id BIGINT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
  document_version_id BIGINT NOT NULL REFERENCES rag_document_versions(id) ON DELETE CASCADE,

  parent_chunk_id BIGINT REFERENCES rag_chunks(id) ON DELETE CASCADE,

  chunk_type TEXT NOT NULL,
  chunk_index INT NOT NULL,

  section_title TEXT,
  heading_path TEXT,

  page_start INT,
  page_end INT,
  start_char INT,
  end_char INT,

  content TEXT NOT NULL,
  content_with_context TEXT NOT NULL,

  content_hash TEXT,
  token_count INT,

  embedding VECTOR(1536),

  search_text TEXT,
  search_tsv tsvector,

  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_chunks IS '文档切片表，保存 parent chunk 和 child chunk';
COMMENT ON COLUMN rag_chunks.id IS 'chunk 主键 ID';
COMMENT ON COLUMN rag_chunks.document_id IS '所属文档 ID';
COMMENT ON COLUMN rag_chunks.document_version_id IS '所属文档版本 ID';
COMMENT ON COLUMN rag_chunks.parent_chunk_id IS '父 chunk ID，child chunk 通过该字段关联 parent chunk';
COMMENT ON COLUMN rag_chunks.chunk_type IS 'chunk 类型，PARENT 或 CHILD';
COMMENT ON COLUMN rag_chunks.chunk_index IS 'chunk 在当前文档版本中的顺序';
COMMENT ON COLUMN rag_chunks.section_title IS '当前 chunk 所属章节标题';
COMMENT ON COLUMN rag_chunks.heading_path IS '标题路径，例如 公司制度 / 报销制度 / 差旅报销';
COMMENT ON COLUMN rag_chunks.page_start IS 'chunk 起始页码，主要用于 PDF';
COMMENT ON COLUMN rag_chunks.page_end IS 'chunk 结束页码，主要用于 PDF';
COMMENT ON COLUMN rag_chunks.start_char IS 'chunk 在原始文本中的起始字符位置';
COMMENT ON COLUMN rag_chunks.end_char IS 'chunk 在原始文本中的结束字符位置';
COMMENT ON COLUMN rag_chunks.content IS '原始 chunk 内容，用于展示给用户';
COMMENT ON COLUMN rag_chunks.content_with_context IS '带文档名、标题、页码的上下文文本，用于生成 embedding';
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
| chunk_index          | INT          | 顺序                  |
| section_title        | TEXT         | 章节标题                |
| heading_path         | TEXT         | 标题路径                |
| page_start           | INT          | 起始页码                |
| page_end             | INT          | 结束页码                |
| start_char           | INT          | 起始字符                |
| end_char             | INT          | 结束字符                |
| content              | TEXT         | 原始内容                |
| content_with_context | TEXT         | 用于 embedding 的上下文文本 |
| content_hash         | TEXT         | 内容 hash             |
| token_count          | INT          | token 数             |
| embedding            | VECTOR(1536) | 向量                  |
| search_text          | TEXT         | 关键词检索文本             |
| search_tsv           | tsvector     | 全文检索向量              |
| created_at           | TIMESTAMP    | 创建时间                |

索引：

```sql
CREATE INDEX idx_rag_chunks_document_version
ON rag_chunks(document_id, document_version_id);

CREATE INDEX idx_rag_chunks_parent
ON rag_chunks(parent_chunk_id);

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
USING hnsw (embedding vector_cosine_ops);
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

  top_k INT DEFAULT 20,
  final_top_k INT DEFAULT 5,

  embedding_model TEXT,
  llm_model TEXT,

  prompt_text TEXT,
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
COMMENT ON COLUMN rag_query_logs.top_k IS '候选检索数量';
COMMENT ON COLUMN rag_query_logs.final_top_k IS '最终送入 prompt 的 chunk 数量';
COMMENT ON COLUMN rag_query_logs.embedding_model IS '问题 embedding 使用的模型';
COMMENT ON COLUMN rag_query_logs.llm_model IS '回答生成使用的 LLM 模型';
COMMENT ON COLUMN rag_query_logs.prompt_text IS '最终发送给 LLM 的 prompt';
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
| top_k             | INT       | 候选数量         |
| final_top_k       | INT       | 入 prompt 数量  |
| embedding_model   | TEXT      | embedding 模型 |
| llm_model         | TEXT      | LLM 模型       |
| prompt_text       | TEXT      | prompt       |
| answer            | TEXT      | 回答           |
| max_score         | FLOAT     | 最高分          |
| min_score         | FLOAT     | 最低分          |
| search_latency_ms | INT       | 检索耗时         |
| llm_latency_ms    | INT       | LLM 耗时       |
| total_latency_ms  | INT       | 总耗时          |
| llm_error         | TEXT      | LLM 错误       |
| created_at        | TIMESTAMP | 创建时间         |

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

  query_log_id BIGINT NOT NULL REFERENCES rag_query_logs(id) ON DELETE CASCADE,

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

  query_log_id BIGINT NOT NULL REFERENCES rag_query_logs(id) ON DELETE CASCADE,

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

  query_log_id BIGINT NOT NULL REFERENCES rag_query_logs(id) ON DELETE CASCADE,

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
COMMENT ON COLUMN rag_failure_cases.query_log_id IS '关联的查询日志 ID';
COMMENT ON COLUMN rag_failure_cases.source_type IS '失败来源，USER_FEEDBACK、MANUAL_DEBUG、EVAL_RUN、AUTO_RULE';
COMMENT ON COLUMN rag_failure_cases.source_ref_id IS '来源记录 ID，例如 feedback_id 或 eval_result_id';
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
| query_log_id         | BIGINT    | 查询日志    |
| source_type          | TEXT      | 来源类型    |
| source_ref_id        | BIGINT    | 来源记录 ID |
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
USER_FEEDBACK
MANUAL_DEBUG
EVAL_RUN
AUTO_RULE
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
保存固定测试问题。
用于评估不同切片策略、检索策略、prompt 策略的效果。
```

```sql
CREATE TABLE rag_eval_cases (
  id BIGSERIAL PRIMARY KEY,

  question TEXT NOT NULL,
  expected_answer TEXT,

  case_type TEXT NOT NULL DEFAULT 'CORE_RULE',
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  priority INT DEFAULT 3,

  created_from TEXT DEFAULT 'MANUAL',

  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_eval_cases IS 'RAG 测试问题集表，用于持续评估检索和回答质量';
COMMENT ON COLUMN rag_eval_cases.id IS '测试用例主键 ID';
COMMENT ON COLUMN rag_eval_cases.question IS '测试问题';
COMMENT ON COLUMN rag_eval_cases.expected_answer IS '期望答案，用于人工或自动评估';
COMMENT ON COLUMN rag_eval_cases.case_type IS '测试类型，CORE_RULE、FREQUENT_QUERY、EDGE_CASE、FAILURE_REGRESSION';
COMMENT ON COLUMN rag_eval_cases.status IS '状态，ACTIVE 表示参与测试，INACTIVE 表示停用';
COMMENT ON COLUMN rag_eval_cases.priority IS '优先级，1 最高，5 最低';
COMMENT ON COLUMN rag_eval_cases.created_from IS '来源，MANUAL、USER_FEEDBACK、FAILURE_CASE';
COMMENT ON COLUMN rag_eval_cases.created_at IS '创建时间';
COMMENT ON COLUMN rag_eval_cases.updated_at IS '更新时间';
```

字段说明：

| 字段              | 类型        | 说明      |
| --------------- | --------- | ------- |
| id              | BIGSERIAL | 测试用例 ID |
| question        | TEXT      | 测试问题    |
| expected_answer | TEXT      | 期望答案    |
| case_type       | TEXT      | 用例类型    |
| status          | TEXT      | 状态      |
| priority        | INT       | 优先级     |
| created_from    | TEXT      | 创建来源    |
| created_at      | TIMESTAMP | 创建时间    |
| updated_at      | TIMESTAMP | 更新时间    |

case_type 枚举：

```txt
CORE_RULE
FREQUENT_QUERY
EDGE_CASE
FAILURE_REGRESSION
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

  eval_case_id BIGINT NOT NULL REFERENCES rag_eval_cases(id) ON DELETE CASCADE,

  document_id BIGINT,
  document_version_id BIGINT,

  expected_section_title TEXT,
  expected_keywords TEXT,

  expected_chunk_id BIGINT,

  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_eval_expected_sources IS '测试用例期望来源表，用于判断检索是否命中正确文档或章节';
COMMENT ON COLUMN rag_eval_expected_sources.id IS '期望来源主键 ID';
COMMENT ON COLUMN rag_eval_expected_sources.eval_case_id IS '所属测试用例 ID';
COMMENT ON COLUMN rag_eval_expected_sources.document_id IS '期望命中的文档 ID';
COMMENT ON COLUMN rag_eval_expected_sources.document_version_id IS '期望命中的文档版本 ID，可为空';
COMMENT ON COLUMN rag_eval_expected_sources.expected_section_title IS '期望命中的章节标题';
COMMENT ON COLUMN rag_eval_expected_sources.expected_keywords IS '期望命中的关键词，多个关键词可用逗号分隔';
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
| expected_keywords      | TEXT      | 期望关键词    |
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

  search_mode TEXT,
  chunk_strategy TEXT,
  embedding_model TEXT,
  llm_model TEXT,

  total_cases INT DEFAULT 0,
  passed_cases INT DEFAULT 0,
  failed_cases INT DEFAULT 0,

  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_eval_runs IS '测试集运行记录表，保存一次评估运行的整体结果';
COMMENT ON COLUMN rag_eval_runs.id IS '评估运行主键 ID';
COMMENT ON COLUMN rag_eval_runs.name IS '评估运行名称';
COMMENT ON COLUMN rag_eval_runs.search_profile_id IS '使用的搜索配置 ID';
COMMENT ON COLUMN rag_eval_runs.search_mode IS '检索模式';
COMMENT ON COLUMN rag_eval_runs.chunk_strategy IS 'chunk 策略说明';
COMMENT ON COLUMN rag_eval_runs.embedding_model IS 'embedding 模型';
COMMENT ON COLUMN rag_eval_runs.llm_model IS 'LLM 模型';
COMMENT ON COLUMN rag_eval_runs.total_cases IS '总测试用例数';
COMMENT ON COLUMN rag_eval_runs.passed_cases IS '通过数量';
COMMENT ON COLUMN rag_eval_runs.failed_cases IS '失败数量';
COMMENT ON COLUMN rag_eval_runs.created_at IS '创建时间';
```

字段说明：

| 字段                | 类型        | 说明           |
| ----------------- | --------- | ------------ |
| id                | BIGSERIAL | 运行 ID        |
| name              | TEXT      | 运行名称         |
| search_profile_id | BIGINT    | 搜索配置         |
| search_mode       | TEXT      | 检索模式         |
| chunk_strategy    | TEXT      | chunk 策略     |
| embedding_model   | TEXT      | embedding 模型 |
| llm_model         | TEXT      | LLM 模型       |
| total_cases       | INT       | 总数           |
| passed_cases      | INT       | 通过数          |
| failed_cases      | INT       | 失败数          |
| created_at        | TIMESTAMP | 创建时间         |

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

  eval_run_id BIGINT NOT NULL REFERENCES rag_eval_runs(id) ON DELETE CASCADE,
  eval_case_id BIGINT NOT NULL REFERENCES rag_eval_cases(id) ON DELETE CASCADE,
  query_log_id BIGINT REFERENCES rag_query_logs(id) ON DELETE SET NULL,

  top1_hit BOOLEAN DEFAULT false,
  top5_hit BOOLEAN DEFAULT false,
  answer_pass BOOLEAN DEFAULT false,

  failure_reason TEXT,
  failure_created BOOLEAN DEFAULT false,

  created_at TIMESTAMP DEFAULT now()
);

COMMENT ON TABLE rag_eval_results IS '测试用例运行结果表，保存每个测试问题的命中情况和回答结果';
COMMENT ON COLUMN rag_eval_results.id IS '评估结果主键 ID';
COMMENT ON COLUMN rag_eval_results.eval_run_id IS '所属评估运行 ID';
COMMENT ON COLUMN rag_eval_results.eval_case_id IS '所属测试用例 ID';
COMMENT ON COLUMN rag_eval_results.query_log_id IS '本次测试对应的查询日志 ID';
COMMENT ON COLUMN rag_eval_results.top1_hit IS '期望来源是否命中 Top 1';
COMMENT ON COLUMN rag_eval_results.top5_hit IS '期望来源是否命中 Top 5';
COMMENT ON COLUMN rag_eval_results.answer_pass IS '回答是否通过评估';
COMMENT ON COLUMN rag_eval_results.failure_reason IS '失败原因';
COMMENT ON COLUMN rag_eval_results.failure_created IS '是否已生成失败案例';
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
| answer_pass     | BOOLEAN   | 回答通过     |
| failure_reason  | TEXT      | 失败原因     |
| failure_created | BOOLEAN   | 是否生成失败案例 |
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
  updated_at TIMESTAMP DEFAULT now()
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
    "model": "gpt-4.1-mini",
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
  "expected_sources": [
    {
      "document_id": 1,
      "expected_section_title": "差旅报销",
      "expected_keywords": "发票,行程单,审批记录"
    }
  ]
}
```

---

## 7.16 运行测试集

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
  "total_cases": 20,
  "passed_cases": 16,
  "failed_cases": 4
}
```

---

## 7.17 搜索配置列表

```http
GET /api/v1/rag/search-profiles
```

---

## 7.18 创建搜索配置

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
  "min_final_score": 0.55
}
```

---

# 8. 文档入库实现方案

## 8.1 入库主流程

```python
async def ingest_document(file, document_id=None):
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
        status="PROCESSING",
    )

    try:
        blocks = document_parser.parse(file.filename, file_bytes)

        chunks = chunker.build_parent_child_chunks(
            document=document,
            version=version,
            blocks=blocks,
        )

        for chunk in chunks:
            if chunk.chunk_type == "CHILD":
                chunk.embedding = await embedding_service.embed(
                    chunk.content_with_context
                )

            chunk.search_text = build_search_text(chunk)
            chunk.search_tsv = build_search_tsv(chunk.search_text)

            chunk_repo.create(chunk)

        document_repo.mark_version_completed(
            version_id=version.id,
            chunk_count=len(chunks),
        )

        document_repo.set_current_version(
            document_id=document.id,
            version_id=version.id,
        )

        return {
            "document_id": document.id,
            "version_id": version.id,
            "status": "COMPLETED",
            "chunk_count": len(chunks),
        }

    except Exception as exc:
        document_repo.mark_version_failed(
            version_id=version.id,
            error_message=str(exc),
        )
        raise
```

关键点：

```txt
新版本全部处理成功后，才切换 current_version_id。
处理失败时，旧版本仍然可用。
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
def build_parent_child_chunks(document, version, blocks):
    sections = split_blocks_by_heading(blocks)

    all_chunks = []
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
                content_with_context=build_context_text(
                    document_name=document.name,
                    heading_path=section.heading_path,
                    page_start=section.page_start,
                    content=parent_text,
                ),
                content_hash=hash_text(parent_text),
                token_count=estimate_tokens(parent_text),
            )

            all_chunks.append(parent_chunk)

            child_texts = split_with_overlap(
                parent_text,
                chunk_size=500,
                overlap=80,
            )

            for child_text in child_texts:
                child_chunk = RagChunkCreate(
                    document_id=document.id,
                    document_version_id=version.id,
                    parent_chunk_id="TEMP_PARENT_REF",
                    chunk_type="CHILD",
                    chunk_index=child_global_index,
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

                all_chunks.append(child_chunk)
                child_global_index += 1

            parent_index += 1

    return all_chunks
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
def hybrid_search(question, query_embedding, profile):
    vector_rows = vector_search(question, query_embedding, profile.vector_top_k)
    keyword_rows = keyword_search(question, profile.keyword_top_k)
    trgm_rows = trigram_search(question, profile.trgm_top_k)

    candidates = {}

    for rank, row in enumerate(vector_rows, start=1):
        cid = row.chunk_id
        candidates.setdefault(cid, row_to_candidate(row))
        candidates[cid].vector_score = row.vector_score
        candidates[cid].vector_rank = rank

    for rank, row in enumerate(keyword_rows, start=1):
        cid = row.chunk_id
        candidates.setdefault(cid, row_to_candidate(row))
        candidates[cid].keyword_score = normalize_keyword_score(row.keyword_score)
        candidates[cid].keyword_rank = rank

    for rank, row in enumerate(trgm_rows, start=1):
        cid = row.chunk_id
        candidates.setdefault(cid, row_to_candidate(row))
        candidates[cid].trgm_score = row.trgm_score
        candidates[cid].trgm_rank = rank

    result = []

    for candidate in candidates.values():
        candidate.final_score = (
            profile.vector_weight * candidate.vector_score +
            profile.keyword_weight * candidate.keyword_score +
            profile.trgm_weight * candidate.trgm_score
        )
        result.append(candidate)

    result.sort(key=lambda x: x.final_score, reverse=True)

    return result
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

```python
def build_prompt(question, selected_parent_chunks):
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

    return f"""
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
```

---

# 12. Debug Query 主流程

```python
async def debug_query(payload, db):
    started_at = now_ms()

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

    if payload.use_llm:
        prompt = prompt_builder.build(
            question=payload.question,
            selected_parent_chunks=selected_parent_chunks,
        )

        llm_started = now_ms()

        try:
            answer = await llm_service.chat(prompt)

            llm_latency_ms = now_ms() - llm_started

            query_log_repo.update_answer(
                query_log_id=query_log.id,
                prompt_text=prompt,
                answer=answer,
                llm_model=llm_service.model_name,
                search_latency_ms=search_latency_ms,
                llm_latency_ms=llm_latency_ms,
                total_latency_ms=now_ms() - started_at,
            )

            llm_result = {
                "used": True,
                "prompt": prompt,
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

            failure_service.create_auto_failure(
                query_log_id=query_log.id,
                failure_type="LLM_ERROR",
                detail=str(exc),
            )

            llm_result = {
                "used": True,
                "prompt": prompt,
                "answer": None,
                "model": llm_service.model_name,
                "latency_ms": None,
                "error": str(exc),
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

# 14. 测试集运行方案

```python
async def run_eval(eval_run_payload):
    cases = eval_repo.list_active_cases()

    eval_run = eval_repo.create_run(
        name=eval_run_payload.name,
        search_profile_id=eval_run_payload.search_profile_id,
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

        answer_pass = False

        if eval_run_payload.use_llm:
            answer_pass = simple_answer_check(
                answer=result.llm.answer,
                expected_answer=case.expected_answer,
            )

        eval_result = eval_repo.create_result(
            eval_run_id=eval_run.id,
            eval_case_id=case.id,
            query_log_id=result.query_log_id,
            top1_hit=top1_hit,
            top5_hit=top5_hit,
            answer_pass=answer_pass,
        )

        if top5_hit:
            passed += 1
        else:
            failed += 1

            create_failure_case(
                query_log_id=result.query_log_id,
                source_type="EVAL_RUN",
                source_ref_id=eval_result.id,
                source_reason="测试集未命中期望来源",
                primary_failure_type="RETRIEVAL_NO_RECALL",
            )

    eval_repo.update_run_counts(
        eval_run_id=eval_run.id,
        passed_cases=passed,
        failed_cases=failed,
    )

    return eval_run
```

---

# 15. 费用说明

## 15.1 Neon

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
embedding VECTOR(1536) 会占用空间。
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

## 15.2 Embedding

如果使用第三方 API，通常按 token 付费。

省钱策略：

```txt
只对 child chunk 生成 embedding。
parent chunk 不生成 embedding。
content_hash 相同则不重新生成 embedding。
文档处理失败不切换 current_version_id。
```

---

## 15.3 LLM

LLM 回答通常按输入输出 token 收费。

省钱策略：

```txt
调试检索时 use_llm=false。
低置信度时不调用 LLM。
final_top_k 控制为 3~5。
parent chunk 不要过大。
```

---

# 16. MVP 开发顺序

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
4. 测试集
5. eval run
6. 质量看板
```

---

# 17. 后端验收标准

## 17.1 文档入库验收

```txt
可以上传 txt/md/pdf。
可以生成 document 和 version。
可以生成 parent / child chunks。
child chunks 有 embedding。
当前版本处理成功后才切换 current_version_id。
旧版本不会被正常检索命中。
```

---

## 17.2 检索验收

```txt
debug-query use_llm=false 能返回 candidates。
candidates 包含 vector_score、keyword_score、trgm_score、final_score。
selected_for_prompt 正确标记。
只检索当前版本 chunk。
```

---

## 17.3 问答验收

```txt
debug-query use_llm=true 能返回 prompt 和 answer。
answer 基于 selected parent chunks。
sources 可以追溯到 document、version、chunk。
低置信度时可以拒答。
```

---

## 17.4 调试验收

```txt
每次查询生成 rag_query_logs。
每个候选 chunk 生成 rag_query_candidates。
可以查看完整 prompt。
可以查看 LLM answer。
可以手动生成失败案例。
```

---

## 17.5 优化验收

```txt
用户点踩可以生成 failure_case。
测试集失败可以生成 failure_case。
失败案例可以分类、填写分析和修复计划。
搜索配置可以调整权重和 top_k。
```
