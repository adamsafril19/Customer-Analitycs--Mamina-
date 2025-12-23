"""
Feature Engineering Service

Calculates RFM, sentiment, and other features from raw data.

OPTIMIZED VERSION:
- Menggunakan SQL agregasi (SUM, AVG, COUNT) agar tidak menarik semua row ke Python
- Parameter commit=False untuk batch processing (lebih cepat)
- Semua query menggunakan func.* dari SQLAlchemy
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import func, case

from app import db
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.feedback import FeedbackClean
from app.models.feature import CustomerFeature

logger = logging.getLogger(__name__)


class FeatureService:
    """
    Feature Engineering Service
    
    Responsibilities:
    - Calculate RFM scores from transaction data
    - Aggregate sentiment metrics from feedback
    - Calculate response time and intensity metrics
    - Store features for ML inference
    
    Catatan performa:
    - Semua perhitungan pakai SQL agregasi (tidak .all() lalu loop di Python)
    - Untuk batch processing, panggil dengan commit=False lalu commit manual per batch
    """
    
    def calculate_customer_features(
        self, 
        customer_id: str,
        as_of_date: Optional[date] = None,
        *,
        commit: bool = True,
        force_update: bool = False
    ) -> CustomerFeature:
        """
        Calculate all features for a single customer
        
        Args:
            customer_id: Customer UUID (string)
            as_of_date: Date to calculate features as of (default: today)
            commit: Apakah langsung db.session.commit() di akhir.
                    Untuk batch processing, set False lalu commit manual per 100 customer.
            force_update: Jika True, akan update meskipun sudah ada data untuk tanggal ini.
            
        Returns:
            CustomerFeature object (baru atau terupdate)
        """
        if as_of_date is None:
            as_of_date = date.today()
        
        # Check if features already exist for this date
        existing = CustomerFeature.query.filter_by(
            customer_id=customer_id,
            as_of_date=as_of_date
        ).first()
        
        if existing and not force_update:
            logger.debug(f"Features already exist for customer {customer_id} on {as_of_date}")
            return existing
        
        # Calculate all metrics using SQL aggregation
        rfm = self._calculate_rfm(customer_id, as_of_date)
        tenure = self._calculate_tenure(customer_id, as_of_date)
        sentiment = self._calculate_sentiment_metrics(customer_id, as_of_date)
        engagement = self._calculate_engagement_metrics(customer_id, as_of_date)
        
        # Create or update feature record
        if existing:
            feature = existing
        else:
            feature = CustomerFeature(
                customer_id=customer_id,
                as_of_date=as_of_date
            )
            db.session.add(feature)
        
        # Set values
        feature.r_score = rfm["r_score"]
        feature.f_score = rfm["f_score"]
        feature.m_score = rfm["m_score"]
        feature.tenure_days = tenure
        feature.avg_sentiment_30 = sentiment["avg_sentiment_30"]
        feature.neg_msg_count_30 = sentiment["neg_msg_count_30"]
        feature.avg_response_secs = engagement["avg_response_secs"]
        feature.intensity_7d = engagement["intensity_7d"]
        feature.created_at = datetime.utcnow()
        
        if commit:
            db.session.commit()
            logger.info(f"Created/updated features for customer {customer_id}")
        
        return feature
    
    def _calculate_rfm(
        self, 
        customer_id: str, 
        as_of_date: date
    ) -> Dict[str, float]:
        """
        Calculate RFM (Recency, Frequency, Monetary) scores menggunakan SQL agregasi.
        
        Penjelasan:
        - Recency: Hari sejak transaksi terakhir (semakin kecil = semakin baik)
        - Frequency: Jumlah transaksi dalam 365 hari terakhir
        - Monetary: Total nilai transaksi
        
        R/F/M score dinormalisasi ke skala 0-5.
        """
        as_of_datetime = datetime.combine(as_of_date, datetime.max.time())
        one_year_ago = as_of_date - timedelta(days=365)
        
        # 1) Last transaction date (untuk Recency)
        last_tx_date = (
            db.session.query(func.max(Transaction.tx_date))
            .filter(
                Transaction.customer_id == customer_id,
                Transaction.status == "completed"
            )
            .scalar()
        )
        
        if not last_tx_date:
            # No transactions at all
            return {"r_score": 0.0, "f_score": 0.0, "m_score": 0.0}
        
        # Calculate recency in days
        recency_days = (as_of_date - last_tx_date.date()).days
        # Normalize: 0 days = score 5, 180 days = score 0
        r_score = max(0.0, 5.0 - (recency_days / 36.0))
        
        # 2) Frequency & Monetary in last 365 days (SQL aggregation)
        freq_count, total_amount = (
            db.session.query(
                func.count(Transaction.tx_id),
                func.coalesce(func.sum(Transaction.amount), 0)
            )
            .filter(
                Transaction.customer_id == customer_id,
                Transaction.status == "completed",
                Transaction.tx_date >= datetime.combine(one_year_ago, datetime.min.time()),
                Transaction.tx_date <= as_of_datetime
            )
            .one()
        )
        
        freq_count = int(freq_count or 0)
        total_amount = float(total_amount or 0)
        
        # Normalize frequency: cap at 5 transactions
        f_score = min(5.0, float(freq_count))
        
        # Normalize monetary: 1 juta per point, cap at 5
        m_score = min(5.0, total_amount / 1_000_000)
        
        return {
            "r_score": round(r_score, 2),
            "f_score": round(f_score, 2),
            "m_score": round(m_score, 2)
        }
    
    def _calculate_tenure(
        self, 
        customer_id: str, 
        as_of_date: date
    ) -> int:
        """
        Calculate customer tenure in days.
        
        Tenure = berapa hari sejak customer pertama kali terdaftar (created_at).
        """
        created_at = (
            db.session.query(Customer.created_at)
            .filter(Customer.customer_id == customer_id)
            .scalar()
        )
        
        if not created_at:
            return 0
        
        created_date = created_at.date() if hasattr(created_at, 'date') else created_at
        tenure = (as_of_date - created_date).days
        return max(0, tenure)
    
    def _calculate_sentiment_metrics(
        self, 
        customer_id: str, 
        as_of_date: date
    ) -> Dict[str, Any]:
        """
        Calculate sentiment-related metrics menggunakan SQL agregasi.
        
        Output:
        - avg_sentiment_30: Rata-rata sentiment_score dalam 30 hari terakhir
        - neg_msg_count_30: Jumlah pesan dengan sentiment_label = 'negative'
        """
        thirty_days_ago = as_of_date - timedelta(days=30)
        start_dt = datetime.combine(thirty_days_ago, datetime.min.time())
        end_dt = datetime.combine(as_of_date, datetime.max.time())
        
        base_filter = [
            FeedbackClean.customer_id == customer_id,
            FeedbackClean.processed_at >= start_dt,
            FeedbackClean.processed_at <= end_dt
        ]
        
        # Total messages in period
        total_count = (
            db.session.query(func.count(FeedbackClean.feedback_id))
            .filter(*base_filter)
            .scalar()
        ) or 0
        
        if total_count == 0:
            return {"avg_sentiment_30": 0.0, "neg_msg_count_30": 0}
        
        # Average sentiment (hanya yang punya nilai)
        avg_sentiment = (
            db.session.query(func.avg(FeedbackClean.sentiment_score))
            .filter(
                *base_filter,
                FeedbackClean.sentiment_score.isnot(None)
            )
            .scalar()
        ) or 0.0
        
        # Count negative messages (sentiment_label = 'negative')
        neg_count = (
            db.session.query(func.count(FeedbackClean.feedback_id))
            .filter(
                *base_filter,
                FeedbackClean.sentiment_label == "negative"
            )
            .scalar()
        ) or 0
        
        return {
            "avg_sentiment_30": round(float(avg_sentiment), 4),
            "neg_msg_count_30": int(neg_count)
        }
    
    def _calculate_engagement_metrics(
        self, 
        customer_id: str, 
        as_of_date: date
    ) -> Dict[str, Any]:
        """
        Calculate engagement metrics menggunakan SQL agregasi.
        
        Output:
        - avg_response_secs: Rata-rata response_time_secs dalam 30 hari terakhir
        - intensity_7d: Jumlah pesan dalam 7 hari terakhir
        """
        seven_days_ago = as_of_date - timedelta(days=7)
        thirty_days_ago = as_of_date - timedelta(days=30)
        end_dt = datetime.combine(as_of_date, datetime.max.time())
        
        # Intensity: count messages in last 7 days
        intensity = (
            db.session.query(func.count(FeedbackClean.feedback_id))
            .filter(
                FeedbackClean.customer_id == customer_id,
                FeedbackClean.processed_at >= datetime.combine(seven_days_ago, datetime.min.time()),
                FeedbackClean.processed_at <= end_dt
            )
            .scalar()
        ) or 0
        
        # Average response time in last 30 days (hanya yang punya nilai)
        avg_response = (
            db.session.query(func.avg(FeedbackClean.response_time_secs))
            .filter(
                FeedbackClean.customer_id == customer_id,
                FeedbackClean.response_time_secs.isnot(None),
                FeedbackClean.processed_at >= datetime.combine(thirty_days_ago, datetime.min.time()),
                FeedbackClean.processed_at <= end_dt
            )
            .scalar()
        ) or 0.0
        
        return {
            "avg_response_secs": round(float(avg_response), 2),
            "intensity_7d": int(intensity)
        }
    
    def get_latest_features(self, customer_id: str) -> Optional[CustomerFeature]:
        """Get most recent features for customer"""
        return CustomerFeature.query.filter_by(
            customer_id=customer_id
        ).order_by(CustomerFeature.as_of_date.desc()).first()
    
    def recalculate_all_features(
        self, 
        customer_ids: Optional[List[str]] = None,
        as_of_date: Optional[date] = None
    ) -> Dict[str, int]:
        """
        Recalculate features for multiple customers.
        
        CATATAN: Untuk skala besar, gunakan Celery task (etl_tasks.recalculate_customer_features)
        yang sudah dioptimasi dengan batch commit.
        
        Args:
            customer_ids: List of customer IDs (None = all active customers)
            as_of_date: Date to calculate for (default: today)
            
        Returns:
            Dict with processed and failed counts
        """
        if as_of_date is None:
            as_of_date = date.today()
        
        if customer_ids is None:
            # Get all active customers
            customers = Customer.query.filter_by(is_active=True).all()
            customer_ids = [str(c.customer_id) for c in customers]
        
        processed = 0
        failed = 0
        
        for i, cid in enumerate(customer_ids):
            try:
                # commit=False untuk batch, commit setiap 100
                self.calculate_customer_features(cid, as_of_date, commit=False, force_update=True)
                processed += 1
                
                # Commit setiap 100 customer
                if (i + 1) % 100 == 0:
                    db.session.commit()
                    logger.info(f"Batch committed: {i + 1} customers processed")
                    
            except Exception as e:
                logger.error(f"Failed to calculate features for {cid}: {e}")
                db.session.rollback()
                failed += 1
        
        # Final commit
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Final commit failed: {e}")
            db.session.rollback()
        
        return {"processed": processed, "failed": failed}
