# ML Models Directory

This directory contains the pre-trained ML model artifacts for the churn prediction system.

## Required Files

1. **churn_model.pkl** - Main XGBoost/sklearn classification model
2. **vectorizer.pkl** - Text vectorizer for NLP features (optional)
3. **features.json** - Feature metadata (names, types, order)
4. **shap_explainer.pkl** - Pre-computed SHAP explainer for interpretability

## Important Notes

- These files are **NOT included in version control** (see .gitignore)
- Models are trained separately using Jupyter notebooks or training scripts
- The `features.json` file defines the expected feature order for inference
- Model files should be copied to this directory before deployment

## Feature Order (CRITICAL)

The feature vector MUST be in this exact order:

1. r_score (Recency)
2. f_score (Frequency)
3. m_score (Monetary)
4. tenure_days
5. avg_sentiment_30
6. neg_msg_count_30
7. avg_response_secs
8. intensity_7d

## Training vs Inference

- **Training**: Done externally (Jupyter notebook, separate Python scripts)
- **Inference**: Done by this Flask backend using pre-trained models

## Model Versioning

Each model should have a version string (e.g., "v1.0.0") that is:

- Stored in the environment variable `MODEL_VERSION`
- Saved with each prediction for traceability

## How to Generate Models

Example training code (run separately):

```python
import joblib
from sklearn.ensemble import GradientBoostingClassifier
import shap

# Train model
model = GradientBoostingClassifier()
model.fit(X_train, y_train)

# Save model
joblib.dump(model, 'models/churn_model.pkl')

# Create and save SHAP explainer
explainer = shap.TreeExplainer(model)
joblib.dump(explainer, 'models/shap_explainer.pkl')
```
