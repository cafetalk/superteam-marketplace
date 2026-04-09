"""Tests for _shared/embedding.py"""
import json, sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
import embedding


class TestGetEmbedding:
    def test_returns_1536_dim(self):
        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps({
            "output": {"embeddings": [{"embedding": [0.1] * 1536}]}
        }).encode()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test"}), \
             patch("urllib.request.urlopen", return_value=fake_resp):
            vec = embedding.get_embedding("hello")
        assert len(vec) == 1536


class TestGetEmbeddingsBatch:
    def test_batch_splits_at_25(self):
        call_count = [0]
        def mock_urlopen(req, timeout=60):
            call_count[0] += 1
            body = json.loads(req.data.decode())
            n = len(body["input"]["texts"])
            resp = MagicMock()
            resp.read.return_value = json.dumps({
                "output": {"embeddings": [{"embedding": [0.1] * 1536} for _ in range(n)]}
            }).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test"}), \
             patch("urllib.request.urlopen", side_effect=mock_urlopen):
            vecs = embedding.get_embeddings_batch(["text"] * 30)
        assert len(vecs) == 30
        assert call_count[0] == 2

    def test_batch_preserves_order(self):
        def mock_urlopen(req, timeout=60):
            body = json.loads(req.data.decode())
            texts = body["input"]["texts"]
            resp = MagicMock()
            resp.read.return_value = json.dumps({
                "output": {"embeddings": [
                    {"embedding": [float(i)] * 1536} for i, _ in enumerate(texts)
                ]}
            }).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test"}), \
             patch("urllib.request.urlopen", side_effect=mock_urlopen):
            vecs = embedding.get_embeddings_batch(["a", "b", "c"])
        assert vecs[0][0] == 0.0
        assert vecs[1][0] == 1.0
        assert vecs[2][0] == 2.0

    def test_empty_input(self):
        assert embedding.get_embeddings_batch([]) == []

    def test_single_text(self):
        def mock_urlopen(req, timeout=60):
            resp = MagicMock()
            resp.read.return_value = json.dumps({
                "output": {"embeddings": [{"embedding": [0.5] * 1536}]}
            }).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test"}), \
             patch("urllib.request.urlopen", side_effect=mock_urlopen):
            vecs = embedding.get_embeddings_batch(["hello"])
        assert len(vecs) == 1
        assert len(vecs[0]) == 1536
