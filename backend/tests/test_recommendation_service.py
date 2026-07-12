"""Tests for customer-voice decision support policy."""
from app.services.recommendation_service import RecommendationContextService


def test_policy_falls_back_without_nlp_context():
    result = RecommendationContextService._policy(
        risk_label="high",
        sentiment_label=None,
        sentiment_score=None,
        complaint_ratio=0.0,
        topic_text="",
        context_available=False,
    )

    assert result["action_type"] == "call"
    assert result["priority"] == "high"
    assert "NO_NLP_CONTEXT" in result["reason_codes"]
    assert result["details"]["source"] == "transaction"


def test_policy_prioritizes_service_recovery_for_negative_voice():
    result = RecommendationContextService._policy(
        risk_label="medium",
        sentiment_label="negative",
        sentiment_score=-0.7,
        complaint_ratio=0.3,
        topic_text="pelayanan",
        context_available=True,
    )

    assert result["action_type"] == "call"
    assert result["priority"] == "medium"
    assert "NEGATIVE_SENTIMENT" in result["reason_codes"]
    assert "COMPLAINT_SIGNAL" in result["reason_codes"]


def test_policy_maps_price_topic_to_promotion():
    result = RecommendationContextService._policy(
        risk_label="high",
        sentiment_label="neutral",
        sentiment_score=0.0,
        complaint_ratio=0.0,
        topic_text="informasi harga paket promo",
        context_available=True,
    )

    assert result["action_type"] == "promo"
    assert "PRICE_PROMO_TOPIC" in result["reason_codes"]


def test_transaction_fallback_uses_customer_lifecycle_signal():
    dormant = RecommendationContextService._policy(
        risk_label="high",
        sentiment_label=None,
        sentiment_score=None,
        complaint_ratio=0.0,
        topic_text="",
        context_available=False,
        transaction_context={
            "recency_days": 210,
            "tx_count_90d": 0,
            "tenure_days": 500,
            "lifetime_tx_count": 5,
        },
    )
    new_customer = RecommendationContextService._policy(
        risk_label="high",
        sentiment_label=None,
        sentiment_score=None,
        complaint_ratio=0.0,
        topic_text="",
        context_available=False,
        transaction_context={
            "recency_days": 30,
            "tx_count_90d": 1,
            "tenure_days": 45,
            "lifetime_tx_count": 1,
        },
    )

    assert dormant["title"] != new_customer["title"]
    assert "TX_DORMANT" in dormant["reason_codes"]
    assert "TX_NEW_CUSTOMER" in new_customer["reason_codes"]


def test_policy_extracts_service_intent_from_message_text():
    result = RecommendationContextService._policy(
        risk_label="medium",
        sentiment_label="neutral",
        sentiment_score=0.0,
        complaint_ratio=0.0,
        topic_text="mau tanya pijat bayi bisa homecare",
        context_available=True,
        transaction_context={"last_tx_is_homecare": 1},
    )

    assert result["details"]["business_intent"] == "service"
    assert result["details"]["source"] == "nlp_and_transaction"
    assert "INTENT_SERVICE" in result["reason_codes"]


def test_sentiment_summary_does_not_hide_material_negative_share():
    class Semantics:
        avg_sentiment_score = -0.05
        sentiment_dist = {"neutral": 6, "negative": 4, "positive": 0}

        @staticmethod
        def get_dominant_sentiment():
            return "neutral"

    assert RecommendationContextService._sentiment_label(Semantics()) == "negative"


def test_generic_bertopic_label_is_not_treated_as_business_intent():
    assert (
        RecommendationContextService._useful_topic_name(
            "Maaf / Sawojajar / Yaa"
        )
        == ""
    )
