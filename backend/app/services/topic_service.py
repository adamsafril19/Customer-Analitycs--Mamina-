"""
Topic Service

Uses BERTopic for topic modeling and assignment.
DASHBOARD ONLY - NOT for ML training.

KNOWN LIMITATIONS (acceptable for dashboard):

1. VERSION COUPLING RISK
   - BERTopic.load() may not restore embedding_model correctly
   - If embedding space != topic space, assignments become meaningless
   - Solution: Always save/load embedding_model alongside topic_model

2. CONFIDENCE IS NOT PROBABILITY
   - BERTopic "probability" is cosine similarity in reduced space
   - NOT a calibrated posterior
   - "70% confidence" means "vector is 70% similar to cluster centroid"
   - For dashboard display only, not for statistical inference

3. BATCH TOPIC COLLAPSE
   - transform([msg1, msg2, msg3]) may cause cross-document influence
   - One customer's spam complaints can homogenize all their topics
   - Acceptable for per-customer dashboard, dangerous for cross-customer analysis
"""
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Maximum number of samples used for Silhouette Score computation.
# Silhouette is O(n²) in memory so we cap it to avoid OOM on large corpora.
_SILHOUETTE_MAX_SAMPLES = 5_000
TOPIC_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

INDONESIAN_TOPIC_STOP_WORDS = [
    "ada", "aja", "aku", "apa", "atau", "bisa", "buat", "dari", "dengan",
    "di", "dan", "ini", "itu", "jadi", "jika", "juga", "kak", "kami",
    "kalau", "karena", "ke", "mau", "mohon", "nya", "saja", "saya",
    "sudah", "untuk", "ya", "yang", "yg",
]

DEFAULT_TUNING_CANDIDATES = [
    {"n_neighbors": 10, "n_components": 5, "min_cluster_size": 30, "min_samples": 5},
    {"n_neighbors": 15, "n_components": 5, "min_cluster_size": 40, "min_samples": 5},
    {"n_neighbors": 15, "n_components": 5, "min_cluster_size": 50, "min_samples": 10},
    {"n_neighbors": 30, "n_components": 5, "min_cluster_size": 50, "min_samples": 5},
    {"n_neighbors": 30, "n_components": 10, "min_cluster_size": 50, "min_samples": 10},
    {"n_neighbors": 45, "n_components": 10, "min_cluster_size": 75, "min_samples": 10},
]


class TopicService:
    """
    Topic modeling and assignment service using BERTopic

    DASHBOARD ONLY - ML pipeline does NOT use this.

    Singleton pattern to load model once and reuse.

    Two modes of operation:
    1. Train mode: Build topic model from corpus
    2. Inference mode: Assign topics to new messages
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern - ensure only one instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.topic_model = None
        self.topic_mapping = {}  # topic_idx -> topic_id (UUID)
        self.embedding_model = None
        self.model_version = None  # Track which version is loaded
        self._initialized = True

    def get_model_version(self) -> Optional[str]:
        """Get current loaded model version"""
        return self.model_version

    def load_model(
        self,
        model_path: Optional[str] = None,
        version: Optional[str] = None,
        clustering_params: Optional[Dict[str, int]] = None,
        load_embedding_model: bool = True,
    ) -> None:
        """
        Load existing BERTopic model

        Args:
            model_path: Path to saved BERTopic model. If None, creates empty model.
            version: Model version identifier for tracking
        """
        try:
            from bertopic import BERTopic

            if model_path:
                logger.info(f"Loading topic model from: {model_path}")
                self.embedding_model = None
                if load_embedding_model:
                    from sentence_transformers import SentenceTransformer

                    self.embedding_model = SentenceTransformer(
                        TOPIC_EMBEDDING_MODEL
                    )
                else:
                    from bertopic.backend import BaseEmbedder

                    self.embedding_model = BaseEmbedder()
                self.topic_model = BERTopic.load(
                    model_path,
                    embedding_model=self.embedding_model,
                )
                version_file = Path(model_path) / "model_version.txt"
                saved_version = (
                    version_file.read_text(encoding="utf-8").strip()
                    if version_file.is_file()
                    else None
                )
                self.model_version = (
                    version
                    or saved_version
                    or Path(model_path).name
                )
            else:
                logger.info("Initializing new BERTopic model")
                # Initialize with embedding model
                from sentence_transformers import SentenceTransformer
                from hdbscan import HDBSCAN
                from sklearn.feature_extraction.text import CountVectorizer
                from umap import UMAP

                params = {
                    "n_neighbors": 15,
                    "n_components": 5,
                    "min_cluster_size": 50,
                    "min_samples": 10,
                    **(clustering_params or {}),
                }
                self.embedding_model = SentenceTransformer(
                    TOPIC_EMBEDDING_MODEL
                )
                umap_model = UMAP(
                    n_neighbors=params["n_neighbors"],
                    n_components=params["n_components"],
                    min_dist=0.0,
                    metric="cosine",
                    random_state=42,
                )
                hdbscan_model = HDBSCAN(
                    min_cluster_size=params["min_cluster_size"],
                    min_samples=params["min_samples"],
                    metric="euclidean",
                    prediction_data=True,
                )
                vectorizer_model = CountVectorizer(
                    ngram_range=(1, 2),
                    min_df=2,
                    stop_words=INDONESIAN_TOPIC_STOP_WORDS,
                )
                self.topic_model = BERTopic(
                    embedding_model=self.embedding_model,
                    umap_model=umap_model,
                    hdbscan_model=hdbscan_model,
                    vectorizer_model=vectorizer_model,
                    language="indonesian",
                    nr_topics=None,
                    verbose=False
                )
                self.model_version = version or "new_untrained"

            logger.info(f"Topic model loaded/initialized successfully (version: {self.model_version})")

        except Exception as e:
            logger.error(f"Failed to load topic model: {e}")
            raise

    def tune_clustering(
        self,
        embeddings: np.ndarray,
        candidates: Optional[List[Dict[str, int]]] = None,
        min_topics: int = 5,
        max_topics: int = 30,
    ) -> Dict[str, object]:
        """Select a deterministic UMAP/HDBSCAN configuration on cached embeddings."""
        from hdbscan import HDBSCAN
        from hdbscan.validity import validity_index
        from sklearn.metrics import silhouette_score as sk_silhouette
        from umap import UMAP

        embeddings = np.asarray(embeddings)
        if embeddings.ndim != 2 or len(embeddings) < 3:
            raise ValueError("At least three 2-D embeddings are required for tuning.")

        trials = []
        for raw_params in candidates or DEFAULT_TUNING_CANDIDATES:
            params = dict(raw_params)
            reducer = UMAP(
                n_neighbors=params["n_neighbors"],
                n_components=params["n_components"],
                min_dist=0.0,
                metric="cosine",
                random_state=42,
            )
            reduced = reducer.fit_transform(embeddings)
            clusterer = HDBSCAN(
                min_cluster_size=params["min_cluster_size"],
                min_samples=params["min_samples"],
                metric="euclidean",
                prediction_data=True,
            )
            labels = clusterer.fit_predict(reduced)
            mask = labels != -1
            real_labels = labels[mask]
            n_topics = len(set(real_labels))
            outlier_rate = float(np.mean(labels == -1))

            if n_topics < 2 or len(real_labels) <= n_topics:
                silhouette = -1.0
                dbcv = -1.0
                largest_topic_share = 1.0
            else:
                silhouette = float(
                    sk_silhouette(reduced[mask], real_labels, metric="euclidean")
                )
                dbcv = float(
                    validity_index(
                        reduced.astype(np.float64),
                        labels,
                        metric="euclidean",
                    )
                )
                counts = np.unique(real_labels, return_counts=True)[1]
                largest_topic_share = float(counts.max() / counts.sum())

            topic_penalty = 0.0
            if n_topics < min_topics:
                topic_penalty += (min_topics - n_topics) * 0.10
            if n_topics > max_topics:
                topic_penalty += (n_topics - max_topics) * 0.02
            imbalance_penalty = max(0.0, largest_topic_share - 0.45)
            score = (
                silhouette
                + (0.25 * dbcv)
                - (0.30 * outlier_rate)
                - (0.25 * imbalance_penalty)
                - topic_penalty
            )
            trials.append({
                "params": params,
                "score": round(score, 4),
                "silhouette_cluster_space": round(silhouette, 4),
                "dbcv_score": round(dbcv, 4),
                "outlier_rate": round(outlier_rate, 4),
                "n_topics": n_topics,
                "largest_topic_share": round(largest_topic_share, 4),
            })

        trials.sort(key=lambda trial: trial["score"], reverse=True)
        return {"best_params": trials[0]["params"], "trials": trials}

    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.topic_model is not None

    def train(
        self,
        texts: List[str],
        embeddings: Optional[np.ndarray] = None,
        target_topics: Optional[int] = None,
    ) -> Dict[str, object]:
        """
        Train topic model on corpus

        Args:
            texts: List of text documents
            embeddings: Pre-computed embeddings (optional)
            target_topics: Target number of topics after reduction (optional)

        Returns:
            Dict with training stats and topic info
        """
        if self.topic_model is None:
            self.load_model()

        logger.info(f"Training topic model on {len(texts)} documents")

        # Fit model
        if embeddings is not None:
            topics, probs = self.topic_model.fit_transform(texts, embeddings)
        else:
            topics, probs = self.topic_model.fit_transform(texts)

        if target_topics:
            real_topics = {topic for topic in topics if topic != -1}
            if len(real_topics) > target_topics:
                self.topic_model.reduce_topics(texts, nr_topics=target_topics)
                topics = list(self.topic_model.topics_)
                probs = self.topic_model.probabilities_

        # Get topic info
        topic_info = self.topic_model.get_topic_info()

        logger.info(f"Found {len(topic_info)} topics")

        return {
            "n_topics": len(topic_info),
            "topics": topics,
            "probabilities": probs,
            "topic_info": topic_info.to_dict('records')
        }

    def evaluate(
        self,
        texts: List[str],
        topics: List[int],
        embeddings: Optional[np.ndarray] = None,
        silhouette_sample_size: int = _SILHOUETTE_MAX_SAMPLES,
        random_state: int = 42,
    ) -> Dict[str, object]:
        """
        Evaluate BERTopic clustering quality after training.

        Metrics computed:
          - outlier_rate        : fraction of documents assigned to topic -1
          - n_outliers          : absolute count of outlier documents
          - n_topics_found      : number of real topics (excluding -1)
          - topic_diversity     : uniqueness of top keywords across topics
                                  (0 = all topics share the same words, 1 = fully unique)
          - silhouette_score    : mean intra/inter-cluster tightness in embedding space
                                  (range -1 to 1; higher is better; None if < 2 clusters)
          - silhouette_sampled  : True if sampling was applied for Silhouette computation
          - silhouette_n        : number of samples used for Silhouette computation
          - evaluation_warnings : list of human-readable quality warnings

        INTERPRETATION NOTES:
          - outlier_rate > 0.40  -> consider lowering min_cluster_size in HDBSCAN
          - topic_diversity < 0.50 -> topics may be too similar / redundant
          - silhouette_score < 0.10 -> clusters are poorly separated; consider fewer topics
        """
        if self.topic_model is None:
            raise RuntimeError("Topic model is not loaded. Call load_model() first.")

        n_docs = len(topics)
        n_outliers = sum(1 for t in topics if t == -1)
        outlier_rate = n_outliers / n_docs if n_docs > 0 else 0.0

        # --- Topic counts ---
        topic_info = self.topic_model.get_topic_info()
        real_topic_rows = [row for _, row in topic_info.iterrows() if row["Topic"] != -1]
        n_topics_found = len(real_topic_rows)

        # --- Topic Diversity ---
        # Fraction of unique keywords across all top-N words for each topic.
        # Formula: |unique keywords| / total keywords pooled
        top_n_words = 10
        all_keywords: List[str] = []
        for row in real_topic_rows:
            topic_words = self.topic_model.get_topic(int(row["Topic"]))
            if topic_words:
                all_keywords.extend(word.lower() for word, _ in topic_words[:top_n_words])

        if all_keywords and n_topics_found > 0:
            topic_diversity = round(len(set(all_keywords)) / len(all_keywords), 4)
        else:
            topic_diversity = None

        # --- Silhouette Score (sampled) ---
        silhouette_score_val = None
        silhouette_embedding_space = None
        silhouette_sampled = False
        silhouette_n = 0
        non_outlier_mask = [i for i, t in enumerate(topics) if t != -1]

        if len(set(t for t in topics if t != -1)) >= 2 and len(non_outlier_mask) >= 2:
            try:
                from sklearn.metrics import silhouette_score as sk_silhouette

                # Build or reuse embeddings
                if embeddings is None:
                    logger.info("Silhouette: encoding texts with embedding model ...")
                    if self.embedding_model is not None:
                        embed_source = self.embedding_model
                    else:
                        # Attempt to pull the embedding model out of the BERTopic instance
                        embed_source = getattr(self.topic_model, "embedding_model", None)
                    if embed_source is None:
                        raise RuntimeError(
                            "No embedding model available for Silhouette computation. "
                            "Pass pre-computed embeddings to evaluate()."
                        )
                    all_embeddings = np.array(
                        embed_source.encode(texts, show_progress_bar=False)
                    )
                else:
                    all_embeddings = np.asarray(embeddings)

                # Filter to non-outlier documents only
                filtered_embeddings = all_embeddings[non_outlier_mask]
                filtered_topics = [topics[i] for i in non_outlier_mask]

                # Sample if corpus is large to keep computation tractable
                if len(filtered_embeddings) > silhouette_sample_size:
                    rng = np.random.default_rng(random_state)
                    idx = rng.choice(
                        len(filtered_embeddings),
                        size=silhouette_sample_size,
                        replace=False,
                    )
                    filtered_embeddings = filtered_embeddings[idx]
                    filtered_topics = [filtered_topics[i] for i in idx]
                    silhouette_sampled = True

                silhouette_n = len(filtered_embeddings)

                if len(set(filtered_topics)) >= 2:
                    silhouette_embedding_space = round(
                        float(sk_silhouette(filtered_embeddings, filtered_topics)),
                        4,
                    )

                    # HDBSCAN clusters BERTopic's UMAP output, so this is the
                    # primary silhouette metric for clustering quality.
                    reduced = getattr(
                        getattr(self.topic_model, "umap_model", None),
                        "embedding_",
                        None,
                    )
                    if reduced is not None and len(reduced) == len(topics):
                        reduced = np.asarray(reduced)[non_outlier_mask]
                        if silhouette_sampled:
                            reduced = reduced[idx]
                        silhouette_score_val = round(
                            float(sk_silhouette(reduced, filtered_topics)),
                            4,
                        )
                    else:
                        silhouette_score_val = silhouette_embedding_space
                    logger.info(
                        "Silhouette Score (cluster space): %.4f (n=%d, sampled=%s)",
                        silhouette_score_val,
                        silhouette_n,
                        silhouette_sampled,
                    )
            except ImportError:
                logger.warning(
                    "scikit-learn not available; skipping Silhouette Score computation."
                )
            except Exception as exc:
                logger.warning("Silhouette Score computation failed: %s", exc)

        # --- Quality Warnings ---
        eval_warnings: List[str] = []
        if outlier_rate > 0.40:
            eval_warnings.append(
                f"HIGH OUTLIER RATE: {outlier_rate:.1%} of documents were not assigned to any topic. "
                "Consider lowering min_cluster_size in HDBSCAN or importing more data."
            )
        if topic_diversity is not None and topic_diversity < 0.50:
            eval_warnings.append(
                f"LOW TOPIC DIVERSITY: {topic_diversity:.2f} — topics share many keywords and may be redundant. "
                "Consider reducing target_topics or improving pre-processing."
            )
        if silhouette_score_val is not None and silhouette_score_val < 0.10:
            eval_warnings.append(
                f"LOW SILHOUETTE SCORE: {silhouette_score_val:.4f} — clusters are not well-separated. "
                "Consider fewer target topics or a different HDBSCAN configuration."
            )
        if n_topics_found < 3:
            eval_warnings.append(
                f"VERY FEW TOPICS: only {n_topics_found} topics found. "
                "The model may need more diverse training data."
            )

        result = {
            "outlier_rate": round(outlier_rate, 4),
            "n_outliers": n_outliers,
            "n_docs": n_docs,
            "n_topics_found": n_topics_found,
            "topic_diversity": topic_diversity,
            "silhouette_score": silhouette_score_val,
            "silhouette_cluster_space": silhouette_score_val,
            "silhouette_embedding_space": silhouette_embedding_space,
            "silhouette_sampled": silhouette_sampled,
            "silhouette_n": silhouette_n,
            "evaluation_warnings": eval_warnings,
        }

        # Log summary
        logger.info("=== BERTopic Clustering Evaluation ===")
        logger.info("  Docs           : %d", n_docs)
        logger.info("  Topics found   : %d", n_topics_found)
        logger.info("  Outlier rate   : %.2f%% (%d docs)", outlier_rate * 100, n_outliers)
        logger.info("  Topic diversity: %s", topic_diversity)
        logger.info("  Silhouette     : %s", silhouette_score_val)
        if eval_warnings:
            for w in eval_warnings:
                logger.warning("  [WARN] %s", w)
        else:
            logger.info("  No quality warnings.")
        logger.info("======================================")

        return result

    def predict(self, text: str) -> Tuple[Optional[int], float]:
        """
        Assign topic to single text

        Args:
            text: Input text string

        Returns:
            Tuple of (topic_idx, similarity)
            - topic_idx: Topic index (-1 for outlier), or None if error
            - similarity: Cosine similarity to topic centroid (0-1)
              NOTE: This is NOT a probability, it's embedding distance
        """
        if self.topic_model is None:
            logger.warning("Topic model not loaded, cannot predict")
            return None, 0.0

        if not text or not text.strip():
            return None, 0.0

        try:
            topics, probs = self.topic_model.transform([text])
            topic_idx = topics[0]
            # NOTE: This is similarity score, NOT calibrated probability
            similarity = float(probs[0].max()) if hasattr(probs[0], 'max') else float(probs[0])

            return topic_idx, round(similarity, 4)

        except Exception as e:
            logger.warning(f"Topic prediction failed: {e}")
            return None, 0.0

    def predict_batch(
        self,
        texts: List[str],
        embeddings: Optional[np.ndarray] = None
    ) -> List[Tuple[Optional[int], float]]:
        """
        Assign topics to multiple texts

        Args:
            texts: List of input text strings
            embeddings: Pre-computed embeddings (optional)

        Returns:
            List of (topic_idx, similarity) tuples
            NOTE: similarity is cosine distance, NOT probability
        """
        if self.topic_model is None:
            logger.warning("Topic model not loaded, cannot predict")
            return [(None, 0.0)] * len(texts)

        if not texts:
            return []

        try:
            if embeddings is not None:
                topics, probs = self.topic_model.transform(texts, embeddings)
            else:
                topics, probs = self.topic_model.transform(texts)

            results = []
            for i, (topic_idx, prob) in enumerate(zip(topics, probs)):
                if not texts[i] or not texts[i].strip():
                    results.append((None, 0.0))
                else:
                    # NOTE: This is similarity, NOT probability
                    similarity = float(prob.max()) if hasattr(prob, 'max') else float(prob)
                    results.append((topic_idx, round(similarity, 4)))

            return results

        except Exception as e:
            logger.warning(f"Batch topic prediction failed: {e}")
            return [(None, 0.0)] * len(texts)

    def get_topic_keywords(self, topic_idx: int, n_words: int = 10) -> List[str]:
        """
        Get top keywords for a topic

        Args:
            topic_idx: Topic index
            n_words: Number of keywords to return

        Returns:
            List of top keywords
        """
        if self.topic_model is None:
            return []

        try:
            topic_words = self.topic_model.get_topic(topic_idx)
            if topic_words:
                return [word for word, _ in topic_words[:n_words]]
            return []
        except Exception:
            return []

    def get_all_topics(self) -> List[Dict]:
        """
        Get info for all topics

        Returns:
            List of topic dicts with id, name, keywords
        """
        if self.topic_model is None:
            return []

        try:
            topic_info = self.topic_model.get_topic_info()

            topics = []
            for _, row in topic_info.iterrows():
                topic_idx = row['Topic']
                if topic_idx == -1:  # Skip outlier topic
                    continue

                keywords = self.get_topic_keywords(topic_idx)
                topics.append({
                    "topic_idx": topic_idx,
                    "name": row.get('Name', f'Topic_{topic_idx}'),
                    "count": row.get('Count', 0),
                    "keywords": keywords
                })

            return topics

        except Exception as e:
            logger.error(f"Failed to get topics: {e}")
            return []

    def save_model(self, path: str) -> bool:
        """
        Save trained topic model

        Args:
            path: Path to save model

        Returns:
            True if successful
        """
        if self.topic_model is None:
            logger.error("No model to save")
            return False

        try:
            self.topic_model.save(
                path,
                serialization="safetensors",
                save_ctfidf=True,
                save_embedding_model=(
                    TOPIC_EMBEDDING_MODEL
                ),
            )
            output_path = Path(path)
            if output_path.is_dir() and self.model_version:
                (output_path / "model_version.txt").write_text(
                    self.model_version,
                    encoding="utf-8",
                )
            logger.info(f"Topic model saved to {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save topic model: {e}")
            return False
