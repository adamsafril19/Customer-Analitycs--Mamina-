"""
Models Package

Ontology:
- Raw: FeedbackRaw (phone only), Transaction
- Linked: FeedbackLinked (identity resolution)
- Features: CustomerNumericFeatures, CustomerTextSignals, FeedbackFeatures
- Semantics: CustomerTextSemantics (dashboard only)
- Labels: ChurnLabel (ground truth)
- Predictions: ChurnPrediction, ShapCache
- Registry: EmbeddingModelRegistry, MLModelRegistry (model identity)
"""
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.feedback import FeedbackRaw, FeedbackLinked, FeedbackFeatures
from app.models.numeric_features import CustomerNumericFeatures
from app.models.text_signals import CustomerTextSignals
from app.models.text_semantics import CustomerTextSemantics
from app.models.churn_label import ChurnLabel
from app.models.prediction import ChurnPrediction
from app.models.action import Action
from app.models.user import User
from app.models.topic import Topic, ModelVersion, ShapCache
from app.models.embedding_registry import EmbeddingModelRegistry
from app.models.ml_registry import MLModelRegistry

__all__ = [
    "Customer",
    "Transaction",
    "FeedbackRaw",
    "FeedbackLinked",
    "FeedbackFeatures",
    "CustomerNumericFeatures",
    "CustomerTextSignals",
    "CustomerTextSemantics",
    "ChurnLabel",
    "ChurnPrediction",
    "Action",
    "User",
    "Topic",
    "ModelVersion",
    "ShapCache",
    "EmbeddingModelRegistry",
    "MLModelRegistry"
]


