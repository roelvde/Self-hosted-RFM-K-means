"""Tests for RFM calculation logic."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import Customer, Order, RFMFeature
from app.rfm import calculate_rfm
from app.db import Base, engine, SessionLocal


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_customers(db_session):
    """Create sample customers."""
    customers = [
        Customer(customer_id="C001", email="customer1@test.com", country="US"),
        Customer(customer_id="C002", email="customer2@test.com", country="UK"),
        Customer(customer_id="C003", email="customer3@test.com", country="CA"),
    ]
    for customer in customers:
        db_session.add(customer)
    db_session.commit()
    return customers


@pytest.fixture
def sample_orders(db_session, sample_customers):
    """Create sample orders."""
    calc_date = datetime(2024, 1, 15)
    
    orders = [
        # Customer 1: recent, frequent, high value
        Order(
            order_id="O001",
            customer_id="C001",
            order_date=calc_date - timedelta(days=5),
            order_amount=Decimal("100.00"),
            status="completed"
        ),
        Order(
            order_id="O002",
            customer_id="C001",
            order_date=calc_date - timedelta(days=10),
            order_amount=Decimal("150.00"),
            status="completed"
        ),
        # Customer 2: old, infrequent, low value
        Order(
            order_id="O003",
            customer_id="C002",
            order_date=calc_date - timedelta(days=200),
            order_amount=Decimal("20.00"),
            status="completed"
        ),
        # Customer 3: no orders (will test default behavior)
    ]
    
    for order in orders:
        db_session.add(order)
    db_session.commit()
    return orders


def test_calculate_rfm_with_orders(db_session, sample_customers, sample_orders):
    """Test RFM calculation for customers with orders."""
    calc_date = datetime(2024, 1, 15)
    window_days = 365
    
    rfm_features = calculate_rfm(db_session, calc_date, window_days)
    
    # Should have RFM for all customers
    assert len(rfm_features) == 3
    
    # Find customer 1's RFM
    c1_rfm = next(rfm for rfm in rfm_features if rfm.customer_id == "C001")
    assert c1_rfm.recency_days == 5  # Most recent order was 5 days ago
    assert c1_rfm.frequency == 2  # 2 orders
    assert c1_rfm.monetary == Decimal("250.00")  # 100 + 150
    
    # Find customer 2's RFM
    c2_rfm = next(rfm for rfm in rfm_features if rfm.customer_id == "C002")
    assert c2_rfm.recency_days == 200  # Most recent order was 200 days ago
    assert c2_rfm.frequency == 1  # 1 order
    assert c2_rfm.monetary == Decimal("20.00")


def test_calculate_rfm_no_orders(db_session, sample_customers):
    """Test RFM calculation for customers with no orders."""
    calc_date = datetime(2024, 1, 15)
    window_days = 365
    
    rfm_features = calculate_rfm(db_session, calc_date, window_days)
    
    # Find customer 3's RFM (no orders)
    c3_rfm = next(rfm for rfm in rfm_features if rfm.customer_id == "C003")
    assert c3_rfm.recency_days == window_days + 1  # High recency (no activity)
    assert c3_rfm.frequency == 0
    assert c3_rfm.monetary == Decimal("0.00")


def test_calculate_rfm_only_completed_orders(db_session, sample_customers):
    """Test that only completed orders are counted."""
    calc_date = datetime(2024, 1, 15)
    
    # Add a cancelled order
    cancelled_order = Order(
        order_id="O004",
        customer_id="C001",
        order_date=calc_date - timedelta(days=1),
        order_amount=Decimal("50.00"),
        status="cancelled"
    )
    db_session.add(cancelled_order)
    db_session.commit()
    
    window_days = 365
    rfm_features = calculate_rfm(db_session, calc_date, window_days)
    
    c1_rfm = next(rfm for rfm in rfm_features if rfm.customer_id == "C001")
    # Should still be 250.00 (cancelled order not counted)
    assert c1_rfm.monetary == Decimal("250.00")

