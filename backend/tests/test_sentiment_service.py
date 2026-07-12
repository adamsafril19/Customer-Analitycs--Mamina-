"""Unit tests for sentiment checkpoint label normalization."""
from types import SimpleNamespace

from app.services.sentiment_service import SentimentService


def test_configure_labels_uses_checkpoint_mapping():
    service = SentimentService()
    service.model = SimpleNamespace(
        config=SimpleNamespace(
            num_labels=3,
            id2label={0: "positive", 1: "negative", 2: "neutral"},
        )
    )

    service._configure_labels()

    assert service.index_labels == ["positive", "negative", "neutral"]


def test_configure_labels_supports_indonesian_aliases():
    service = SentimentService()
    service.model = SimpleNamespace(
        config=SimpleNamespace(
            num_labels=3,
            id2label={0: "negatif", 1: "netral", 2: "positif"},
        )
    )

    service._configure_labels()

    assert service.index_labels == ["negative", "neutral", "positive"]
