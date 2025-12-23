"""
Test Configuration
"""
import pytest
import os
from app import create_app, db
from app.models.user import User
from app.models.customer import Customer


@pytest.fixture(scope="session")
def app():
    """Create application for testing"""
    # Set test config
    os.environ["FLASK_ENV"] = "testing"
    
    app = create_app("testing")
    
    # Create tables
    with app.app_context():
        db.create_all()
        
        # Create test admin user
        admin = User(
            username="testadmin",
            email="admin@test.com",
            role="admin"
        )
        admin.set_password("testpassword")
        db.session.add(admin)
        
        # Create test operator user
        operator = User(
            username="testoperator",
            email="operator@test.com",
            role="operator"
        )
        operator.set_password("testpassword")
        db.session.add(operator)
        
        db.session.commit()
    
    yield app
    
    # Cleanup
    with app.app_context():
        db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture(scope="function")
def auth_headers(client):
    """Get authentication headers for admin user"""
    response = client.post("/api/auth/login", json={
        "username": "testadmin",
        "password": "testpassword"
    })
    data = response.get_json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture(scope="function")
def operator_headers(client):
    """Get authentication headers for operator user"""
    response = client.post("/api/auth/login", json={
        "username": "testoperator",
        "password": "testpassword"
    })
    data = response.get_json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture(scope="function")
def sample_customer(app):
    """Create sample customer for testing"""
    with app.app_context():
        customer = Customer(
            name="Test Customer",
            city="Jakarta",
            consent_given=True
        )
        db.session.add(customer)
        db.session.commit()
        
        customer_id = str(customer.customer_id)
    
    return customer_id


@pytest.fixture(scope="function")
def db_session(app):
    """Provide database session for tests"""
    with app.app_context():
        yield db.session
        db.session.rollback()
