"""
Tests for repaired NLP pipeline behavior.
"""
import pytest
from flask import Flask


class TestMessageFeatureRules:
    def test_detect_complaint_keywords(self):
        from app.services.message_feature_service import MessageFeatureService

        assert MessageFeatureService.detect_complaint("Saya sangat kecewa dengan layanan ini")
        assert MessageFeatureService.detect_complaint("Treatment telat dan lama banget")
        assert MessageFeatureService.detect_complaint("Produknya tidak sesuai")
        assert not MessageFeatureService.detect_complaint("Terima kasih, pelayanan bagus")

    def test_detect_refund_request_keywords(self):
        from app.services.message_feature_service import MessageFeatureService

        assert MessageFeatureService.detect_refund_request("Tolong refund uang saya")
        assert MessageFeatureService.detect_refund_request("Saya mau cancel booking")
        assert MessageFeatureService.detect_refund_request("Bisa uang kembali?")
        assert not MessageFeatureService.detect_refund_request("Mau booking untuk besok")

    def test_refund_counts_as_complaint(self):
        from app.services.message_feature_service import MessageFeatureService

        assert MessageFeatureService.detect_complaint("Tolong refund uang saya")


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

    def load_model(self, model_path=None, version=None):
        self.load_called_with = model_path
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
