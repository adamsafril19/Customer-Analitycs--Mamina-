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
from typing import List, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


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
    
    def load_model(self, model_path: Optional[str] = None, version: Optional[str] = None) -> None:
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
                self.topic_model = BERTopic.load(model_path)
                # Extract version from path or use provided
                self.model_version = version or model_path.split("/")[-1]
            else:
                logger.info("Initializing new BERTopic model")
                # Initialize with embedding model
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer(
                    'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
                )
                self.topic_model = BERTopic(
                    embedding_model=self.embedding_model,
                    language="indonesian",
                    verbose=False
                )
                self.model_version = version or "new_untrained"
            
            logger.info(f"Topic model loaded/initialized successfully (version: {self.model_version})")
            
        except Exception as e:
            logger.error(f"Failed to load topic model: {e}")
            raise
    
    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.topic_model is not None
    
    def train(
        self, 
        texts: List[str], 
        embeddings: Optional[np.ndarray] = None
    ) -> Dict[str, any]:
        """
        Train topic model on corpus
        
        Args:
            texts: List of text documents
            embeddings: Pre-computed embeddings (optional)
            
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
        
        # Get topic info
        topic_info = self.topic_model.get_topic_info()
        
        logger.info(f"Found {len(topic_info)} topics")
        
        return {
            "n_topics": len(topic_info),
            "topics": topics,
            "probabilities": probs,
            "topic_info": topic_info.to_dict('records')
        }
    
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
            self.topic_model.save(path)
            logger.info(f"Topic model saved to {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save topic model: {e}")
            return False
