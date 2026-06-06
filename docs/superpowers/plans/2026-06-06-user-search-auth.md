# 普通用户文档检索与环境变量权限方案

## Summary

新增环境变量驱动的两类用户：`SUPER_ADMIN` 和 `NORMAL_USER`。不做用户表、不做数据隔离；普通用户可完整使用“文档管理”和“文档检索”，超管保留调试、词典、查询日志等能力。

文档检索返回多条结果，每条命中 chunk 都有自己的 answer、命中内容和前后文；用户反馈只绑定整次查询。

## Key Changes

- 认证：新增 `/api/v1/auth/login`、`/api/v1/auth/me`、`/api/v1/auth/logout`，用环境变量配置用户和密码，后端签发 `HttpOnly` session cookie。
- 权限：文档接口和普通检索接口允许两类用户；`/rag/debug`、`/rag/synonyms`、`/rag/query-logs/*`、失败案例、评测样本只允许超管。
- 普通检索：新增 `POST /api/v1/rag/search`，复用现有检索排序，默认最多返回 5 条结果，不暴露分数、Prompt、权重、top_k。
- 每条结果答案：一次 LLM 调用批量生成所有结果答案，每条答案只能基于该条 chunk 的命中内容、前文、后文生成，不能跨 chunk 合并。
- 反馈：新增整次查询反馈接口 `POST /api/v1/rag/search/{query_log_id}/feedback`，不绑定单个 chunk。

## Public Interfaces

环境变量：

```env
AUTH_SESSION_SECRET=change-me
AUTH_TOKEN_EXPIRE_MINUTES=1440

SUPER_ADMIN_USERNAME=admin
SUPER_ADMIN_PASSWORD=admin-password

NORMAL_USER_USERNAME=user
NORMAL_USER_PASSWORD=user-password

CORS_ORIGINS=http://localhost:5173
```

普通检索请求：

```json
{
  "question": "差旅报销需要什么材料？",
  "use_llm": true
}
```

普通检索响应：

```json
{
  "query_log_id": 1001,
  "question": "差旅报销需要什么材料？",
  "status": "COMPLETED",
  "results": [
    {
      "rank": 1,
      "query_candidate_id": 501,
      "chunk_id": 10,
      "answer_status": "ANSWERED",
      "answer": "差旅报销需要提供发票、行程单、审批记录。",
      "document_id": 1,
      "document_name": "公司报销制度.pdf",
      "section_title": "差旅报销",
      "heading_path": "报销制度 / 差旅报销",
      "hit_content": "差旅报销需要提供发票、行程单、审批记录。",
      "before_context": "员工提交差旅报销前，需要先确认出差审批已完成。",
      "after_context": "如涉及住宿费用，还需要提供酒店水单或平台订单截图。"
    }
  ],
  "warnings": []
}
```

状态枚举：

- 顶层 `status`：`COMPLETED`、`NO_RECALL`、`LLM_DISABLED`、`LLM_ERROR`
- 单条 `answer_status`：`ANSWERED`、`NO_ANSWER`、`LLM_DISABLED`、`LLM_ERROR`

反馈请求：

```json
{
  "rating": "PARTIALLY_HELPFUL",
  "comment": "找到了相关制度，但回答不够完整。",
  "expected_answer": "还需要说明住宿报销材料。"
}
```

`rating`：`HELPFUL`、`PARTIALLY_HELPFUL`、`NOT_HELPFUL`

## Implementation Notes

- 后端新增认证模块，使用标准库 HMAC 签名 cookie，不引入额外 JWT 依赖；前端 `fetch` 统一带 `credentials: "include"`。
- 新增 `rag_search_service`：调用现有 debug 检索链路拿到 selected chunks，再按 `parent_chunk_id + child_index` 取前一个和后一个 child 作为上下文。
- Prompt 使用批量 JSON 输出格式：每条结果按 `rank` 返回 `answer_status` 和 `answer`；如果 LLM 不可用或解析失败，保留检索结果，结果 answer 置空并标记对应错误状态。
- 数据库新增 `rag_query_feedbacks`；扩展 `rag_query_candidates` 保存 `result_answer`、`result_answer_status`、`before_context_snapshot`、`after_context_snapshot`、`result_answer_error`。
- 前端新增 `/login` 和 `/rag/search`；侧边栏普通用户只显示“文档管理 / 文档检索”，超管额外显示“检索调试 / 检索词典”。
- `/documents` 导航文案从“文档”改为“文档管理”。

## Test Plan

- 后端：登录成功/失败、`/auth/me`、未登录 401、普通用户访问超管接口 403、超管访问全部接口成功。
- 后端：普通检索返回最多 5 条 results；每条包含 answer、hit_content、before_context、after_context；无召回、LLM disabled、LLM error 都返回稳定结构。
- 后端：整次查询反馈可写入 `rag_query_feedbacks`，记录 `query_log_id`、`username`、`role`、`rating`、备注和期望答案。
- 前端：未登录跳转 `/login`；普通用户只看到“文档管理 / 文档检索”；超管看到完整导航。
- 前端：文档检索页展示多条结果，每条有自己的回答和上下文展开；提交整体反馈后显示成功状态。

## Assumptions

- 普通用户拥有完整文档管理权限：上传、查看、上传新版本、删除。
- 普通检索默认展示 5 条结果，第一版不提供数量调节。
- 反馈第一版只评价整次查询，不评价单条 chunk。
- 不做任何用户级数据隔离，所有用户共享同一套文档和检索日志。
