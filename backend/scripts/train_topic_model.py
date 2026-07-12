#!/usr/bin/env python
"""
Train BERTopic model for customer WhatsApp topics.

This trains an unsupervised topic model from customer inbound messages and saves
it to a path that can be mounted as TOPIC_MODEL_PATH in Docker.

Usage:
    python -m scripts.train_topic_model
    python -m scripts.train_topic_model --source csv --csv-path ../whatsapp_messages.csv
"""
import argparse
import csv
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.feedback import FeedbackLinked, FeedbackRaw
from app.models.topic import Topic, ModelVersion
from app.services.topic_service import TopicService


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = "models/topic_model"
DEFAULT_VERSION_PREFIX = "bertopic"
DEFAULT_TARGET_TOPICS = 30
TRUSTED_LINK_STATUSES = ("verified", "probable")
NOISE_MESSAGES = {
    "[this message was deleted]",
    "this message was deleted",
    "<media omitted>",
    "media omitted",
    "image omitted",
    "video omitted",
    "audio omitted",
    "sticker omitted",
}

TOPIC_LABELS = [
    ("Pendaftaran Member & Outlet", {"daftar", "member", "daftar member", "outlet", "sawojajar", "suhat", "bidan"}),
    ("Request Bidan", {"request", "bidan", "gadis"}),
    ("Homecare & Alamat", {"homecare", "rumah", "alamat", "shareloc", "lokasi", "maps"}),
    ("Reservasi & Jadwal", {"booking", "reservasi", "jadwal", "slot", "besok", "sabtu", "minggu", "jam"}),
    ("Baby Swim", {"swim", "baby swim", "berenang", "renang", "terapi swim"}),
    ("Perawatan Tambahan", {"cuci hidung", "hidung", "potong kuku", "kuku"}),
    ("Pijat Bayi", {"pijat", "pijat bayi", "bayi", "baby", "spa", "treatment"}),
    ("Konsultasi Bayi", {"usia", "bulan", "pilek", "rewel", "aman", "mandi", "tidur"}),
    ("Harga, Promo & Pembayaran", {"harga", "biaya", "paket", "promo", "mahal", "payment", "bayar", "diskon", "point"}),
    ("Pengalaman Positif", {"enak", "nyaman", "sabar", "mantap", "bagus", "terima", "kasih", "makasih"}),
    ("Keluhan Keterlambatan Layanan", {"telat", "terlambat", "keterlambatan", "lama", "10 menit", "menit"}),
    ("Keluhan Layanan", {"kecewa", "kurang", "buruk", "komplain", "tidak puas", "gak puas"}),
]

TOPIC_NAME_STOPWORDS = {
    "maaf",
    "yaa",
    "ya",
    "baik",
    "mbak",
    "kak",
    "bunda",
    "selamat",
    "pagi",
    "hari",
    "kah",
    "ngga",
    "kalo",
    "akan",
    "saya",
    "aku",
    "ini",
    "di",
    "mau",
    "bisa",
    "untuk",
}


def normalize_text(text: str) -> str:
    """Normalize whitespace for topic training without changing meaning."""
    return re.sub(r"\s+", " ", (text or "").strip())


def is_trainable_text(text: str, min_chars: int) -> bool:
    """Keep messages with enough signal for topic modeling."""
    cleaned = normalize_text(text)
    if len(cleaned) < min_chars:
        return False
    lowered = cleaned.casefold()
    if lowered in {
        "ok",
        "oke",
        "iya",
        "ya",
        "baik",
        "sip",
        "thanks",
        "makasih",
        *NOISE_MESSAGES,
    }:
        return False
    return True


def human_topic_name(keywords: List[str], fallback_name: str) -> str:
    keyword_set = {kw.lower() for kw in keywords if kw}
    priority_labels = {
        "Keluhan Keterlambatan Layanan",
        "Keluhan Layanan",
    }
    for label, label_keywords in TOPIC_LABELS:
        if label in priority_labels and keyword_set & label_keywords:
            return label

    best_label = None
    best_score = 0
    for label, label_keywords in TOPIC_LABELS:
        score = len(keyword_set & label_keywords)
        if score > best_score:
            best_label = label
            best_score = score
    high_intent_labels = {
        "Homecare & Alamat",
        "Baby Swim",
        "Perawatan Tambahan",
        "Keluhan Keterlambatan Layanan",
    }
    if best_label and (best_score >= 2 or best_label in high_intent_labels):
        return best_label
    useful_keywords = [
        kw for kw in keywords
        if kw and kw.lower() not in TOPIC_NAME_STOPWORDS
    ]
    clean_name = " / ".join(useful_keywords[:3])
    return clean_name.title() if clean_name else fallback_name


def deduplicate_texts(texts: Iterable[str]) -> List[str]:
    """Remove exact normalized duplicates while preserving chronological order."""
    unique = []
    seen = set()
    for text in texts:
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def load_texts_from_db(
    direction: str,
    min_chars: int,
    limit: int | None,
    trusted_only: bool = True,
) -> List[str]:
    query = FeedbackRaw.query.filter(
        FeedbackRaw.text.isnot(None),
        FeedbackRaw.direction == direction,
    )
    if trusted_only:
        query = query.join(
            FeedbackLinked,
            FeedbackRaw.msg_id == FeedbackLinked.msg_id,
        ).filter(FeedbackLinked.link_status.in_(TRUSTED_LINK_STATUSES))

    query = query.order_by(FeedbackRaw.timestamp.asc())
    texts = [normalize_text(row.text) for row in query.all()]
    texts = deduplicate_texts(
        text for text in texts if is_trainable_text(text, min_chars)
    )
    return texts[:limit] if limit else texts


def load_texts_from_csv(csv_path: str, direction: str, min_chars: int, limit: int | None) -> List[str]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    rows: Iterable[dict]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = {name.lower(): name for name in (reader.fieldnames or [])}
        text_col = (
            fieldnames.get("message_text")
            or fieldnames.get("text")
            or fieldnames.get("message")
            or fieldnames.get("content")
        )
        direction_col = fieldnames.get("direction")
        sender_type_col = fieldnames.get("sender_type")
        if not text_col:
            raise RuntimeError(
                "CSV must contain a text/message/content column. "
                f"Available columns: {reader.fieldnames}"
            )

        texts = []
        for row in reader:
            if direction_col and (row.get(direction_col) or "").lower() != direction.lower():
                continue
            if sender_type_col:
                sender_type = (row.get(sender_type_col) or "").strip().lower()
                row_direction = {
                    "customer": "inbound",
                    "admin": "outbound",
                }.get(sender_type, sender_type)
                if row_direction != direction.lower():
                    continue
            text = normalize_text(row.get(text_col) or "")
            if is_trainable_text(text, min_chars):
                texts.append(text)
    texts = deduplicate_texts(texts)
    return texts[:limit] if limit else texts


def reset_output_path(output_path: str, overwrite: bool) -> None:
    path = Path(output_path)
    if path.exists():
        if not overwrite:
            raise RuntimeError(f"Output path already exists: {output_path}. Use --overwrite to replace it.")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)


def validate_topic_runtime() -> None:
    """Fail fast when the installed BERTopic embedding backend is incompatible."""
    try:
        from sentence_transformers.models import StaticEmbedding  # noqa: F401
    except (ImportError, NameError) as exc:
        raise RuntimeError(
            "Incompatible NLP dependencies: BERTopic requires "
            "sentence_transformers.models.StaticEmbedding. Rebuild the worker "
            "with the pinned requirements before training."
        ) from exc


def upsert_topics(topic_service: TopicService, model_version: str, replace_topics: bool) -> int:
    topic_rows = topic_service.get_all_topics()
    if replace_topics:
        Topic.query.filter_by(model_version=model_version).delete()

    saved = 0
    for row in topic_rows:
        topic_idx = int(row["topic_idx"])
        topic = Topic.query.filter_by(
            topic_idx=topic_idx,
            model_version=model_version,
        ).first()
        if topic is None:
            topic = Topic(topic_idx=topic_idx, model_version=model_version)
            db.session.add(topic)
        keywords = [kw for kw in (row.get("keywords") or []) if kw and kw.strip()]
        topic.name = human_topic_name(keywords, row.get("name") or f"Topic {topic_idx}")
        topic.top_keywords = keywords
        saved += 1

    db.session.commit()
    return saved


def register_topic_model_version(
    model_version: str,
    output_path: str,
    eval_metrics: dict,
) -> None:
    """
    Upsert a ModelVersion record for the trained BERTopic model.

    Stores evaluation metrics (outlier_rate, topic_diversity, silhouette_score,
    warnings) in the ``metrics`` JSON column so training history can be audited
    from the dashboard or admin panel.
    """
    existing = ModelVersion.query.filter_by(model_version=model_version).first()
    if existing:
        existing.model_path = output_path
        existing.metrics = eval_metrics
        existing.trained_at = datetime.utcnow()
        db.session.commit()
        return

    mv = ModelVersion(
        model_version=model_version,
        model_path=output_path,
        trained_at=datetime.utcnow(),
        metrics=eval_metrics,
        deployed=False,
        notes="BERTopic clustering model",
    )
    db.session.add(mv)
    db.session.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train BERTopic from Mamina WhatsApp messages")
    parser.add_argument("--source", choices=["db", "csv"], default="db")
    parser.add_argument("--csv-path", default="../whatsapp_messages.csv")
    parser.add_argument("--direction", default="inbound")
    parser.add_argument("--min-chars", type=int, default=15)
    parser.add_argument("--min-docs", type=int, default=50)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--target-topics", type=int, default=DEFAULT_TARGET_TOPICS)
    parser.add_argument(
        "--no-auto-tune",
        action="store_true",
        help="Disable UMAP/HDBSCAN parameter search before the final fit.",
    )
    parser.add_argument("--output-path", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--replace-topics", action="store_true")
    parser.add_argument(
        "--include-provisional",
        action="store_true",
        help="Include inbound messages from provisional links when source=db.",
    )
    parser.add_argument("--flask-env", default=os.getenv("FLASK_ENV", "development"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = create_app(args.flask_env)

    with app.app_context():
        if args.source == "db":
            texts = load_texts_from_db(
                args.direction,
                args.min_chars,
                args.limit,
                trusted_only=not args.include_provisional,
            )
        else:
            texts = load_texts_from_csv(args.csv_path, args.direction, args.min_chars, args.limit)

        logger.info("Loaded %s trainable texts from %s", len(texts), args.source)
        if len(texts) < args.min_docs:
            raise RuntimeError(
                f"Need at least {args.min_docs} trainable texts, got {len(texts)}. "
                "Import more WhatsApp data or lower --min-docs for experimentation."
            )

        output_path = args.output_path
        model_version = args.model_version or f"{DEFAULT_VERSION_PREFIX}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        validate_topic_runtime()
        reset_output_path(output_path, args.overwrite)

        service = TopicService()
        service.load_model(version=model_version)
        logger.info("Encoding corpus once for clustering and evaluation")
        embeddings = service.embedding_model.encode(
            texts,
            show_progress_bar=False,
            batch_size=64,
        )

        tuning_result = None
        if not args.no_auto_tune:
            tuning_result = service.tune_clustering(
                embeddings,
                max_topics=args.target_topics,
            )
            best_params = tuning_result["best_params"]
            for trial in tuning_result["trials"]:
                logger.info("Clustering tuning trial: %s", trial)
            logger.info("Selected clustering parameters: %s", best_params)
            service.load_model(
                version=model_version,
                clustering_params=best_params,
            )

        train_result = service.train(
            texts,
            embeddings=embeddings,
            target_topics=args.target_topics,
        )
        if not service.save_model(output_path):
            raise RuntimeError(f"Failed to save topic model to {output_path}")

        service.model_version = model_version
        saved_topics = upsert_topics(service, model_version, args.replace_topics)

        # ── Clustering Evaluation ─────────────────────────────────────────────
        topics_list: List[int] = list(train_result.get("topics") or [])
        eval_metrics: dict = {}
        if topics_list:
            try:
                eval_metrics = service.evaluate(
                    texts=texts,
                    topics=topics_list,
                    embeddings=embeddings,
                )
                if tuning_result:
                    eval_metrics["tuning"] = tuning_result
            except Exception as exc:
                logger.warning("Clustering evaluation failed (non-fatal): %s", exc)
                eval_metrics = {"evaluation_error": str(exc)}
        else:
            logger.warning("No topic assignments available; skipping evaluation.")
            eval_metrics = {"evaluation_error": "No topic assignments returned from training."}

        # Persist evaluation to model_versions table
        try:
            register_topic_model_version(
                model_version=model_version,
                output_path=output_path,
                eval_metrics=eval_metrics,
            )
            logger.info("Saved evaluation metrics to model_versions table")
        except Exception as exc:
            logger.warning("Failed to persist evaluation metrics (non-fatal): %s", exc)
        # ─────────────────────────────────────────────────────────────────────

        logger.info("Saved topic model: %s", output_path)
        logger.info("Model version: %s", model_version)
        logger.info("Saved topic metadata rows: %s", saved_topics)
        logger.info("Docker TOPIC_MODEL_PATH should be: /app/%s", output_path.replace("\\", "/"))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
