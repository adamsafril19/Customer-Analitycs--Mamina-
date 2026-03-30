"""
Embedding Service

SEMANTIC REPRESENTATION SERVICE - NOT SAFE FOR RAW ML

Sentence-transformers map meaning to vector space.
This is compressed meaning, NOT statistical signal.

IMPORTANT WARNINGS:
1. Embedding = semantic representation (not like msg_length)
2. If model changes, old embeddings become incompatible
3. Zero vectors should NEVER be stored (they're fake signals)
4. Singleton only works in single-process mode

For production with multiple workers, use:
- Shared model loading via Redis/pickle
- Or accept each worker loads model separately
"""
import logging
import hashlib
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Embedding Service using sentence-transformers
    
    SEMANTIC REPRESENTATION - not safe for raw ML without identity resolution.
    
    WARNING: Singleton pattern only works per-process.
    In gunicorn/uvicorn with multiple workers, each worker loads its own model.
    """
    
    _instance = None
    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM = 384
    
    def __new__(cls):
        """Singleton pattern - ensure only one instance PER PROCESS"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.model = None
        self.model_version = None  # Track for semantic continuity
        self.model_config_hash = None  # Actual config-based hash
        self._initialized = True
    
    def get_model_version(self) -> str:
        """
        Get model version identifier for versioning stored embeddings.
        Format: model_name|dim (e.g., "MiniLM-L12-v2|384")
        
        WARNING: This is name-based, not weight-based.
        Models with same name can have different weights over time.
        For production, use get_model_hash() which includes config.
        """
        if self.model_version:
            return self.model_version
        # Extract short name from full model path
        short_name = self.MODEL_NAME.split("/")[-1]
        return f"{short_name}|{self.EMBEDDING_DIM}"
    
    def get_model_hash(self) -> str:
        """
        Get hash of model config for stricter versioning.
        
        Uses actual model config if loaded, falls back to name-based hash.
        NOTE: This still doesn't hash weights, just config. For true
        weight-based versioning, use HuggingFace commit SHA.
        """
        if self.model_config_hash:
            return self.model_config_hash
        
        # Try to get actual config from loaded model
        if self.model is not None:
            try:
                # SentenceTransformer has internal model with config
                config_dict = {}
                if hasattr(self.model, '_modules'):
                    for name, module in self.model._modules.items():
                        if hasattr(module, 'config'):
                            config_dict[name] = str(module.config)
                if config_dict:
                    config_str = str(sorted(config_dict.items()))
                    return hashlib.md5(config_str.encode()).hexdigest()[:12]
            except Exception:
                pass
        
        # Fallback to name-based hash
        config_str = f"{self.MODEL_NAME}|{self.EMBEDDING_DIM}"
        return hashlib.md5(config_str.encode()).hexdigest()[:8]
        
    def load_model(self) -> None:
        """
        Load the sentence-transformer model
        
        Called once at application startup.
        Downloads model on first run (~90MB).
        
        NOTE: In multi-worker mode, each worker calls this separately.
        """
        if self.model is not None:
            logger.debug("Embedding model already loaded")
            return
            
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Loading embedding model: {self.MODEL_NAME}")
            self.model = SentenceTransformer(self.MODEL_NAME)
            self.model_version = self.get_model_version()
            self.model_config_hash = self.get_model_hash()
            logger.info(f"Embedding model loaded (version: {self.model_version}, hash: {self.model_config_hash})")
            
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
            raise
    
    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def encode(self, text: str) -> Optional[List[float]]:
        """
        Encode single text to embedding vector
        
        Args:
            text: Input text string
            
        Returns:
            List of floats (384 dimensions), or None for empty text
            
        Raises:
            RuntimeError: If model is not loaded
            
        IMPORTANT: Returns None for empty text, NOT zero vector.
        Zero vectors are fake signals that corrupt average computations.
        """
        if self.model is None:
            raise RuntimeError("Embedding model not loaded. Call load_model() first.")
        
        if not text or not text.strip():
            # Return None for empty text - NOT zero vector!
            # Zero vector corrupts averages and similarity computations
            return None
        
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def encode_batch(self, texts: List[str], batch_size: int = 32) -> List[Optional[List[float]]]:
        """
        Encode multiple texts efficiently
        
        Args:
            texts: List of input text strings
            batch_size: Batch size for encoding
            
        Returns:
            List of embedding vectors (None for empty texts)
        """
        if self.model is None:
            raise RuntimeError("Embedding model not loaded. Call load_model() first.")
        
        if not texts:
            return []
        
        valid_indices = []
        valid_texts = []
        
        # Identify non-empty texts
        for i, t in enumerate(texts):
            if t and t.strip():
                valid_indices.append(i)
                valid_texts.append(t)
        
        # Initialize results with None
        results = [None] * len(texts)
        
        # Encode non-empty texts
        if valid_texts:
            embeddings = self.model.encode(
                valid_texts, 
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            
            # Place embeddings at correct indices
            for idx, embedding in zip(valid_indices, embeddings):
                results[idx] = embedding.tolist()
        
        return results
    
    def compute_average_embedding(
        self, 
        embeddings: List[Optional[List[float]]]
    ) -> Optional[List[float]]:
        """
        Compute average of multiple embeddings
        
        Args:
            embeddings: List of embedding vectors (may contain None)
            
        Returns:
            Average embedding vector, or None if no valid embeddings
            
        WARNING: This does NOT validate version consistency.
        Use compute_average_embedding_versioned() for version-safe averaging.
        """
        if not embeddings:
            return None
        
        # Filter out None and zero vectors
        valid_embeddings = [
            e for e in embeddings 
            if e is not None and any(v != 0.0 for v in e)
        ]
        
        if not valid_embeddings:
            return None
        
        arr = np.array(valid_embeddings)
        avg = np.mean(arr, axis=0)
        return avg.tolist()
    
    def compute_average_embedding_versioned(
        self,
        embeddings_with_versions: List[tuple]
    ) -> Optional[tuple]:
        """
        Compute average of embeddings WITH version validation.
        
        Args:
            embeddings_with_versions: List of (embedding, model_version) tuples
            
        Returns:
            Tuple of (average_embedding, model_version) or None
            
        Raises:
            ValueError: If embeddings have mixed versions
        """
        if not embeddings_with_versions:
            return None
        
        # Filter valid embeddings
        valid = [
            (e, v) for e, v in embeddings_with_versions
            if e is not None and any(val != 0.0 for val in e)
        ]
        
        if not valid:
            return None
        
        # Check version consistency
        versions = set(v for _, v in valid)
        if len(versions) > 1:
            raise ValueError(
                f"Cannot average embeddings from different model versions: {versions}. "
                f"This would mix coordinate systems."
            )
        
        model_version = valid[0][1]
        embeddings = [e for e, _ in valid]
        
        arr = np.array(embeddings)
        avg = np.mean(arr, axis=0)
        return (avg.tolist(), model_version)
    
    def compute_similarity(
        self, 
        embedding1: Optional[List[float]], 
        embedding2: Optional[List[float]]
    ) -> float:
        """
        Compute cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score in range [-1, 1]
            NOTE: This is NOT normalized to [0,1]. For dashboard display,
            consider using: normalized = (similarity + 1) / 2
            
        Raises:
            ValueError: If either embedding is None or zero vector
            
        WARNING: This does NOT validate version consistency.
        Use compute_similarity_versioned() for version-safe comparison.
        """
        if embedding1 is None or embedding2 is None:
            raise ValueError("Cannot compute similarity: embedding is None (missing data)")
        
        arr1 = np.array(embedding1)
        arr2 = np.array(embedding2)
        
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)
        
        if norm1 == 0:
            raise ValueError("Cannot compute similarity: embedding1 is zero vector (corrupted data)")
        if norm2 == 0:
            raise ValueError("Cannot compute similarity: embedding2 is zero vector (corrupted data)")
        
        similarity = np.dot(arr1, arr2) / (norm1 * norm2)
        return float(similarity)
    
    def compute_similarity_versioned(
        self,
        embedding1: Optional[List[float]],
        version1: str,
        embedding2: Optional[List[float]],
        version2: str
    ) -> float:
        """
        Compute similarity WITH version validation.
        
        Args:
            embedding1: First embedding vector
            version1: Model version of first embedding
            embedding2: Second embedding vector
            version2: Model version of second embedding
            
        Returns:
            Cosine similarity score in range [-1, 1]
            
        Raises:
            ValueError: If embeddings have different versions
        """
        if version1 != version2:
            raise ValueError(
                f"Cannot compute similarity across model versions: {version1} vs {version2}. "
                f"This would compare vectors in different coordinate systems."
            )
        
        return self.compute_similarity(embedding1, embedding2)
