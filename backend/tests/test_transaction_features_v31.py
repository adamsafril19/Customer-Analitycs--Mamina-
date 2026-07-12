"""Tests for the transaction-derived v3.1 feature set."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest


def test_v31_transaction_features_respect_temporal_cutoff(app):
    with app.app_context():
        from app import db
        from app.models.customer import Customer
        from app.models.transaction import Transaction
        from app.services.feature_service import FeatureService

        as_of_date = date(2026, 1, 1)
        customer = Customer(
            name="V3.1 Feature Test",
            consent_given=True,
            created_at=datetime(2025, 1, 1),
        )
        db.session.add(customer)
        db.session.flush()

        def add_tx(days_from_cutoff, service_type, amount, status="completed"):
            db.session.add(
                Transaction(
                    customer_id=customer.customer_id,
                    tx_date=datetime.combine(
                        as_of_date + timedelta(days=days_from_cutoff),
                        datetime.min.time(),
                    ),
                    service_type=service_type,
                    amount=Decimal(str(amount)),
                    status=status,
                )
            )

        add_tx(-120, "Outlet", 50000)
        add_tx(-80, "Homecare", 0)
        add_tx(-40, "Outlet", 100000)
        add_tx(-5, " HOMECARE ", 200000)
        add_tx(-2, "Homecare", 300000, status="cancelled")
        add_tx(1, "Homecare", 400000)
        db.session.commit()

        feature = FeatureService().populate_numeric_features(
            str(customer.customer_id),
            as_of_date,
        )

        assert feature.tx_count_90d == 3
        assert feature.homecare_tx_ratio_90d == pytest.approx(2 / 3)
        assert feature.last_tx_is_homecare == 1.0
        assert feature.zero_amount_tx_count_90d == 1
        assert feature.lifetime_tx_count == 4

        db.session.delete(customer)
        db.session.commit()


def test_v31_training_schema_matches_feature_service():
    from app.services.feature_service import FeatureService
    from scripts.train_model import MULTIMODAL_FEATURE_NAMES

    assert FeatureService.FEATURE_SCHEMA_VERSION == "v3.2.0"
    assert FeatureService.expected_feature_count() == 25
    assert MULTIMODAL_FEATURE_NAMES == FeatureService.get_feature_names()
    assert "has_communication_90d" in MULTIMODAL_FEATURE_NAMES
    assert "paid_tx_ratio_90d" not in MULTIMODAL_FEATURE_NAMES


def test_feature_windows_are_exact_and_non_overlapping():
    from app.services.feature_service import FeatureService

    as_of = date(2026, 1, 31)
    newest_start, newest_end = FeatureService._window_bounds(as_of, 0, 30)
    prior_start, prior_end = FeatureService._window_bounds(as_of, 1, 30)

    assert newest_start.date() == date(2026, 1, 2)
    assert newest_end.date() == date(2026, 1, 31)
    assert prior_start.date() == date(2025, 12, 3)
    assert prior_end.date() == date(2026, 1, 1)
    assert prior_end < newest_start
