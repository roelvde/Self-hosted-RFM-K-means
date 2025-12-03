"""Tests for clustering logic."""
import pytest
import numpy as np
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import Customer, RFMFeature, CustomerCluster
from app.clustering import run_kmeans_clustering, map_cluster_to_segment
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
def sample_rfm_features(db_session):
    """Create sample RFM features for clustering."""
    calc_date = datetime(2024, 1, 15)
    
    # Create customers
    customers = [
        Customer(customer_id=f"C{i:03d}", email=f"customer{i}@test.com")
        for i in range(1, 21)  # 20 customers
    ]
    for customer in customers:
        db_session.add(customer)
    db_session.commit()
    
    # Create diverse RFM features
    rfm_features = []
    for i, customer in enumerate(customers):
        # Create different patterns
        if i < 5:
            # Champions: low recency, high frequency, high monetary
            recency = 10 + i
            frequency = 10 + i
            monetary = Decimal("500.00") + Decimal(str(i * 50))
        elif i < 10:
            # At Risk: high recency, low frequency, low monetary
            recency = 200 + i * 10
            frequency = 1
            monetary = Decimal("20.00")
        elif i < 15:
            # Loyal: low recency, high frequency, medium monetary
            recency = 20 + i
            frequency = 8
            monetary = Decimal("200.00")
        else:
            # Mixed
            recency = 100 + i
            frequency = 3
            monetary = Decimal("100.00")
        
        rfm = RFMFeature(
            customer_id=customer.customer_id,
            calc_date=calc_date,
            recency_days=recency,
            frequency=frequency,
            monetary=monetary
        )
        rfm_features.append(rfm)
        db_session.add(rfm)
    
    db_session.commit()
    return rfm_features


def test_run_kmeans_clustering(db_session, sample_rfm_features):
    """Test K-means clustering execution."""
    calc_date = datetime(2024, 1, 15)
    k = 4
    
    cluster_assignments, centroids = run_kmeans_clustering(db_session, calc_date, k)
    
    # Should have assignments for all customers
    assert len(cluster_assignments) == len(sample_rfm_features)
    
    # Should have k centroids
    assert centroids.shape[0] == k
    assert centroids.shape[1] == 3  # 3 features (R, F, M)
    
    # All assignments should have segment names
    for assignment in cluster_assignments:
        assert assignment.segment_name is not None
        assert assignment.cluster_id >= 0
        assert assignment.cluster_id < k


def test_map_cluster_to_segment():
    """Test cluster to segment name mapping."""
    # Create mock centroids (standardized space)
    centroids = np.array([
        [-1.0, 1.0, 1.0],  # Low recency, high freq, high monetary -> Champions
        [1.0, -1.0, -1.0],  # High recency, low freq, low monetary -> At Risk
        [-0.3, 0.8, 0.5],  # Medium -> Potential Loyalists
    ])
    
    segment1 = map_cluster_to_segment(0, centroids)
    assert segment1 == "Champions"
    
    segment2 = map_cluster_to_segment(1, centroids)
    assert segment2 == "At Risk"

