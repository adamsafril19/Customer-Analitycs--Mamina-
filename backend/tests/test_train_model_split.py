"""Tests for leakage-resistant temporal model splitting."""
from datetime import date

import pandas as pd
import pytest

from scripts.train_model import (
    COMMUNICATION_FEATURES,
    promote_staged_artifacts,
    purged_temporal_split,
    select_neutralized_features,
    validate_candidate_improvement,
)
from app.services.shap_wrapper import GatedRiskModel


class _ConstantBaseModel:
    feature_importances_ = [0.0] * 25

    def predict_proba(self, values):
        import numpy as np

        score = np.full(len(values), 0.2)
        return np.column_stack([1.0 - score, score])


class _ConstantAdjuster:
    def predict_proba(self, values):
        import numpy as np

        score = np.full(len(values), 0.8)
        return np.column_stack([1.0 - score, score])


def _monthly_rows():
    rows = []
    for observation_date in pd.date_range(
        start="2025-01-01",
        end="2025-10-01",
        freq="MS",
    ):
        for customer_id in ("customer-a", "customer-b"):
            rows.append(
                {
                    "customer_id": customer_id,
                    "observation_date": observation_date.date(),
                    "churned": 0,
                }
            )
    return pd.DataFrame(rows)


def test_purged_temporal_split_uses_complete_dates_and_available_labels():
    train, test, purged, test_start = purged_temporal_split(
        _monthly_rows(),
        test_size=0.2,
        prediction_horizon_days=90,
    )

    assert test_start == date(2025, 9, 1)
    assert set(test["observation_date"].dt.date) == {
        date(2025, 9, 1),
        date(2025, 10, 1),
    }
    assert set(purged["observation_date"].dt.date) == {
        date(2025, 7, 1),
        date(2025, 8, 1),
    }
    assert set(train["observation_date"]).isdisjoint(test["observation_date"])
    assert train["observation_date"].max() + pd.Timedelta(days=90) <= pd.Timestamp(
        test_start
    )

    for frame in (train, test, purged):
        assert frame.groupby("observation_date")["customer_id"].count().eq(2).all()


def test_purged_temporal_split_rejects_empty_training_period():
    df = _monthly_rows()
    df = df[df["observation_date"] >= date(2025, 9, 1)]

    with pytest.raises(ValueError, match="empty train or test"):
        purged_temporal_split(
            df,
            test_size=0.5,
            prediction_horizon_days=90,
        )


def test_sparse_text_coverage_neutralizes_communication_features():
    df = _monthly_rows()
    df["has_text_signal"] = 0

    neutralized, coverage = select_neutralized_features(
        df,
        prediction_horizon_days=90,
    )

    assert coverage == 0.0
    assert set(COMMUNICATION_FEATURES).issubset(neutralized)


def test_candidate_gate_rejects_material_baseline_regression():
    with pytest.raises(RuntimeError, match="candidate rejected"):
        validate_candidate_improvement({
            "roc_auc": -0.01,
            "pr_auc": 0.0,
        })


def test_artifact_promotion_replaces_complete_candidate(tmp_path):
    output = tmp_path / "models"
    staging = output / ".training-test"
    output.mkdir()
    staging.mkdir()
    (output / "multimodal_model.pkl").write_bytes(b"old")
    (output / "shap_explainer.pkl").write_bytes(b"old-shap")
    (staging / "multimodal_model.pkl").write_bytes(b"new")

    promote_staged_artifacts(str(staging), str(output))

    assert (output / "multimodal_model.pkl").read_bytes() == b"new"
    assert not (output / "shap_explainer.pkl").exists()
    assert not (output / ".artifact-backup").exists()


def test_gated_model_falls_back_without_communication():
    import numpy as np

    from app.services.feature_service import FeatureService

    names = FeatureService.get_feature_names()
    gate_idx = names.index("has_communication_90d")
    values = np.zeros((2, len(names)))
    values[1, gate_idx] = 1.0

    model = GatedRiskModel(
        base_model=_ConstantBaseModel(),
        adjuster=_ConstantAdjuster(),
        feature_names=names,
        base_neutralized_features=["complaint_ratio", "msg_trend_smoothed"],
    )

    scores = model.predict_proba(values)[:, 1]
    assert scores.tolist() == pytest.approx([0.2, 0.8])
