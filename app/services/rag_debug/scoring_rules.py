"""调试检索（RAG Debug）评分规则。

这些数值刻意保持现有检索行为不变。集中放在这里，是为了让后续调参变成显式、可 review 的改动，
避免魔法数字散落在评分公式里。
"""

# 主题门控（topic gate）防止宽泛同义词命中（例如“技术栈”）把不匹配具体主题的 chunk 推高。
TOPIC_GATE_MIN_SCORE = 0.40
INTENT_GATE_MIN_SCORE = 0.75
TOPICLESS_SYNONYM_SCORE_CAP = 0.50

# 保护召回（protected recall）为强 heading 命中和强 keyword 命中各保留一个槽位，避免被高向量噪声完全挤出。
PROTECTED_RECALL_TOP_K = 3
LEXICAL_PROTECTION_MIN_SCORE = 0.70
HEADING_PROTECTION_MIN_SCORE = 0.70

# 字段感知 keyword 评分把 section title 和正文作为主信号。
# 标题路径（heading path）有结构价值但可能过宽，因此先增强再封顶；文件名只作为弱辅助信号，避免纯文件名命中。
KEYWORD_SECTION_MIX_WEIGHT = 0.35
KEYWORD_HEADING_MIX_WEIGHT = 0.25
KEYWORD_CONTENT_MIX_WEIGHT = 0.35
KEYWORD_DOCUMENT_NAME_MIX_WEIGHT = 0.05
KEYWORD_SECTION_BOOST = 1.35
KEYWORD_HEADING_BOOST = 1.20
KEYWORD_HEADING_SCORE_CAP = 0.90
KEYWORD_DOCUMENT_NAME_MULTIPLIER = 0.45

# 三元相似度（trigram）比 keyword 覆盖率更宽松，因此结构增强和文件名贡献都更保守。
TRGM_SECTION_BOOST = 1.20
TRGM_HEADING_BOOST = 1.10
TRGM_HEADING_SCORE_CAP = 0.85
TRGM_DOCUMENT_NAME_MULTIPLIER = 0.40

# 诊断信息（diagnostics）是提示性信息，阈值低于正式召回，用于暴露“可能相关但未参与检索”的文档。
DIAGNOSTIC_RELATED_MATCH_MIN_SCORE = 0.35

# 目录型 chunk 可作为导航线索，但不能压过真实正文；因此降权而不是直接过滤。
DIRECTORY_LIKE_CHUNK_SCORE_MULTIPLIER = 0.45
DIRECTORY_SINGLE_LINE_MIN_MARKER_COUNT = 3
DIRECTORY_SINGLE_LINE_MAX_CHARS = 300
DIRECTORY_SHORT_LINE_MAX_CHARS = 40
DIRECTORY_PROSE_LINE_MIN_CHARS = 30
DIRECTORY_LIST_LIKE_LINE_RATIO = 0.60
DIRECTORY_SHORT_LINE_RATIO = 0.60

# 过短 ASCII 片段（如 ai）歧义太大，不参与精确 token 命中。
MIN_ASCII_MATCH_TERM_LENGTH = 3

SCORE_DECIMAL_PLACES = 6
