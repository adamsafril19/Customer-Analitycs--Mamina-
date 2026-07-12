"""
Tests for repaired NLP pipeline behavior.
"""
import pytest
from flask import Flask
from types import SimpleNamespace
from datetime import datetime, timedelta


class TestMessageFeatureRules:
    def test_detect_complaint_contextual_rules(self):
        from app.services.message_feature_service import MessageFeatureService

        assert MessageFeatureService.detect_complaint(
            "Saya sangat kecewa dengan SOP Mamina, bidan tidak cuci tangan"
        )
        assert MessageFeatureService.detect_complaint(
            "Admin balasnya lama banget dan terapis belum datang"
        )
        assert MessageFeatureService.detect_complaint(
            "Treatment oralcare tidak benar-benar bersih atau rapi"
        )
        assert not MessageFeatureService.detect_complaint("Terima kasih, pelayanan bagus")
        assert not MessageFeatureService.detect_complaint(
            "Nama Bayi: Rara. Keluhan: tidur kurang nyenyak. Jenis Treatment: pijat bayi"
        )
        assert not MessageFeatureService.detect_complaint(
            "Kak maaf saya agak telat 10 menit karena masih di jalan"
        )
        assert not MessageFeatureService.detect_complaint(
            "ASI saya seret dan bayi rewel, apakah bisa konsultasi laktasi?"
        )

    def test_detect_refund_request_keywords(self):
        from app.services.message_feature_service import MessageFeatureService

        assert MessageFeatureService.detect_refund_request("Tolong refund uang saya")
        assert MessageFeatureService.detect_refund_request("Saya mau cancel booking")
        assert MessageFeatureService.detect_refund_request("Bisa uang kembali?")
        assert not MessageFeatureService.detect_refund_request("Mau booking untuk besok")

    def test_refund_counts_as_complaint(self):
        from app.services.message_feature_service import MessageFeatureService

        assert MessageFeatureService.detect_complaint("Tolong refund uang saya")

    def test_batch_embedding_stores_vector_and_model_version(self):
        from app.services.message_feature_service import MessageFeatureService

        class FakeEmbeddingService:
            def get_model_version(self):
                return "embedding-v1"

            def encode_batch(self, texts, batch_size):
                assert texts == ["pesan satu", "pesan dua"]
                assert batch_size == 64
                return [[0.1, 0.2], [0.3, 0.4]]

        first = SimpleNamespace(embedding=None, embedding_model_version=None)
        second = SimpleNamespace(embedding=None, embedding_model_version=None)
        service = MessageFeatureService()
        service._embedding_service = FakeEmbeddingService()

        failed = service._assign_batch_embeddings(
            [(first, "pesan satu"), (second, "pesan dua")]
        )

        assert failed == 0
        assert first.embedding == [0.1, 0.2]
        assert second.embedding_model_version == "embedding-v1"


def test_semantic_topic_filter_excludes_bertopic_outlier():
    from app.services.semantic_service import SemanticService

    assert SemanticService._is_assignable_topic(0)
    assert SemanticService._is_assignable_topic("2")
    assert not SemanticService._is_assignable_topic(-1)
    assert not SemanticService._is_assignable_topic(None)


def test_response_time_pairs_first_inbound_with_next_admin_reply():
    from app.services.etl_service import ETLService

    started = datetime(2026, 1, 1, 9, 0)

    def row(direction, minutes):
        raw = SimpleNamespace(
            direction=direction,
            timestamp=started + timedelta(minutes=minutes),
        )
        feature = SimpleNamespace(response_time_secs=999)
        return raw, feature

    first = row("inbound", 0)
    follow_up = row("inbound", 2)
    reply = row("outbound", 5)
    second = row("inbound", 10)
    second_reply = row("outbound", 12)

    updated = ETLService._apply_response_times(
        [first, follow_up, reply, second, second_reply]
    )

    assert updated == 2
    assert first[1].response_time_secs == 300
    assert follow_up[1].response_time_secs is None
    assert reply[1].response_time_secs is None
    assert second[1].response_time_secs == 120


class _FakeSentimentService:
    def __init__(self, loaded=True):
        self.loaded = loaded
        self.load_called = False

    def is_model_loaded(self):
        return self.loaded

    def load_model(self):
        self.load_called = True
        self.loaded = True


class _FakeTopicService:
    def __init__(self, loaded=False):
        self.loaded = loaded
        self.load_called_with = None

    def is_model_loaded(self):
        return self.loaded

    def load_model(
        self,
        model_path=None,
        version=None,
        load_embedding_model=True,
    ):
        self.load_called_with = model_path
        self.load_embedding_model = load_embedding_model
        self.loaded = True


class TestSemanticStrictLoading:
    def test_strict_requires_topic_model_path(self):
        flask_app = Flask(__name__)
        flask_app.config["NLP_STRICT"] = True
        flask_app.config["TOPIC_MODEL_PATH"] = None

        with flask_app.app_context():
            from app.services.semantic_service import SemanticService

            service = SemanticService()
            service._sentiment_service = _FakeSentimentService(loaded=True)
            service._topic_service = _FakeTopicService(loaded=False)

            with pytest.raises(RuntimeError, match="TOPIC_MODEL_PATH"):
                service.ensure_models_loaded()

    def test_loads_topic_model_from_config(self):
        flask_app = Flask(__name__)
        flask_app.config["NLP_STRICT"] = True
        flask_app.config["TOPIC_MODEL_PATH"] = "/app/models/topic_model"

        with flask_app.app_context():
            from app.services.semantic_service import SemanticService

            topic = _FakeTopicService(loaded=False)
            service = SemanticService()
            service._sentiment_service = _FakeSentimentService(loaded=True)
            service._topic_service = topic

            service.ensure_models_loaded()

            assert topic.load_called_with == "/app/models/topic_model"
            assert topic.load_embedding_model is False
