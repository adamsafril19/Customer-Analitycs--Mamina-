"""
Sentiment Service

Uses IndoBERTweet for Indonesian sentiment classification.
Model: Aardiiiiy/indobertweet-base-Indonesian-sentiment-analysis
"""
import logging
from typing import Tuple, List, Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


class SentimentService:
    """
    Sentiment classification service using IndoBERTweet
    
    DASHBOARD ONLY - ML pipeline does NOT use this.
    
    Singleton pattern to load model once and reuse.
    Uses Aardiiiiy/indobertweet-base-Indonesian-sentiment-analysis for Indonesian text.
    
    IMPORTANT: avg_sentiment_score is model-relative, not absolute psychological scale.
    Different model versions may produce different scores for same text.
    """
    
    _instance = None
    MODEL_NAME = "Aardiiiiy/indobertweet-base-Indonesian-sentiment-analysis"
    LABELS = ["negative", "neutral", "positive"]
    
    def __new__(cls):
        """Singleton pattern - ensure only one instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.model = None
        self.tokenizer = None
        self.model_version = None  # Track model version for semantic continuity
        self._initialized = True
    
    def get_model_version(self) -> str:
        """Get current model version identifier"""
        return self.model_version or self.MODEL_NAME
    
    def load_model(self) -> None:
        """
        Load the sentiment classification model
        
        Called once at application startup.
        Downloads model on first run.
        """
        if self.model is not None:
            logger.debug("Sentiment model already loaded")
            return
        
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch
            
            logger.info(f"Loading sentiment model: {self.MODEL_NAME}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.MODEL_NAME)
            self.model.eval()
            
            # Use GPU if available
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            
            # Store model version for semantic continuity
            self.model_version = self.MODEL_NAME
            
            logger.info(f"Sentiment model loaded successfully on {self.device} (version: {self.model_version})")
            
        except Exception as e:
            logger.error(f"Failed to load sentiment model: {e}")
            raise
    
    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def predict(self, text: str) -> Tuple[str, float]:
        """
        Predict sentiment for single text
        
        Args:
            text: Input text string
            
        Returns:
            Tuple of (label, score)
            - label: 'positive', 'neutral', or 'negative'
            - score: valence score (-1 to 1) = P(positive) - P(negative)
            
        Raises:
            RuntimeError: If model is not loaded
        """
        if self.model is None:
            raise RuntimeError("Sentiment model not loaded. Call load_model() first.")
        
        if not text or not text.strip():
            return "neutral", 0.0
        
        import torch
        
        # Tokenize
        inputs = self.tokenizer(
            text, 
            return_tensors="pt", 
            truncation=True, 
            max_length=512,
            padding=True
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Predict
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
            
        probs_list = probs[0].cpu().tolist()
        p_neg, p_neu, p_pos = probs_list
        
        # Get label
        pred_idx = torch.argmax(probs, dim=-1).item()
        label = self.LABELS[pred_idx]
        
        # CORRECT: Valence = P(positive) - P(negative)
        valence = p_pos - p_neg
        
        return label, round(valence, 4)
    
    def predict_batch(self, texts: List[str], batch_size: int = 32) -> List[Tuple[str, float]]:
        """
        Predict sentiment for multiple texts efficiently
        
        Args:
            texts: List of input text strings
            batch_size: Batch size for processing
            
        Returns:
            List of (label, score) tuples
        """
        if self.model is None:
            raise RuntimeError("Sentiment model not loaded. Call load_model() first.")
        
        if not texts:
            return []
        
        import torch
        
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            # Handle empty texts
            batch_texts_clean = [t if t and t.strip() else "." for t in batch_texts]
            
            # Tokenize
            inputs = self.tokenizer(
                batch_texts_clean,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Predict
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.softmax(outputs.logits, dim=-1)
            
            # Process each prediction
            for j, text in enumerate(batch_texts):
                if not text or not text.strip():
                    results.append(("neutral", 0.0))
                else:
                    probs_j = probs[j].cpu().tolist()
                    p_neg, p_neu, p_pos = probs_j
                    
                    pred_idx = torch.argmax(probs[j]).item()
                    label = self.LABELS[pred_idx]
                    valence = p_pos - p_neg
                    
                    results.append((label, round(valence, 4)))
        
        return results
