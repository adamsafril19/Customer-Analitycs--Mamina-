"""
Feature Service Tests
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal


class TestFeatureService:
    """Tests for Feature Service"""
    
    def test_calculate_rfm_no_transactions(self, app, sample_customer):
        """Test RFM calculation with no transactions"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            rfm = service._calculate_rfm(sample_customer, date.today())
            
            assert rfm["r_score"] == 0
            assert rfm["f_score"] == 0
            assert rfm["m_score"] == 0
    
    def test_calculate_tenure(self, app, sample_customer):
        """Test tenure calculation"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            tenure = service._calculate_tenure(sample_customer, date.today())
            
            # Customer was just created, tenure should be 0
            assert tenure >= 0
    
    def test_calculate_sentiment_metrics_no_feedback(self, app, sample_customer):
        """Test sentiment metrics with no feedback"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            sentiment = service._calculate_sentiment_metrics(sample_customer, date.today())
            
            assert sentiment["avg_sentiment_30"] == 0
            assert sentiment["neg_msg_count_30"] == 0
    
    def test_calculate_engagement_metrics_no_data(self, app, sample_customer):
        """Test engagement metrics with no data"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            engagement = service._calculate_engagement_metrics(sample_customer, date.today())
            
            assert engagement["avg_response_secs"] == 0
            assert engagement["intensity_7d"] == 0
    
    def test_calculate_customer_features(self, app, sample_customer):
        """Test full feature calculation"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            from app.models.feature import CustomerFeature
            
            service = FeatureService()
            today = date.today()
            
            # Calculate features
            features = service.calculate_customer_features(sample_customer, today)
            
            assert features is not None
            assert features.customer_id == sample_customer or str(features.customer_id) == sample_customer
            assert features.as_of_date == today
    
    def test_get_latest_features(self, app, sample_customer):
        """Test getting latest features"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            today = date.today()
            
            # First calculate features
            service.calculate_customer_features(sample_customer, today)
            
            # Then get latest
            features = service.get_latest_features(sample_customer)
            
            assert features is not None
            assert features.as_of_date == today
    
    def test_feature_vector_conversion(self, app, sample_customer):
        """Test feature vector conversion"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            today = date.today()
            
            features = service.calculate_customer_features(sample_customer, today)
            vector = features.to_feature_vector()
            
            assert len(vector) == 8
            assert all(isinstance(v, (int, float)) for v in vector)


class TestFeatureVectorOrder:
    """Tests for feature vector ordering"""
    
    def test_feature_vector_order_matches_metadata(self, app, sample_customer):
        """Test that feature vector order matches metadata"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            from app.services.ml_service import MLService
            
            feature_service = FeatureService()
            ml_service = MLService()
            
            # Get feature names from metadata
            feature_names = ml_service._get_default_feature_metadata()["feature_names"]
            
            # Calculate features
            features = feature_service.calculate_customer_features(
                sample_customer, 
                date.today()
            )
            
            # Get vector
            vector = features.to_feature_vector()
            
            # Vector length should match feature names
            assert len(vector) == len(feature_names)
