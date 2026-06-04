import hashlib

import httpx

from app.core.config import Settings

DASHSCOPE_MAX_BATCH_SIZE = 10


class FakeEmbeddingService:
    def __init__(self, *, dimension: int) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [round((digest[index % len(digest)] / 127.5) - 1.0, 6) for index in range(self.dimension)]


class DashScopeEmbeddingService:
    def __init__(
        self,
        *,
        api_key: str,
        api_url: str,
        model: str,
        dimension: int,
        batch_size: int = DASHSCOPE_MAX_BATCH_SIZE,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.dimension = dimension
        self.batch_size = max(1, min(batch_size, DASHSCOPE_MAX_BATCH_SIZE))
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for batch in _batched(texts, self.batch_size):
            # extend表示：把另一个列表里的元素，一个个追加到 embeddings 这个列表里。
            embeddings.extend(self._embed_batch(batch, text_type="document"))
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        # 调用API获取问题对应的向量
        return self._embed_batch([text], text_type="query")[0]
    # 调用模型获取文本对应的向量
    def _embed_batch(self, texts: list[str], *, text_type: str) -> list[list[float]]:
        # 同步发起http请求到 DashScope 的 embedding API，获取文本的向量表示
        response = httpx.post(
            url=self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": {"texts": texts},
                "parameters": {"text_type": text_type, "dimension": self.dimension},
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"DashScope embedding failed: {response.text}")
        data = response.json()
        embeddings = data.get("output", {}).get("embeddings", [])
        if len(embeddings) != len(texts):
            raise RuntimeError("DashScope embedding response size mismatch")
        return [item["embedding"] for item in embeddings]


def create_embedding_service(settings: Settings):
    if settings.embedding_provider == "fake":
        return FakeEmbeddingService(dimension=settings.embedding_dimension)
    assert settings.dashscope_api_key is not None
    return DashScopeEmbeddingService(
        api_key=settings.dashscope_api_key,
        api_url=settings.dashscope_api_url,
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
        batch_size=settings.embedding_batch_size,
    )

# 分批后的文本列表，例如 [["text1", "text2"], ["text3"]]
def _batched(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
