"""
ETL Celery Tasks

Background tasks for:
- Processing WhatsApp logs
- Recalculating customer features
"""
import logging
from typing import List, Optional

from app.tasks import celery_app
from app import db

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="etl.process_whatsapp_logs")
def process_whatsapp_logs(self, file_path: str, admin_name: str = "Mamina"):
    """
    Process WhatsApp export file
    
    Args:
        file_path: Path to WhatsApp export file
        admin_name: Name of admin/business in chat
        
    Returns:
        Processing statistics
    """
    from app.services.etl_service import ETLService
    
    logger.info(f"Starting WhatsApp processing: {file_path}")
    
    try:
        self.update_state(state="PROGRESS", meta={"progress": 10})
        
        etl_service = ETLService()
        result = etl_service.process_whatsapp_file(file_path, admin_name)
        
        self.update_state(state="PROGRESS", meta={"progress": 100})
        
        logger.info(f"WhatsApp processing complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"WhatsApp processing failed: {e}")
        raise


@celery_app.task(bind=True, name="etl.recalculate_customer_features")
def recalculate_customer_features(self, customer_ids: Optional[List[str]] = None):
    """
    Recalculate features for customers (OPTIMIZED with batch commit)
    
    Catatan performa:
    - commit dilakukan setiap 100 customer untuk mengurangi overhead
    - rollback per-customer jika ada error, tidak menghentikan seluruh batch
    
    Args:
        customer_ids: Optional list of customer IDs (None = all active customers)
        
    Returns:
        Processing statistics
    """
    from app.services.feature_service import FeatureService
    from app.models.customer import Customer
    
    logger.info(f"Starting feature recalculation for {len(customer_ids) if customer_ids else 'all'} customers")
    
    try:
        self.update_state(state="PROGRESS", meta={"progress": 5})
        
        feature_service = FeatureService()
        
        # Get customer IDs if not provided
        if customer_ids is None:
            customers = Customer.query.filter_by(is_active=True).all()
            customer_ids = [str(c.customer_id) for c in customers]
        
        total = len(customer_ids)
        processed = 0
        failed = 0
        failed_details = []
        
        for i, cid in enumerate(customer_ids):
            try:
                # commit=False: kita commit manual per batch
                feature_service.calculate_customer_features(cid, commit=False, force_update=True)
                processed += 1
                
                # Commit setiap 100 customer
                if processed % 100 == 0:
                    db.session.commit()
                    db.session.expire_all()  # Bersihkan cache session
                    logger.info(f"Batch committed: {processed}/{total}")
                    
            except Exception as e:
                db.session.rollback()
                logger.warning(f"Failed to calculate features for {cid}: {e}")
                failed += 1
                failed_details.append({"customer_id": cid, "error": str(e)})
            
            # Update progress
            progress = int((i + 1) / total * 100)
            self.update_state(state="PROGRESS", meta={
                "progress": progress,
                "processed": processed,
                "failed": failed
            })
        
        # Final commit
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Final commit failed: {e}")
            db.session.rollback()
        
        result = {
            "total": total,
            "processed": processed,
            "failed": failed,
            "failed_details": failed_details[:10]  # Limit to first 10 errors
        }
        
        logger.info(f"Feature recalculation complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Feature recalculation failed: {e}")
        db.session.rollback()
        raise


@celery_app.task(bind=True, name="etl.calculate_response_times")
def calculate_response_times(self, customer_ids: Optional[List[str]] = None):
    """
    Calculate response times for customer messages (OPTIMIZED with batch commit)
    
    Args:
        customer_ids: Optional list of customer IDs
        
    Returns:
        Processing statistics
    """
    from app.services.etl_service import ETLService
    from app.models.customer import Customer
    
    logger.info("Starting response time calculation")
    
    try:
        etl_service = ETLService()
        
        if customer_ids is None:
            customers = Customer.query.filter_by(is_active=True).all()
            customer_ids = [str(c.customer_id) for c in customers]
        
        total = len(customer_ids)
        total_updated = 0
        failed = 0
        
        for i, cid in enumerate(customer_ids):
            try:
                updated = etl_service.calculate_response_times(cid)
                total_updated += updated
                
                # Commit setiap 100 customer
                if (i + 1) % 100 == 0:
                    db.session.commit()
                    db.session.expire_all()
                    
            except Exception as e:
                db.session.rollback()
                logger.warning(f"Failed to calculate response times for {cid}: {e}")
                failed += 1
            
            # Update progress
            progress = int((i + 1) / total * 100)
            self.update_state(state="PROGRESS", meta={
                "progress": progress,
                "total_updated": total_updated
            })
        
        # Final commit
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Final commit failed: {e}")
            db.session.rollback()
        
        return {"total_updated": total_updated, "failed": failed}
        
    except Exception as e:
        logger.error(f"Response time calculation failed: {e}")
        db.session.rollback()
        raise
