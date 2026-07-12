"""Customer-voice context and deterministic intervention recommendations."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import func

from app import db
from app.models.embedding_registry import EmbeddingModelRegistry
from app.models.feedback import FeedbackFeatures, FeedbackLinked, FeedbackRaw
from app.models.prediction import ChurnPrediction
from app.models.recommendation_context import RecommendationContext
from app.models.text_semantics import CustomerTextSemantics
from app.models.text_signals import CustomerTextSignals
from app.models.topic import Topic
from app.services.explainer_service import ExplainerService


class RecommendationContextService:
    POLICY_VERSION = "retention_policy_v2"

    INTENT_KEYWORDS = {
        "complaint": (
            "kecewa", "komplain", "keluhan", "buruk", "terlalu lama", "lambat",
            "tidak nyaman", "marah", "refund", "salah",
        ),
        "scheduling": (
            "jadwal", "booking", "reservasi", "kunjungan", "appointment",
            "slot", "jam", "besok", "hari ini",
        ),
        "price": (
            "harga", "promo", "diskon", "paket", "biaya", "tarif", "voucher",
        ),
        "service": (
            "treatment", "perawatan", "pijat", "spa", "massage", "homecare",
            "facial", "baby", "bayi", "anak", "ibu",
        ),
        "location": (
            "lokasi", "alamat", "cabang", "sawojajar", "malang", "maps",
            "rumah", "datang",
        ),
    }

    def __init__(self):
        self._embedding_model = EmbeddingModelRegistry.get_active()

    def _semantic_snapshot(
        self,
        customer_id,
        as_of_date,
    ) -> Optional[CustomerTextSemantics]:
        return CustomerTextSemantics.query.filter(
            CustomerTextSemantics.customer_id == customer_id,
            CustomerTextSemantics.as_of_date <= as_of_date,
        ).order_by(CustomerTextSemantics.as_of_date.desc()).first()

    def _sentiment_trend(
        self,
        semantics: Optional[CustomerTextSemantics],
    ) -> Optional[float]:
        if not semantics or semantics.avg_sentiment_score is None:
            return None
        prior = CustomerTextSemantics.query.filter(
            CustomerTextSemantics.customer_id == semantics.customer_id,
            CustomerTextSemantics.as_of_date
            <= semantics.as_of_date - timedelta(days=30),
            CustomerTextSemantics.avg_sentiment_score.isnot(None),
        ).order_by(CustomerTextSemantics.as_of_date.desc()).first()
        if not prior:
            return 0.0
        return float(semantics.avg_sentiment_score) - float(
            prior.avg_sentiment_score
        )

    @staticmethod
    def _topic(semantics: Optional[CustomerTextSemantics]) -> Dict[str, Any]:
        topic_id = semantics.get_dominant_topic() if semantics else None
        topic = None
        if topic_id is not None and semantics.topic_model_version:
            try:
                topic = Topic.query.filter_by(
                    topic_idx=int(topic_id),
                    model_version=semantics.topic_model_version,
                ).first()
            except (TypeError, ValueError):
                topic = None
        return {
            "id": str(topic_id) if topic_id is not None else None,
            "name": topic.name if topic else None,
            "keywords": list(topic.top_keywords or []) if topic else [],
        }

    @staticmethod
    def _useful_topic_name(name: Optional[str]) -> str:
        """Suppress topic labels made mostly from conversational filler."""
        normalized = (name or "").strip().lower()
        filler_tokens = {"maaf", "yaa", "ya", "iya", "oke", "ok", "kak"}
        tokens = {
            token.strip(" /,.-")
            for token in normalized.split()
            if token.strip(" /,.-")
        }
        if not normalized or len(tokens - filler_tokens) <= 1:
            return ""
        # Known mixed filler/location labels are not stable business intents.
        if "maaf" in tokens and ("yaa" in tokens or "ya" in tokens):
            return ""
        return normalized

    @staticmethod
    def _number(values: Dict[str, Any], key: str, default: float = 0.0) -> float:
        try:
            value = values.get(key, default)
            return float(default if value is None else value)
        except (TypeError, ValueError):
            return float(default)

    @classmethod
    def _classify_intent(
        cls,
        text: str,
        complaint_ratio: float,
    ) -> Optional[str]:
        normalized = (text or "").lower()
        scores = {
            intent: sum(1 for keyword in keywords if keyword in normalized)
            for intent, keywords in cls.INTENT_KEYWORDS.items()
        }
        if complaint_ratio >= 0.2:
            scores["complaint"] += 2
        best_intent = max(scores, key=scores.get)
        return best_intent if scores[best_intent] > 0 else None

    @classmethod
    def _transaction_signal(cls, values: Optional[Dict[str, Any]]) -> str:
        values = values or {}
        recency = cls._number(values, "recency_days")
        recency_ratio = cls._number(values, "recency_ratio")
        tx_count = cls._number(values, "tx_count_90d")
        frequency_trend = cls._number(values, "frequency_trend_smoothed")
        spend_trend = cls._number(values, "spend_trend_smoothed")
        lifetime_count = cls._number(values, "lifetime_tx_count")
        tenure = cls._number(values, "tenure_days")
        zero_amount = cls._number(values, "zero_amount_tx_count_90d")
        homecare = cls._number(values, "last_tx_is_homecare")

        if zero_amount > 0:
            return "transaction_quality"
        if lifetime_count <= 1 and tenure <= 120:
            return "new_customer"
        if recency >= 180 or (tx_count == 0 and recency >= 120):
            return "dormant"
        if recency >= 90 or recency_ratio >= 1.5:
            return "overdue"
        if frequency_trend < -0.15:
            return "frequency_decline"
        if spend_trend < -0.15:
            return "spend_decline"
        if homecare >= 0.5:
            return "homecare"
        if lifetime_count >= 8:
            return "loyal"
        return "routine"

    @staticmethod
    def _action(
        action_type: str,
        priority: str,
        title: str,
        rationale: str,
        reasons,
        *,
        source: str,
        objective: str,
        timing: str,
        channel: str,
        opening: str,
        business_intent: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "action_type": action_type,
            "priority": priority,
            "title": title,
            "rationale": rationale,
            "reason_codes": list(dict.fromkeys(reasons)),
            "details": {
                "source": source,
                "objective": objective,
                "timing": timing,
                "channel": channel,
                "suggested_opening": opening,
                "business_intent": business_intent,
            },
        }

    @classmethod
    def _policy(
        cls,
        risk_label: str,
        sentiment_label: Optional[str],
        sentiment_score: Optional[float],
        complaint_ratio: float,
        topic_text: str,
        context_available: bool,
        transaction_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        risk_label = (risk_label or "low").lower()
        priority = risk_label if risk_label in {"high", "medium"} else "low"
        reasons = [f"{risk_label.upper()}_RISK"]
        tx_signal = cls._transaction_signal(transaction_context)
        reasons.append(f"TX_{tx_signal.upper()}")

        negative = sentiment_label == "negative" or (
            sentiment_score is not None and sentiment_score <= -0.15
        )
        positive = sentiment_label == "positive" or (
            sentiment_score is not None and sentiment_score >= 0.2
        )
        complaint = complaint_ratio >= 0.2
        intent = cls._classify_intent(topic_text, complaint_ratio) if context_available else None
        if negative:
            reasons.append("NEGATIVE_SENTIMENT")
        if positive:
            reasons.append("POSITIVE_SENTIMENT")
        if complaint:
            reasons.append("COMPLAINT_SIGNAL")

        source = "nlp_and_transaction" if context_available else "transaction"
        timing = "Hari ini" if risk_label == "high" else (
            "Dalam 3 hari" if risk_label == "medium" else "Dalam 7 hari"
        )

        if context_available and (complaint or negative or intent == "complaint"):
            return cls._action(
                "call", "high" if risk_label == "high" else "medium",
                "Pulihkan pengalaman customer sebelum menawarkan promo",
                "Keluhan atau sentimen negatif terdeteksi. Baca pesan bukti, "
                "klarifikasi masalah, lalu sepakati penyelesaian.",
                reasons + ["INTENT_COMPLAINT"], source=source,
                objective="Service recovery dan memastikan masalah terselesaikan",
                timing="Hari ini", channel="Telepon atau WhatsApp personal",
                opening="Kami ingin memastikan pengalaman sebelumnya sudah ditangani. "
                "Boleh diceritakan bagian yang masih kurang nyaman?",
                business_intent="complaint",
            )
        if context_available and intent == "scheduling":
            return cls._action(
                "call", priority,
                "Tuntaskan kebutuhan reservasi yang belum selesai",
                "Percakapan mengandung kebutuhan jadwal atau booking. Tawarkan dua "
                "pilihan waktu yang konkret agar customer mudah memutuskan.",
                reasons + ["INTENT_SCHEDULING", "SCHEDULING_TOPIC"], source=source,
                objective="Mengubah minat reservasi menjadi jadwal terkonfirmasi",
                timing=timing, channel="WhatsApp",
                opening="Untuk jadwal berikutnya, tersedia dua pilihan waktu. "
                "Mana yang paling nyaman untuk Kakak?",
                business_intent="scheduling",
            )
        if context_available and intent == "price":
            return cls._action(
                "promo", priority,
                "Tawarkan opsi layanan sesuai kebutuhan dan anggaran",
                "Customer membahas harga, paket, atau promo. Jelaskan pilihan yang "
                "relevan; hindari mengirim promo massal tanpa konteks.",
                reasons + ["INTENT_PRICE", "PRICE_PROMO_TOPIC"], source=source,
                objective="Mengurangi hambatan harga tanpa diskon berlebihan",
                timing=timing, channel="WhatsApp",
                opening="Kami punya beberapa pilihan layanan dengan manfaat dan "
                "rentang harga berbeda. Boleh kami sesuaikan dengan kebutuhan Kakak?",
                business_intent="price",
            )
        if context_available and intent in {"service", "location"}:
            is_service = intent == "service"
            return cls._action(
                "call" if risk_label == "high" else "email", priority,
                "Jawab kebutuhan layanan secara spesifik" if is_service
                else "Hilangkan hambatan lokasi atau kunjungan",
                "Gunakan topik dan pesan bukti untuk menjawab kebutuhan customer, "
                "kemudian arahkan ke langkah reservasi yang jelas.",
                reasons + [f"INTENT_{intent.upper()}"], source=source,
                objective="Memberi informasi relevan dan mengarahkan ke reservasi",
                timing=timing, channel="WhatsApp",
                opening="Kami menindaklanjuti pertanyaan Kakak agar informasinya "
                "lebih jelas. Kebutuhan utama yang ingin dipastikan apa?",
                business_intent=intent,
            )

        if tx_signal == "transaction_quality":
            return cls._action(
                "review", priority,
                "Verifikasi transaksi bernilai nol sebelum menghubungi customer",
                "Terdapat transaksi bernilai nol pada periode terbaru. Pastikan "
                "pencatatan valid agar follow-up tidak memakai konteks yang keliru.",
                reasons + (["NLP_CONTEXT_AVAILABLE"] if context_available else ["NO_NLP_CONTEXT"]),
                source=source, objective="Menjaga kualitas data tindakan",
                timing="Sebelum follow-up", channel="Review internal",
                opening="Tidak ada pesan pembuka sebelum data transaksi diverifikasi.",
                business_intent=intent,
            )

        tx_actions = {
            "new_customer": (
                "email", "Lakukan onboarding setelah kunjungan pertama",
                "Customer masih baru. Tanyakan pengalaman awal dan jelaskan waktu "
                "kunjungan lanjutan yang sesuai.",
                "Mendorong kunjungan kedua", "WhatsApp",
                "Bagaimana pengalaman kunjungan pertama Kakak? Kami bisa bantu "
                "menyiapkan perawatan lanjutan bila dibutuhkan.",
            ),
            "dormant": (
                "call", "Aktifkan kembali customer yang lama tidak berkunjung",
                "Tidak ada transaksi dalam periode panjang. Mulai dengan check-in "
                "personal, bukan langsung mengirim promo.",
                "Memahami hambatan dan membuka peluang kunjungan kembali",
                "Telepon atau WhatsApp personal",
                "Sudah cukup lama sejak kunjungan terakhir. Bagaimana kabarnya, "
                "dan apakah ada kebutuhan perawatan yang bisa kami bantu?",
            ),
            "overdue": (
                "call", "Ajak booking ulang sesuai pola kunjungan",
                "Jarak dari transaksi terakhir telah melewati pola yang wajar. "
                "Tawarkan jadwal konkret yang mudah dipilih.",
                "Mengonfirmasi kunjungan berikutnya", "WhatsApp",
                "Kunjungan Kakak berikutnya sudah mendekati atau melewati jadwal "
                "biasanya. Mau kami bantu pilihkan waktu?",
            ),
            "frequency_decline": (
                "email", "Tanyakan penyebab frekuensi kunjungan menurun",
                "Frekuensi transaksi menunjukkan tren menurun. Cari hambatan utama "
                "sebelum menentukan penawaran.",
                "Menemukan hambatan kunjungan", "WhatsApp",
                "Kami melihat jadwal kunjungan belakangan lebih jarang. Apakah ada "
                "kendala waktu, layanan, atau hal lain yang bisa kami bantu?",
            ),
            "spend_decline": (
                "promo", "Tawarkan alternatif layanan yang lebih sesuai",
                "Nilai transaksi menunjukkan tren menurun. Tawarkan pilihan manfaat "
                "dan harga yang relevan, bukan diskon seragam.",
                "Menyesuaikan layanan dengan kebutuhan saat ini", "WhatsApp",
                "Kami bisa bantu memilih opsi perawatan yang tetap sesuai kebutuhan "
                "dan anggaran Kakak saat ini.",
            ),
            "homecare": (
                "call", "Tawarkan penjadwalan ulang layanan homecare",
                "Transaksi terakhir menggunakan homecare. Pertahankan channel "
                "layanan tersebut dan konfirmasi area serta waktu kunjungan.",
                "Memudahkan repeat order homecare", "WhatsApp",
                "Apakah Kakak ingin menjadwalkan kembali layanan homecare? Kami "
                "bisa bantu cek waktu dan area kunjungannya.",
            ),
            "loyal": (
                "email", "Lakukan check-in apresiatif kepada customer loyal",
                "Histori transaksi menunjukkan hubungan jangka panjang. Gunakan "
                "apresiasi dan relevansi layanan, bukan pesan retensi generik.",
                "Menjaga hubungan dan memahami kebutuhan berikutnya", "WhatsApp",
                "Terima kasih sudah mempercayakan perawatan kepada kami. Ada "
                "kebutuhan berikutnya yang ingin Kakak konsultasikan?",
            ),
            "routine": (
                "email", "Lakukan check-in berdasarkan aktivitas terakhir",
                "Belum ada sinyal kebutuhan yang kuat. Gunakan konteks transaksi "
                "terakhir dan hindari asumsi tentang isi percakapan.",
                "Menjaga engagement tanpa komunikasi berlebihan", "WhatsApp",
                "Kami ingin memastikan kebutuhan perawatan Kakak tetap terpenuhi. "
                "Apakah ada yang ingin dikonsultasikan?",
            ),
        }
        action_type, title, rationale, objective, channel, opening = tx_actions[tx_signal]
        if risk_label == "high" and action_type == "email":
            action_type = "call"
            channel = "Telepon atau WhatsApp personal"
        if context_available and positive and tx_signal in {"routine", "loyal"}:
            title = "Apresiasi pengalaman positif dan ajak kunjungan berikutnya"
            rationale = (
                "Customer voice cenderung positif. Pertahankan pengalaman tersebut "
                "dan arahkan secara ringan ke kebutuhan berikutnya."
            )
        return cls._action(
            action_type, priority, title, rationale,
            reasons + (["NLP_CONTEXT_AVAILABLE"] if context_available else ["NO_NLP_CONTEXT"]),
            source=source, objective=objective, timing=timing, channel=channel,
            opening=opening, business_intent=intent,
        )

    @staticmethod
    def _sentiment_label(
        semantics: Optional[CustomerTextSemantics],
    ) -> Optional[str]:
        if not semantics:
            return None
        score = (
            float(semantics.avg_sentiment_score)
            if semantics.avg_sentiment_score is not None else None
        )
        distribution = semantics.sentiment_dist or {}
        total = sum(float(value or 0) for value in distribution.values())
        negative_share = (
            float(distribution.get("negative", 0) or 0) / total if total else 0.0
        )
        positive_share = (
            float(distribution.get("positive", 0) or 0) / total if total else 0.0
        )
        if (score is not None and score <= -0.15) or negative_share >= 0.3:
            return "negative"
        if (score is not None and score >= 0.2) or positive_share >= 0.5:
            return "positive"
        return semantics.get_dominant_sentiment()

    @staticmethod
    def _transaction_context(prediction: ChurnPrediction) -> Dict[str, Any]:
        from app.services.feature_service import FeatureService

        values = prediction.features_used or []
        if isinstance(values, dict):
            return values
        if isinstance(values, list):
            names = [name for name, _ in FeatureService.FEATURE_SCHEMA]
            return dict(zip(names, values))
        return {}

    def generate_for_prediction(
        self,
        prediction: ChurnPrediction,
        commit: bool = True,
    ) -> RecommendationContext:
        as_of_date = prediction.as_of_date
        as_of_dt = datetime.combine(as_of_date, time.max)
        semantics = self._semantic_snapshot(prediction.customer_id, as_of_date)
        signals = CustomerTextSignals.query.filter(
            CustomerTextSignals.customer_id == prediction.customer_id,
            CustomerTextSignals.as_of_date <= as_of_date,
        ).order_by(CustomerTextSignals.as_of_date.desc()).first()

        trusted_query = db.session.query(FeedbackRaw).join(
            FeedbackLinked,
            FeedbackRaw.msg_id == FeedbackLinked.msg_id,
        ).filter(
            FeedbackLinked.customer_id == prediction.customer_id,
            FeedbackLinked.link_status.in_(("verified", "probable")),
            FeedbackLinked.match_confidence >= 0.7,
            FeedbackRaw.direction == "inbound",
            FeedbackRaw.timestamp <= as_of_dt,
            FeedbackRaw.timestamp
            >= datetime.combine(as_of_date - timedelta(days=89), time.min),
        )
        message_count = trusted_query.count()
        recent_messages = trusted_query.order_by(
            FeedbackRaw.timestamp.desc()
        ).limit(20).all()
        last_message_at = db.session.query(func.max(FeedbackRaw.timestamp)).join(
            FeedbackLinked,
            FeedbackRaw.msg_id == FeedbackLinked.msg_id,
        ).filter(
            FeedbackLinked.customer_id == prediction.customer_id,
            FeedbackLinked.link_status.in_(("verified", "probable")),
            FeedbackLinked.match_confidence >= 0.7,
            FeedbackRaw.direction == "inbound",
            FeedbackRaw.timestamp <= as_of_dt,
        ).scalar()

        topic = self._topic(semantics)
        complaint_ratio = float(
            signals.complaint_rate_30d
            if signals and signals.complaint_rate_30d is not None
            else 0.0
        )
        sentiment_label = self._sentiment_label(semantics)
        sentiment_score = (
            float(semantics.avg_sentiment_score)
            if semantics and semantics.avg_sentiment_score is not None
            else None
        )
        context_available = message_count > 0
        topic_text = " ".join(
            [
                self._useful_topic_name(topic.get("name")),
                *topic.get("keywords", []),
                *(
                    list((semantics.top_keywords or {}).keys())
                    if semantics
                    and isinstance(semantics.top_keywords, dict)
                    else []
                ),
                *(message.text or "" for message in recent_messages),
            ]
        ).lower()
        transaction_context = self._transaction_context(prediction)
        policy = self._policy(
            prediction.churn_label,
            sentiment_label,
            sentiment_score,
            complaint_ratio,
            topic_text,
            context_available,
            transaction_context,
        )

        evidence = []
        if context_available:
            evidence = ExplainerService().get_nearest_messages(
                str(prediction.customer_id),
                top_n=3,
                as_of=as_of_dt,
            )
        sentiment_trend = self._sentiment_trend(semantics)
        embedding_model_version = (
            self._embedding_model.model_version
            if self._embedding_model else None
        )
        if context_available and not embedding_model_version:
            embedding_version_row = (
                db.session.query(FeedbackFeatures.embedding_model_version)
                .join(
                    FeedbackLinked,
                    FeedbackFeatures.link_id == FeedbackLinked.link_id,
                )
                .join(
                    FeedbackRaw,
                    FeedbackFeatures.msg_id == FeedbackRaw.msg_id,
                )
                .filter(
                    FeedbackLinked.customer_id == prediction.customer_id,
                    FeedbackLinked.link_status.in_(("verified", "probable")),
                    FeedbackRaw.timestamp <= as_of_dt,
                    FeedbackFeatures.embedding.isnot(None),
                    FeedbackFeatures.embedding_model_version.isnot(None),
                )
                .order_by(FeedbackRaw.timestamp.desc())
                .first()
            )
            embedding_model_version = (
                embedding_version_row[0] if embedding_version_row else None
            )

        context = RecommendationContext.query.filter_by(
            pred_id=prediction.pred_id
        ).first()
        if not context:
            context = RecommendationContext(
                pred_id=prediction.pred_id,
                customer_id=prediction.customer_id,
                as_of_date=as_of_date,
            )
            db.session.add(context)

        context.context_status = "available" if context_available else "unavailable"
        context.sentiment_label = sentiment_label
        context.sentiment_score = sentiment_score
        context.sentiment_trend = sentiment_trend
        context.dominant_topic_id = topic["id"]
        context.dominant_topic_name = topic["name"]
        context.topic_similarity = (
            float(semantics.avg_topic_similarity)
            if semantics and semantics.avg_topic_similarity is not None
            else None
        )
        context.complaint_ratio = complaint_ratio
        context.message_count = message_count
        context.last_message_at = last_message_at
        context.evidence_messages = evidence
        context.recommended_action_type = policy["action_type"]
        context.priority = policy["priority"]
        context.title = policy["title"]
        context.rationale = policy["rationale"]
        context.reason_codes = policy["reason_codes"]
        context.recommendation_details = policy["details"]
        context.policy_version = self.POLICY_VERSION
        context.risk_model_version = prediction.model_version
        context.sentiment_model_version = (
            semantics.sentiment_model_version if semantics else None
        )
        context.topic_model_version = (
            semantics.topic_model_version if semantics else None
        )
        context.embedding_model_version = embedding_model_version
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return context

    def backfill_latest(self, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        latest = db.session.query(
            ChurnPrediction.customer_id,
            func.max(ChurnPrediction.created_at).label("created_at"),
        ).group_by(ChurnPrediction.customer_id).subquery()
        predictions = ChurnPrediction.query.join(
            latest,
            (ChurnPrediction.customer_id == latest.c.customer_id)
            & (ChurnPrediction.created_at == latest.c.created_at),
        ).all()

        processed = 0
        failed = 0
        errors = []

        if progress_callback:
            progress_callback(20)

        for i, prediction in enumerate(predictions):
            if progress_callback and i % max(1, len(predictions) // 20) == 0:
                progress_callback(20 + int(80 * i / max(1, len(predictions))))
            try:
                self.generate_for_prediction(prediction, commit=False)
                db.session.commit()
                processed += 1
            except Exception as exc:
                db.session.rollback()
                failed += 1
                if len(errors) < 10:
                    errors.append(f"{prediction.pred_id}: {exc}")
        return {
            "success": failed == 0,
            "total": len(predictions),
            "processed": processed,
            "failed": failed,
            "errors": errors,
        }
