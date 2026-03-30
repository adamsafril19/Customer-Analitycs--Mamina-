"""
Linking Service

IDENTITY RESOLUTION LAYER

Matches FeedbackRaw (phone_number) → Customer (phone_hash)
Creates FeedbackLinked with match_confidence.

This is a probabilistic matching layer - not assumed truth.
"""
import logging
from datetime import datetime
from typing import List, Tuple, Optional

from app import db
from app.models.customer import Customer
from app.models.feedback import FeedbackRaw, FeedbackLinked

logger = logging.getLogger(__name__)


class LinkingService:
    """
    Identity resolution service
    
    Matches raw messages to customers by phone number.
    Creates FeedbackLinked records with confidence scores.
    """
    
    def link_unlinked_messages(self) -> dict:
        """
        Link all FeedbackRaw records that don't have FeedbackLinked yet.
        
        Returns stats about linking.
        """
        # Find unlinked messages
        unlinked = db.session.query(FeedbackRaw).outerjoin(
            FeedbackLinked, FeedbackRaw.msg_id == FeedbackLinked.msg_id
        ).filter(FeedbackLinked.link_id == None).all()
        
        stats = {
            "total_unlinked": len(unlinked),
            "linked_exact": 0,
            "linked_new_customer": 0,
            "failed": 0
        }
        
        for raw in unlinked:
            result = self.link_message(raw)
            if result:
                if result[1] == "phone_exact":
                    stats["linked_exact"] += 1
                elif result[1] == "new_customer":
                    stats["linked_new_customer"] += 1
            else:
                stats["failed"] += 1
        
        db.session.commit()
        return stats
    
    def link_message(
        self, 
        raw: FeedbackRaw,
        create_customer_if_missing: bool = True
    ) -> Optional[Tuple[FeedbackLinked, str]]:
        """
        Link a single FeedbackRaw to a Customer.
        
        Returns (FeedbackLinked, match_method) or None if failed.
        
        Link status assignment:
        - verified: Only set manually (human validation)
        - probable: Phone exact match on real customer
        - provisional: Auto-created customer or low confidence
        - rejected: Never auto-set
        """
        if not raw.phone_number:
            logger.warning(f"FeedbackRaw {raw.msg_id} has no phone_number")
            return None
        
        # Check if already linked
        existing = FeedbackLinked.query.filter_by(msg_id=raw.msg_id).first()
        if existing:
            return (existing, "already_linked")
        
        # Try exact phone match
        customer = Customer.query.filter_by(phone_hash=raw.phone_number).first()
        
        if customer:
            # Check if customer is provisional (previously auto-created)
            if getattr(customer, 'is_provisional', False):
                confidence = 0.6
                method = "phone_provisional"
                status = "provisional"  # Provisional customer = provisional link
            else:
                confidence = 1.0
                method = "phone_exact"
                status = "probable"  # Good match but not human-verified
        elif create_customer_if_missing:
            # Create PROVISIONAL customer from phone
            customer = Customer(
                name=f"[Provisional] {raw.phone_number[:8]}...",
                phone_hash=raw.phone_number,
                consent_given=False,
                is_provisional=True
            )
            db.session.add(customer)
            db.session.flush()
            confidence = 0.5
            method = "auto_created_provisional"
            status = "provisional"  # Auto-created = always provisional
            logger.info(f"Created provisional customer from phone {raw.phone_number[:8]}...")
        else:
            return None
        
        # Create link with status
        linked = FeedbackLinked(
            msg_id=raw.msg_id,
            customer_id=customer.customer_id,
            match_confidence=confidence,
            match_method=method,
            link_status=status,
            linked_at=datetime.utcnow()
        )
        db.session.add(linked)
        db.session.flush()
        
        return (linked, method)
    
    def get_linking_stats(self) -> dict:
        """Get statistics about linking status"""
        total_raw = FeedbackRaw.query.count()
        total_linked = FeedbackLinked.query.count()
        
        # Confidence distribution
        high_conf = FeedbackLinked.query.filter(FeedbackLinked.match_confidence >= 0.9).count()
        medium_conf = FeedbackLinked.query.filter(
            FeedbackLinked.match_confidence >= 0.7,
            FeedbackLinked.match_confidence < 0.9
        ).count()
        low_conf = FeedbackLinked.query.filter(FeedbackLinked.match_confidence < 0.7).count()
        
        return {
            "total_raw": total_raw,
            "total_linked": total_linked,
            "unlinked": total_raw - total_linked,
            "high_confidence": high_conf,
            "medium_confidence": medium_conf,
            "low_confidence": low_conf
        }
