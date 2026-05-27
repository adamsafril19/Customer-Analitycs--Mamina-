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
from app.models.feedback import FeedbackRaw
from app.models.topic import Topic
from app.services.topic_service import TopicService


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = "models/topic_model"
DEFAULT_VERSION_PREFIX = "bertopic"
DEFAULT_TARGET_TOPICS = 30

TOPIC_LABELS = [
    ("Reservasi & Jadwal", {"booking", "reservasi", "jadwal", "slot", "besok", "sabtu", "minggu", "jam"}),
    ("Pijat Bayi", {"pijat", "bayi", "baby", "spa", "treatment"}),
    ("Konsultasi Bayi", {"usia", "bulan", "pilek", "rewel", "aman", "mandi", "tidur"}),
    ("Harga & Paket", {"harga", "biaya", "paket", "promo", "mahal"}),
    ("Pengalaman Positif", {"enak", "nyaman", "sabar", "mantap", "bagus", "terima", "kasih", "makasih"}),
    ("Keluhan Layanan", {"telat", "lama", "kecewa", "kurang", "buruk", "komplain"}),
]


def normalize_text(text: str) -> str:
    """Normalize whitespace for topic training without changing meaning."""
    return re.sub(r"\s+", " ", (text or "").strip())


def is_trainable_text(text: str, min_chars: int) -> bool:
    """Keep messages with enough signal for topic modeling."""
    cleaned = normalize_text(text)
    if len(cleaned) < min_chars:
        return False
    if cleaned.lower() in {"ok", "oke", "iya", "ya", "baik", "sip", "thanks", "makasih"}:
        return False
    return True


def human_topic_name(keywords: List[str], fallback_name: str) -> str:
    keyword_set = {kw.lower() for kw in keywords if kw}
    best_label = None
    best_score = 0
    for label, label_keywords in TOPIC_LABELS:
        score = len(keyword_set & label_keywords)
        if score > best_score:
            best_label = label
            best_score = score
    if best_label:
        return best_label
    clean_name = " / ".join(keywords[:3])
    return clean_name.title() if clean_name else fallback_name


def load_texts_from_db(direction: str, min_chars: int, limit: int | None) -> List[str]:
    query = FeedbackRaw.query.filter(
        FeedbackRaw.text.isnot(None),
        FeedbackRaw.direction == direction,
    ).order_by(FeedbackRaw.timestamp.asc())
    if limit:
        query = query.limit(limit)
    texts = [normalize_text(row.text) for row in query.all()]
    return [text for text in texts if is_trainable_text(text, min_chars)]


def load_texts_from_csv(csv_path: str, direction: str, min_chars: int, limit: int | None) -> List[str]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    rows: Iterable[dict]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = {name.lower(): name for name in (reader.fieldnames or [])}
        text_col = fieldnames.get("text") or fieldnames.get("message") or fieldnames.get("content")
        direction_col = fieldnames.get("direction")
        if not text_col:
            raise RuntimeError(
                "CSV must contain a text/message/content column. "
                f"Available columns: {reader.fieldnames}"
            )

        texts = []
        for row in reader:
            if direction_col and (row.get(direction_col) or "").lower() != direction.lower():
                continue
            text = normalize_text(row.get(text_col) or "")
            if is_trainable_text(text, min_chars):
                texts.append(text)
            if limit and len(texts) >= limit:
                break
    return texts


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train BERTopic from Mamina WhatsApp messages")
    parser.add_argument("--source", choices=["db", "csv"], default="db")
    parser.add_argument("--csv-path", default="../whatsapp_messages.csv")
    parser.add_argument("--direction", default="inbound")
    parser.add_argument("--min-chars", type=int, default=15)
    parser.add_argument("--min-docs", type=int, default=50)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--target-topics", type=int, default=DEFAULT_TARGET_TOPICS)
    parser.add_argument("--output-path", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--replace-topics", action="store_true")
    parser.add_argument("--flask-env", default=os.getenv("FLASK_ENV", "development"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = create_app(args.flask_env)

    with app.app_context():
        if args.source == "db":
            texts = load_texts_from_db(args.direction, args.min_chars, args.limit)
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

        reset_output_path(output_path, args.overwrite)

        service = TopicService()
        service.load_model(version=model_version)
        service.train(texts, target_topics=args.target_topics)
        if not service.save_model(output_path):
            raise RuntimeError(f"Failed to save topic model to {output_path}")

        service.model_version = model_version
        saved_topics = upsert_topics(service, model_version, args.replace_topics)

        logger.info("Saved topic model: %s", output_path)
        logger.info("Model version: %s", model_version)
        logger.info("Saved topic metadata rows: %s", saved_topics)
        logger.info("Docker TOPIC_MODEL_PATH should be: /app/%s", output_path.replace("\\", "/"))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
