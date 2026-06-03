import numpy as np


def test_vector_scoring_accepts_pgvector_array_embeddings():
    from app.services.rag_debug_service import _has_embedding, _vector_score

    embedding = np.array([0.2, 0.4, 0.6])

    assert _has_embedding(embedding) is True
    assert _vector_score([0.2, 0.4, 0.6], embedding) == 1
