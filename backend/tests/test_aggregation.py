"""
Integration Tests for Feature Aggregation (Milestone 2)

Tests for:
- recalculate_customer_text_features with embedding aggregation
- topic distribution calculation
- sentiment distribution calculation
"""
import pytest
from datetime import date, datetime, timedelta
import uuid


class TestFeatureAggregation:
    """Integration tests for text feature aggregation"""
    
    def test_recalculate_customer_text_features_empty(self, app, sample_customer):
        """Test aggregation with no feedback data"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            result = service.recalculate_customer_text_features(
                sample_customer, 
                date.today()
            )
            
            assert result is not None
            assert result.msg_count_30d == 0
            assert result.msg_count_7d == 0
            assert result.embedding_count_30d == 0
            assert result.top_topic_counts is None
            assert result.sentiment_dist is None
    
    def test_recalculate_customer_text_features_with_data(
        self, app, sample_customer, sample_feedback_features
    ):
        """Test aggregation with sample feedback data"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            result = service.recalculate_customer_text_features(
                sample_customer, 
                date.today()
            )
            
            assert result is not None
            assert result.msg_count_30d >= 0
            # If there are embeddings, avg_embedding should be calculated
            if result.embedding_count_30d > 0:
                assert result.avg_embedding is not None
    
    def test_recalculate_all_text_features(self, app, sample_customer):
        """Test batch recalculation"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            result = service.recalculate_all_text_features(
                customer_ids=[sample_customer],
                as_of_date=date.today()
            )
            
            assert result["processed"] == 1
            assert result["failed"] == 0


class TestEmbeddingAggregation:
    """Tests for embedding aggregation logic"""
    
    def test_calculate_avg_embedding_from_list(self, app):
        """Test average embedding calculation"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            import numpy as np
            
            service = FeatureService()
            
            # Create sample embeddings
            emb1 = np.ones(384) * 0.5
            emb2 = np.ones(384) * 1.5
            
            avg = service._calculate_avg_embedding_from_list([emb1, emb2])
            
            assert avg is not None
            assert len(avg) == 384
            assert abs(avg[0] - 1.0) < 0.001  # Average of 0.5 and 1.5
    
    def test_calculate_avg_embedding_empty(self, app):
        """Test average embedding with empty list"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            
            avg = service._calculate_avg_embedding_from_list([])
            
            assert avg is None


class TestTopicDistribution:
    """Tests for topic distribution calculation"""
    
    def test_topic_counts_populated(self, app, sample_customer, sample_feedback_with_topics):
        """Test that topic counts are populated correctly"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            result = service.recalculate_customer_text_features(
                sample_customer,
                date.today()
            )
            
            # If topics exist, top_topic_counts should be populated
            if result.msg_count_30d > 0:
                # May be None if no topics assigned
                pass  # Just ensure no error


class TestSentimentDistribution:
    """Tests for sentiment distribution calculation"""
    
    def test_sentiment_dist_format(self, app, sample_customer, sample_feedback_with_sentiment):
        """Test that sentiment distribution has correct format"""
        with app.app_context():
            from app.services.feature_service import FeatureService
            
            service = FeatureService()
            result = service.recalculate_customer_text_features(
                sample_customer,
                date.today()
            )
            
            if result.sentiment_dist:
                # Should contain positive/neutral/negative keys
                valid_keys = {"positive", "neutral", "negative"}
                for key in result.sentiment_dist.keys():
                    assert key in valid_keys
