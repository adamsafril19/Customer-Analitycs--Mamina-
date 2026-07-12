"""Tests for BERTopic corpus preparation and reduction behavior."""
import csv
import sys
import types

import numpy as np
import pandas as pd

from app.services.topic_service import TopicService
from scripts.train_topic_model import (
    deduplicate_texts,
    is_trainable_text,
    load_texts_from_csv,
)


def test_topic_training_filters_noise_and_exact_duplicates():
    assert not is_trainable_text("[this message was deleted]", min_chars=15)
    assert not is_trainable_text("<Media omitted>", min_chars=5)
    assert is_trainable_text("Mau booking treatment besok pagi", min_chars=15)

    assert deduplicate_texts(
        ["Mau booking besok", "mau booking besok", "Harga paket berapa?"]
    ) == ["Mau booking besok", "Harga paket berapa?"]


def test_csv_loader_supports_ready_to_import_schema(tmp_path):
    path = tmp_path / "messages.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "message_id",
                "phone_number",
                "message_timestamp",
                "sender_type",
                "message_text",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "message_id": "m1",
                "phone_number": "6281",
                "message_timestamp": "2026-01-01 09:00:00",
                "sender_type": "customer",
                "message_text": "Mau booking treatment besok pagi",
            }
        )
        writer.writerow(
            {
                "message_id": "m2",
                "phone_number": "6281",
                "message_timestamp": "2026-01-01 09:01:00",
                "sender_type": "admin",
                "message_text": "Baik, tersedia jam sepuluh pagi",
            }
        )

    assert load_texts_from_csv(
        str(path),
        direction="inbound",
        min_chars=15,
        limit=None,
    ) == ["Mau booking treatment besok pagi"]


class _FakeTopicModel:
    def __init__(self):
        self.topics_ = None
        self.probabilities_ = None
        self.reduce_called = False

    def fit_transform(self, texts):
        self.topics_ = [0, 1, 2, -1]
        self.probabilities_ = [0.9, 0.8, 0.7, 0.0]
        return list(self.topics_), list(self.probabilities_)

    def reduce_topics(self, texts, nr_topics):
        self.reduce_called = True
        self.topics_ = [0, 0, 1, -1]
        self.probabilities_ = [0.9, 0.8, 0.7, 0.0]
        return self

    def get_topic_info(self):
        return pd.DataFrame(
            [
                {"Topic": -1, "Name": "Outlier"},
                {"Topic": 0, "Name": "Booking"},
                {"Topic": 1, "Name": "Harga"},
            ]
        )


def test_topic_reduction_uses_updated_model_assignments():
    service = TopicService()
    original_model = service.topic_model
    fake_model = _FakeTopicModel()
    service.topic_model = fake_model

    try:
        result = service.train(
            ["doc one", "doc two", "doc three", "doc four"],
            target_topics=2,
        )
    finally:
        service.topic_model = original_model

    assert fake_model.reduce_called is True
    assert result["topics"] == [0, 0, 1, -1]
    assert result["probabilities"] == [0.9, 0.8, 0.7, 0.0]


def test_tuning_returns_highest_scoring_candidate(monkeypatch):
    service = TopicService()

    class FakeUMAP:
        def __init__(self, n_neighbors, **kwargs):
            self.n_neighbors = n_neighbors

        def fit_transform(self, embeddings):
            result = np.asarray(embeddings, dtype=float).copy()
            result[:, 0] *= self.n_neighbors
            return result

    class FakeHDBSCAN:
        def __init__(self, min_cluster_size, **kwargs):
            self.min_cluster_size = min_cluster_size

        def fit_predict(self, reduced):
            if self.min_cluster_size == 10:
                return np.array([0, 0, 1, 1, -1, -1])
            return np.array([0, 0, 0, 1, 1, 1])

    fake_umap_module = types.ModuleType("umap")
    fake_umap_module.UMAP = FakeUMAP
    fake_hdbscan_module = types.ModuleType("hdbscan")
    fake_hdbscan_module.HDBSCAN = FakeHDBSCAN
    fake_validity_module = types.ModuleType("hdbscan.validity")
    fake_validity_module.validity_index = lambda *args, **kwargs: 0.4
    monkeypatch.setitem(sys.modules, "umap", fake_umap_module)
    monkeypatch.setitem(sys.modules, "hdbscan", fake_hdbscan_module)
    monkeypatch.setitem(sys.modules, "hdbscan.validity", fake_validity_module)
    monkeypatch.setattr(
        "sklearn.metrics.silhouette_score",
        lambda features, labels, metric: 0.7 if len(features) == 6 else 0.2,
    )

    result = service.tune_clustering(
        np.arange(12).reshape(6, 2),
        candidates=[
            {"n_neighbors": 5, "n_components": 2, "min_cluster_size": 10, "min_samples": 2},
            {"n_neighbors": 10, "n_components": 2, "min_cluster_size": 20, "min_samples": 2},
        ],
        min_topics=2,
        max_topics=3,
    )

    assert result["best_params"]["min_cluster_size"] == 20
    assert len(result["trials"]) == 2
