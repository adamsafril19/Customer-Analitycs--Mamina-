"""
Feature Service Tests

UPDATED: Tests for embedding-based text signal features
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
    
    def test_calculate_text_signal_metrics_no_feedback(self, app, sample_customer):
        """Test text signal metrics with no feedback"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            signals = service._calculate_text_signal_metrics(sample_customer, date.today())
            
            assert signals["complaint_rate_30"] == 0
            assert signals["avg_msg_length_30"] == 0
            assert signals["response_delay_mean"] == 0
            assert signals["msg_count_7d"] == 0
            assert signals["msg_volatility"] == 0
    
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
        """Test feature vector conversion with new structure"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            today = date.today()
            
            features = service.calculate_customer_features(sample_customer, today)
            vector = features.to_feature_vector()
            
            # New feature vector has 9 elements
            assert len(vector) == 9
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
            
            # Vector length should match feature names (now 9)
            assert len(vector) == len(feature_names)
            assert len(vector) == 9


class TestEmbeddingService:
    """Tests for Embedding Service"""
    
    def test_embedding_service_singleton(self, app):
        """Test that EmbeddingService is singleton"""
        with app.app_context():
            from app.services.embedding_service import EmbeddingService
            
            service1 = EmbeddingService()
            service2 = EmbeddingService()
            
            assert service1 is service2
    
    def test_embedding_service_properties(self, app):
        """Test EmbeddingService properties"""
        with app.app_context():
            from app.services.embedding_service import EmbeddingService
            
            service = EmbeddingService()
            
            assert service.EMBEDDING_DIM == 384
            assert "MiniLM" in service.MODEL_NAME


class TestETLSignalExtraction:
    """Tests for ETL Service signal extraction"""
    
    def test_extract_signals(self, app):
        """Test signal extraction from text"""
        with app.app_context():
            from app.services.etl_service import ETLService
            
            service = ETLService()
            
            text = "Halo! Bagaimana kabar? Saya sangat senang!!"
            signals = service._extract_signals(text)
            
            assert signals["msg_length"] > 0
            assert signals["num_exclamations"] == 3  # Two !!
            assert signals["num_questions"] == 1
    
    def test_detect_complaint(self, app):
        """Test complaint detection"""
        with app.app_context():
            from app.services.etl_service import ETLService
            
            service = ETLService()
            
            assert service._detect_complaint("Saya sangat kecewa dengan layanan ini")
            assert service._detect_complaint("Pelayanannya buruk sekali")
            assert not service._detect_complaint("Terima kasih, pelayanan bagus")
    
    def test_detect_refund_request(self, app):
        """Test refund request detection"""
        with app.app_context():
            from app.services.etl_service import ETLService
            
            service = ETLService()
            
            assert service._detect_refund_request("Tolong refund uang saya")
            assert service._detect_refund_request("Saya mau cancel booking")
            assert not service._detect_refund_request("Mau booking untuk besok")
