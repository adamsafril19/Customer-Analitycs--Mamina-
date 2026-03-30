"""
Seed Data Script

REVISED: Uses new ontology
"""
import os
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.feedback import FeedbackRaw, FeedbackFeatures
from app.models.numeric_features import CustomerNumericFeatures
from app.models.text_signals import CustomerTextSignals
from app.models.prediction import ChurnPrediction
from app.models.action import Action


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

SERVICE_TYPES = ["baby_spa", "pijat_bayi", "pijat_laktasi", "paket_bundling", "home_visit"]

SAMPLE_MESSAGES = {
    "positive": [
        "Terima kasih banyak, pelayanannya sangat memuaskan 😊",
        "Baby saya jadi tenang setelah dipijat, senang sekali",
        "Mantap pelayanannya, next time booking lagi ya",
    ],
    "neutral": [
        "Mau tanya jadwal besok available jam berapa?",
        "Berapa biaya untuk pijat laktasi?",
        "Bisa booking untuk hari Sabtu?",
    ],
    "negative": [
        "Kenapa telat datangnya? Sudah nungguin lama",
        "Pelayanan kemarin kurang memuaskan",
        "Harganya kok naik? Mahal banget sekarang",
    ]
}


def create_admin_user():
    """Create default admin user"""
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(username="admin", email="admin@mamina.com", role="admin")
        admin.set_password("mamina2024")
        db.session.add(admin)
        print("Created admin user")
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
    """Create sample transactions"""
    transactions = []
    for customer in customers:
        num_tx = random.randint(1, 15)
        for _ in range(num_tx):
            tx = Transaction(
                customer_id=customer.customer_id,
                tx_date=datetime.now() - timedelta(days=random.randint(1, 180)),
                service_type=random.choice(SERVICE_TYPES),
                amount=Decimal(random.choice([150000, 200000, 250000, 300000])),
                status="completed" if random.random() > 0.1 else "cancelled"
            )
            db.session.add(tx)
            transactions.append(tx)
    
    db.session.commit()
    print(f"Created {len(transactions)} transactions")
    return transactions


def create_feedback(customers):
    """Create sample feedback"""
    feedback_list = []
    for customer in customers:
        num_messages = random.randint(3, 10)
        for _ in range(num_messages):
            msg_time = datetime.now() - timedelta(days=random.randint(1, 90))
            sentiment_type = random.choices(["positive", "neutral", "negative"], weights=[0.4, 0.35, 0.25])[0]
            text = random.choice(SAMPLE_MESSAGES[sentiment_type])
            
            raw = FeedbackRaw(
                customer_id=customer.customer_id,
                direction="inbound",
                text=text,
                timestamp=msg_time
            )
            db.session.add(raw)
            db.session.flush()
            
            # Create features (signals only)
            features = FeedbackFeatures(
                msg_id=raw.msg_id,
                customer_id=customer.customer_id,
                msg_length=len(text),
                num_exclamations=text.count("!"),
                num_questions=text.count("?"),
                has_complaint=sentiment_type == "negative",
                response_time_secs=random.randint(60, 7200)
            )
            db.session.add(features)
            feedback_list.append(raw)
    
    db.session.commit()
    print(f"Created {len(feedback_list)} feedback messages")
    return feedback_list


def create_numeric_features(customers):
    """Create numeric features"""
    today = date.today()
    for customer in customers:
        feature = CustomerNumericFeatures(
            customer_id=customer.customer_id,
            as_of_date=today,
            recency_days=random.randint(1, 180),
            tx_count_30d=random.randint(0, 5),
            tx_count_90d=random.randint(0, 15),
            spend_30d=float(random.randint(0, 1000000)),
            spend_90d=float(random.randint(0, 3000000)),
            avg_tx_value=float(random.randint(150000, 500000)),
            tenure_days=random.randint(30, 365),
            r_score=random.uniform(1, 5),
            f_score=random.uniform(1, 5),
            m_score=random.uniform(1, 5)
        )
        db.session.add(feature)
    
    db.session.commit()
    print(f"Created numeric features for {len(customers)} customers")


def create_text_signals(customers):
    """Create text signals"""
    today = date.today()
    for customer in customers:
        signals = CustomerTextSignals(
            customer_id=customer.customer_id,
            as_of_date=today,
            msg_count_7d=random.randint(0, 10),
            msg_count_30d=random.randint(0, 30),
            msg_volatility=random.uniform(0, 5),
            avg_msg_length_30d=random.uniform(20, 200),
            complaint_rate_30d=random.uniform(0, 0.5),
            response_delay_mean=float(random.randint(60, 3600))
        )
        db.session.add(signals)
    
    db.session.commit()
    print(f"Created text signals for {len(customers)} customers")


def create_predictions(customers):
    """Create sample predictions (no top_reasons)"""
    predictions = []
    today = date.today()
    
    for customer in customers:
        churn_score = random.uniform(0, 1)
        churn_label = "low" if churn_score < 0.3 else ("medium" if churn_score < 0.7 else "high")
        
        prediction = ChurnPrediction(
            customer_id=customer.customer_id,
            churn_score=churn_score,
            churn_label=churn_label,
            model_version="v1.0.0",
            as_of_date=today
        )
        db.session.add(prediction)
        predictions.append(prediction)
    
    db.session.commit()
    print(f"Created {len(predictions)} predictions")
    return predictions


def create_actions(predictions):
    """Create sample actions"""
    actions = []
    high_risk = [p for p in predictions if p.churn_label == "high"]
    
    for pred in high_risk[:5]:
        action = Action(
            pred_id=pred.pred_id,
            customer_id=pred.customer_id,
            action_type=random.choice(["call", "promo", "visit"]),
            priority="high",
            assigned_to="operator@mamina.com",
            status="pending",
            notes="Follow up high risk customer",
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
    
    create_admin_user()
    customers = create_customers()
    create_transactions(customers)
    create_feedback(customers)
    create_numeric_features(customers)
    create_text_signals(customers)
    predictions = create_predictions(customers)
    create_actions(predictions)
    
    print("=" * 50)
    print("Seed data creation complete!")
    print("Login: admin / mamina2024")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        seed_all()
