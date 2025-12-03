"""Tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.api import app
from app.db import Base, engine, SessionLocal, get_db
from app.models import Customer, Order, RFMFeature, CustomerCluster
from datetime import datetime, timedelta
from decimal import Decimal


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create a test client with database dependency override."""
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data


def test_get_segments_empty(client):
    """Test getting segments when none exist."""
    response = client.get("/segments")
    assert response.status_code == 404


def test_get_customer_not_found(client):
    """Test getting a non-existent customer."""
    response = client.get("/customers/NONEXISTENT")
    assert response.status_code == 404

