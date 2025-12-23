"""
API Endpoint Tests
"""
import pytest
import json


class TestHealthEndpoint:
    """Tests for health check endpoints"""
    
    def test_health_check_returns_ok(self, client):
        """Test health check returns OK status"""
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] in ["ok", "degraded"]
        assert "timestamp" in data
        assert "model_loaded" in data
    
    def test_liveness_check(self, client):
        """Test liveness check for k8s"""
        response = client.get("/api/live")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["alive"] is True


class TestAuthEndpoints:
    """Tests for authentication endpoints"""
    
    def test_login_success(self, client):
        """Test successful login"""
        response = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpassword"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "testadmin"
    
    def test_login_invalid_password(self, client):
        """Test login with invalid password"""
        response = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
    
    def test_login_missing_fields(self, client):
        """Test login with missing fields"""
        response = client.post("/api/auth/login", json={
            "username": "testadmin"
        })
        
        assert response.status_code == 400
    
    def test_get_current_user(self, client, auth_headers):
        """Test getting current user info"""
        response = client.get("/api/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["username"] == "testadmin"
        assert data["role"] == "admin"
    
    def test_refresh_token(self, client):
        """Test token refresh"""
        # First login to get refresh token
        login_response = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpassword"
        })
        refresh_token = login_response.get_json()["refresh_token"]
        
        # Use refresh token
        response = client.post("/api/auth/refresh", headers={
            "Authorization": f"Bearer {refresh_token}"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert "access_token" in data


class TestCustomerEndpoints:
    """Tests for customer endpoints"""
    
    def test_create_customer(self, client, auth_headers):
        """Test customer creation"""
        response = client.post("/api/customers", 
            headers=auth_headers,
            json={
                "name": "New Customer",
                "city": "Surabaya",
                "consent_given": True
            }
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "New Customer"
        assert data["city"] == "Surabaya"
        assert "customer_id" in data
    
    def test_create_customer_missing_name(self, client, auth_headers):
        """Test customer creation without name"""
        response = client.post("/api/customers",
            headers=auth_headers,
            json={"city": "Jakarta"}
        )
        
        assert response.status_code == 400
    
    def test_get_customer(self, client, auth_headers, sample_customer):
        """Test getting customer details"""
        response = client.get(
            f"/api/customers/{sample_customer}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Test Customer"
    
    def test_get_customer_not_found(self, client, auth_headers):
        """Test getting non-existent customer"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.get(
            f"/api/customers/{fake_uuid}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_update_customer(self, client, auth_headers, sample_customer):
        """Test updating customer"""
        response = client.patch(
            f"/api/customers/{sample_customer}",
            headers=auth_headers,
            json={"city": "Bandung"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["city"] == "Bandung"
    
    def test_list_customers(self, client, auth_headers, sample_customer):
        """Test listing customers"""
        response = client.get("/api/customers", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert "total" in data
        assert "customers" in data
        assert isinstance(data["customers"], list)
    
    def test_customer_360_view(self, client, auth_headers, sample_customer):
        """Test customer 360 view"""
        response = client.get(
            f"/api/customers/{sample_customer}/360",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert "customer" in data
        assert "rfm_features" in data
        assert "sentiment_summary" in data
        assert "transaction_summary" in data


class TestActionEndpoints:
    """Tests for action endpoints"""
    
    def test_create_action(self, client, auth_headers, sample_customer):
        """Test action creation"""
        response = client.post("/api/actions",
            headers=auth_headers,
            json={
                "customer_id": sample_customer,
                "action_type": "call",
                "priority": "high",
                "notes": "Follow up call"
            }
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data["action_type"] == "call"
        assert data["priority"] == "high"
        assert data["status"] == "pending"
    
    def test_create_action_invalid_type(self, client, auth_headers, sample_customer):
        """Test action creation with invalid type"""
        response = client.post("/api/actions",
            headers=auth_headers,
            json={
                "customer_id": sample_customer,
                "action_type": "invalid_type"
            }
        )
        
        assert response.status_code == 400
    
    def test_list_actions(self, client, auth_headers):
        """Test listing actions"""
        response = client.get("/api/actions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert "total" in data
        assert "actions" in data


class TestAuthorizationRequired:
    """Tests for authorization requirements"""
    
    def test_customers_requires_auth(self, client):
        """Test that customers endpoint requires authentication"""
        response = client.get("/api/customers")
        assert response.status_code == 401
    
    def test_predictions_requires_auth(self, client):
        """Test that predictions endpoint requires authentication"""
        response = client.get("/api/predictions")
        assert response.status_code == 401
    
    def test_actions_requires_auth(self, client):
        """Test that actions endpoint requires authentication"""
        response = client.get("/api/actions")
        assert response.status_code == 401
