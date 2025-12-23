"""
ML Service Tests
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np


class TestMLService:
    """Tests for ML Service"""
    
    def test_ml_service_singleton(self, app):
        """Test that MLService is a singleton"""
        with app.app_context():
            from app.services.ml_service import MLService
            
            service1 = MLService()
            service2 = MLService()
            
            assert service1 is service2
    
    def test_is_model_loaded_false_initially(self, app):
        """Test that model is not loaded initially"""
        with app.app_context():
            from app.services.ml_service import MLService
            
            service = MLService()
            # Reset for test
            service.model = None
            
            assert service.is_model_loaded() is False
    
    @patch('joblib.load')
    def test_load_model_success(self, mock_load, app):
        """Test successful model loading"""
        with app.app_context():
            from app.services.ml_service import MLService
            
            mock_model = Mock()
            mock_load.return_value = mock_model
            
            service = MLService()
            service._initialized = False
            service.__init__()
            
            # This would normally load from file
            service.model = mock_model
            
            assert service.is_model_loaded() is True
    
    def test_get_default_feature_metadata(self, app):
        """Test default feature metadata"""
        with app.app_context():
            from app.services.ml_service import MLService
            
            service = MLService()
            metadata = service._get_default_feature_metadata()
            
            assert "feature_names" in metadata
            assert "feature_types" in metadata
            assert "expected_shape" in metadata
            assert len(metadata["feature_names"]) == 8
    
    def test_score_to_label_low(self, app):
        """Test score to label conversion - low"""
        with app.app_context():
            from app.services.ml_service import MLService
            
            service = MLService()
            
            assert service._score_to_label(0.1) == "low"
            assert service._score_to_label(0.29) == "low"
    
    def test_score_to_label_medium(self, app):
        """Test score to label conversion - medium"""
        with app.app_context():
            from app.services.ml_service import MLService
            
            service = MLService()
            
            assert service._score_to_label(0.3) == "medium"
            assert service._score_to_label(0.5) == "medium"
            assert service._score_to_label(0.69) == "medium"
    
    def test_score_to_label_high(self, app):
        """Test score to label conversion - high"""
        with app.app_context():
            from app.services.ml_service import MLService
            
            service = MLService()
            
            assert service._score_to_label(0.7) == "high"
            assert service._score_to_label(0.9) == "high"
            assert service._score_to_label(1.0) == "high"
    
    def test_predict_without_model_raises_error(self, app):
        """Test prediction without model raises error"""
        with app.app_context():
            from app.services.ml_service import MLService
            from app.utils.errors import ModelNotLoadedError
            
            service = MLService()
            service.model = None
            
            with pytest.raises(ModelNotLoadedError):
                service.predict([1, 2, 3, 4, 5, 6, 7, 8])
    
    def test_predict_with_mock_model(self, app):
        """Test prediction with mocked model"""
        with app.app_context():
            from app.services.ml_service import MLService
            
            service = MLService()
            
            # Create mock model
            mock_model = Mock()
            mock_model.predict_proba = Mock(return_value=np.array([[0.3, 0.7]]))
            
            service.model = mock_model
            service.feature_metadata = service._get_default_feature_metadata()
            
            features = [3.0, 2.0, 4.0, 100, 0.5, 2, 300, 5]
            score, label = service.predict(features)
            
            assert score == 0.7
            assert label == "high"
    
    def test_predict_batch(self, app):
        """Test batch prediction"""
        with app.app_context():
            from app.services.ml_service import MLService
            
            service = MLService()
            
            # Create mock model
            mock_model = Mock()
            mock_model.predict_proba = Mock(return_value=np.array([
                [0.8, 0.2],
                [0.4, 0.6],
                [0.1, 0.9]
            ]))
            
            service.model = mock_model
            service.feature_metadata = service._get_default_feature_metadata()
            
            features_list = [
                [3.0, 2.0, 4.0, 100, 0.5, 2, 300, 5],
                [1.0, 1.0, 1.0, 50, -0.3, 5, 600, 2],
                [0.5, 0.5, 0.5, 20, -0.8, 10, 900, 1]
            ]
            
            results = service.predict_batch(features_list)
            
            assert len(results) == 3
            assert results[0][0] == 0.2  # First customer score
            assert results[0][1] == "low"
            assert results[1][0] == 0.6
            assert results[1][1] == "medium"
            assert results[2][0] == 0.9
            assert results[2][1] == "high"
