"""
Seed Data Script

Creates sample data for testing and development.
Run with: python seed_data.py
"""
import os
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal
import random

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.feedback import FeedbackRaw, FeedbackClean
from app.models.feature import CustomerFeature
from app.models.prediction import ChurnPrediction
from app.models.action import Action


# Sample data
SAMPLE_CUSTOMERS = [
    {"name": "Ibu Sari Wijaya", "city": "Jakarta Selatan"},
    {"name": "Ibu Dewi Lestari", "city": "Jakarta Barat"},
    {"name": "Ibu Rina Kusuma", "city": "Tangerang"},
    {"name": "Ibu Maya Putri", "city": "Bekasi"},
    {"name": "Ibu Ani Handayani", "city": "Jakarta Timur"},
    {"name": "Ibu Fitri Rahayu", "city": "Depok"},
    {"name": "Ibu Linda Susanti", "city": "Bogor"},
    {"name": "Ibu Wati Purnama", "city": "Jakarta Pusat"},
    {"name": "Ibu Yuni Astuti", "city": "Tangerang Selatan"},
    {"name": "Ibu Ratna Sari", "city": "Bandung"},
]

SERVICE_TYPES = [
    "baby_spa",
    "pijat_bayi",
    "pijat_laktasi",
    "paket_bundling",
    "home_visit"
]

SAMPLE_MESSAGES = {
    "positive": [
        "Terima kasih banyak, pelayanannya sangat memuaskan 😊",
        "Baby saya jadi tenang setelah dipijat, senang sekali",
        "Mantap pelayanannya, next time booking lagi ya",
        "Terapisnya ramah dan profesional, recommended!",
        "Puas banget sama hasilnya, thank you Mamina!",
    ],
    "neutral": [
        "Mau tanya jadwal besok available jam berapa?",
        "Berapa biaya untuk pijat laktasi?",
        "Bisa booking untuk hari Sabtu?",
        "Alamat tempatnya di mana ya?",
        "Terapisnya bisa datang ke rumah?",
    ],
    "negative": [
        "Kenapa telat datangnya? Sudah nungguin lama",
        "Pelayanan kemarin kurang memuaskan",
        "Harganya kok naik? Mahal banget sekarang",
        "Terapisnya kurang ramah, kecewa saya",
        "Booking dibatalin sepihak, gimana sih?",
    ]
}


def create_admin_user():
    """Create default admin user"""
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@mamina.com",
            role="admin"
        )
        admin.set_password("mamina2024")
        db.session.add(admin)
        print("Created admin user: admin / mamina2024")
    
    # Create operator
    operator = User.query.filter_by(username="operator").first()
    if not operator:
        operator = User(
            username="operator",
            email="operator@mamina.com",
            role="operator"
        )
        operator.set_password("operator2024")
        db.session.add(operator)
        print("Created operator user: operator / operator2024")
    
    db.session.commit()


def create_customers():
    """Create sample customers"""
    customers = []
    
    for data in SAMPLE_CUSTOMERS:
        customer = Customer(
            name=data["name"],
            city=data["city"],
            consent_given=True,
            is_active=True,
            created_at=datetime.now() - timedelta(days=random.randint(30, 365))
        )
        db.session.add(customer)
        customers.append(customer)
    
    db.session.commit()
    print(f"Created {len(customers)} customers")
    return customers


def create_transactions(customers):
    """Create sample transactions for customers"""
    transactions = []
    
    for customer in customers:
        # Random number of transactions
        num_tx = random.randint(1, 15)
        
        for _ in range(num_tx):
            tx_date = datetime.now() - timedelta(days=random.randint(1, 180))
            
            tx = Transaction(
                customer_id=customer.customer_id,
                tx_date=tx_date,
                service_type=random.choice(SERVICE_TYPES),
                amount=Decimal(random.choice([150000, 200000, 250000, 300000, 500000])),
                status="completed" if random.random() > 0.1 else "cancelled"
            )
            db.session.add(tx)
            transactions.append(tx)
    
    db.session.commit()
    print(f"Created {len(transactions)} transactions")
    return transactions


def create_feedback(customers):
    """Create sample feedback messages for customers"""
    feedback_list = []
    
    for customer in customers:
        # Random number of messages
        num_messages = random.randint(3, 20)
        
        for i in range(num_messages):
            msg_time = datetime.now() - timedelta(
                days=random.randint(1, 90),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            # Pick sentiment type
            sentiment_type = random.choices(
                ["positive", "neutral", "negative"],
                weights=[0.4, 0.35, 0.25]
            )[0]
            
            text = random.choice(SAMPLE_MESSAGES[sentiment_type])
            
            # Create raw feedback
            raw = FeedbackRaw(
                customer_id=customer.customer_id,
                direction="inbound",
                text=text,
                timestamp=msg_time,
                raw_meta={"source": "whatsapp"}
            )
            db.session.add(raw)
            db.session.flush()
            
            # Create clean feedback
            sentiment_scores = {
                "positive": random.uniform(0.3, 1.0),
                "neutral": random.uniform(-0.2, 0.2),
                "negative": random.uniform(-1.0, -0.3)
            }
            
            clean = FeedbackClean(
                msg_id=raw.msg_id,
                customer_id=customer.customer_id,
                sentiment_score=sentiment_scores[sentiment_type],
                sentiment_label=sentiment_type,
                topic_labels=[random.choice(["jadwal", "harga", "layanan", "promo", "terima_kasih"])],
                keywords_emotion={"intensity": random.uniform(0.3, 0.9)},
                response_time_secs=random.randint(60, 7200),
                intensity_7d=random.randint(1, 10)
            )
            db.session.add(clean)
            feedback_list.append((raw, clean))
    
    db.session.commit()
    print(f"Created {len(feedback_list)} feedback messages")
    return feedback_list


def create_features(customers):
    """Create sample features for customers"""
    features = []
    today = date.today()
    
    for customer in customers:
        feature = CustomerFeature(
            customer_id=customer.customer_id,
            as_of_date=today,
            r_score=random.uniform(1, 5),
            f_score=random.uniform(1, 5),
            m_score=random.uniform(1, 5),
            tenure_days=random.randint(30, 365),
            avg_sentiment_30=random.uniform(-0.5, 0.8),
            neg_msg_count_30=random.randint(0, 10),
            avg_response_secs=random.randint(60, 3600),
            intensity_7d=random.randint(1, 15)
        )
        db.session.add(feature)
        features.append(feature)
    
    db.session.commit()
    print(f"Created {len(features)} feature records")
    return features


def create_predictions(customers):
    """Create sample predictions for customers"""
    predictions = []
    today = date.today()
    
    for customer in customers:
        churn_score = random.uniform(0, 1)
        
        if churn_score < 0.3:
            churn_label = "low"
        elif churn_score < 0.7:
            churn_label = "medium"
        else:
            churn_label = "high"
        
        top_reasons = [
            {
                "feature": "avg_sentiment_30",
                "impact": random.uniform(-0.5, 0.5),
                "description": "Sentimen pelanggan"
            },
            {
                "feature": "f_score",
                "impact": random.uniform(-0.3, 0.3),
                "description": "Frekuensi kunjungan"
            },
            {
                "feature": "r_score",
                "impact": random.uniform(-0.2, 0.2),
                "description": "Recency transaksi"
            }
        ]
        
        prediction = ChurnPrediction(
            customer_id=customer.customer_id,
            churn_score=churn_score,
            churn_label=churn_label,
            top_reasons=top_reasons,
            model_version="v1.0.0",
            as_of_date=today
        )
        db.session.add(prediction)
        predictions.append(prediction)
    
    db.session.commit()
    print(f"Created {len(predictions)} predictions")
    return predictions


def create_actions(predictions):
    """Create sample actions for high-risk predictions"""
    actions = []
    
    high_risk = [p for p in predictions if p.churn_label == "high"]
    
    for pred in high_risk[:5]:  # Top 5 high risk
        action = Action(
            pred_id=pred.pred_id,
            customer_id=pred.customer_id,
            action_type=random.choice(["call", "promo", "visit"]),
            priority="high",
            assigned_to="operator@mamina.com",
            status="pending",
            notes="Follow up customer dengan risiko churn tinggi",
            due_date=date.today() + timedelta(days=random.randint(1, 7))
        )
        db.session.add(action)
        actions.append(action)
    
    db.session.commit()
    print(f"Created {len(actions)} actions")
    return actions


def seed_all():
    """Run all seed functions"""
    print("=" * 50)
    print("Starting seed data creation...")
    print("=" * 50)
    
    # Create admin user
    create_admin_user()
    
    # Create customers
    customers = create_customers()
    
    # Create transactions
    create_transactions(customers)
    
    # Create feedback
    create_feedback(customers)
    
    # Create features
    create_features(customers)
    
    # Create predictions
    predictions = create_predictions(customers)
    
    # Create actions
    create_actions(predictions)
    
    print("=" * 50)
    print("Seed data creation complete!")
    print("=" * 50)
    print("\nLogin credentials:")
    print("  Admin: admin / mamina2024")
    print("  Operator: operator / operator2024")


if __name__ == "__main__":
    app = create_app()
    
    with app.app_context():
        # Create tables if not exist
        db.create_all()
        
        # Seed data
        seed_all()
