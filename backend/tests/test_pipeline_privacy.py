"""Privacy boundaries for technical ML pipeline responses."""

from datetime import date


def test_feature_snapshot_samples_use_customer_id_without_name(app, monkeypatch):
    """Technical feature previews must not expose the operational customer name."""
    with app.app_context():
        from app import db
        from app.models.customer import Customer
        from app.models.numeric_features import CustomerNumericFeatures
        from app.services.feature_service import FeatureService
        from app.services.pipeline_service import PipelineService

        as_of_date = date(2026, 1, 31)
        customer = Customer(name="Private Customer", consent_given=True)
        db.session.add(customer)
        db.session.flush()
        db.session.add(
            CustomerNumericFeatures(
                customer_id=customer.customer_id,
                as_of_date=as_of_date,
                recency_days=12,
                tx_count_90d=3,
            )
        )
        db.session.commit()

        monkeypatch.setattr(
            FeatureService,
            "get_default_as_of_date",
            staticmethod(lambda: as_of_date),
        )
        monkeypatch.setattr(
            FeatureService,
            "get_ml_feature_dict",
            lambda self, customer_id, snapshot_date: {"recency_days": 12.0},
        )

        result = PipelineService()._feature_snapshot_status()

        assert result["sample_rows"] == [
            {
                "customer_id": str(customer.customer_id),
                "recency_days": 12.0,
            }
        ]
        assert "customer_name" not in result["sample_rows"][0]
