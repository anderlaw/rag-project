def test_dashscope_embedding_sends_dimension_and_document_text_type(monkeypatch):
    from app.services.embedding import DashScopeEmbeddingService

    calls = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"output": {"embeddings": [{"embedding": [0.1, 0.2], "text_index": 0}]}}

    def fake_post(**kwargs):
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.embedding.httpx.post", fake_post)

    service = DashScopeEmbeddingService(
        api_key="key",
        api_url="https://example.test/embeddings",
        model="text-embedding-v4",
        dimension=1536,
    )

    assert service.embed(["hello"]) == [[0.1, 0.2]]
    assert calls[0]["json"]["parameters"] == {"text_type": "document", "dimension": 1536}


def test_dashscope_embedding_batches_requests_to_api_limit(monkeypatch):
    from app.services.embedding import DashScopeEmbeddingService

    batch_sizes = []

    class FakeResponse:
        status_code = 200

        def __init__(self, size: int) -> None:
            self.size = size

        def json(self):
            return {
                "output": {
                    "embeddings": [
                        {"embedding": [float(index)], "text_index": index}
                        for index in range(self.size)
                    ]
                }
            }

    def fake_post(**kwargs):
        texts = kwargs["json"]["input"]["texts"]
        batch_sizes.append(len(texts))
        return FakeResponse(len(texts))

    monkeypatch.setattr("app.services.embedding.httpx.post", fake_post)

    service = DashScopeEmbeddingService(
        api_key="key",
        api_url="https://example.test/embeddings",
        model="text-embedding-v4",
        dimension=1536,
        batch_size=16,
    )

    embeddings = service.embed([f"text {index}" for index in range(11)])

    assert batch_sizes == [10, 1]
    assert len(embeddings) == 11


def test_dashscope_query_embedding_sends_query_text_type(monkeypatch):
    from app.services.embedding import DashScopeEmbeddingService

    calls = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"output": {"embeddings": [{"embedding": [0.3, 0.4], "text_index": 0}]}}

    def fake_post(**kwargs):
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.embedding.httpx.post", fake_post)

    service = DashScopeEmbeddingService(
        api_key="key",
        api_url="https://example.test/embeddings",
        model="text-embedding-v4",
        dimension=1536,
    )

    assert service.embed_query("how to reimburse") == [0.3, 0.4]
    assert calls[0]["json"]["parameters"] == {"text_type": "query", "dimension": 1536}

