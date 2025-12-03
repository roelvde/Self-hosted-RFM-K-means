"""SQLAlchemy database models."""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class Customer(Base):
    """Customer model."""
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, unique=True, index=True, nullable=False)  # Business key
    email = Column(String, nullable=True)
    country = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    
    # Relationships
    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    rfm_features = relationship("RFMFeature", back_populates="customer", cascade="all, delete-orphan")
    clusters = relationship("CustomerCluster", back_populates="customer", cascade="all, delete-orphan")


class Order(Base):
    """Order model."""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True, nullable=False)  # Business key
    customer_id = Column(String, ForeignKey("customers.customer_id"), index=True, nullable=False)
    order_date = Column(DateTime, nullable=False, index=True)
    order_amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="EUR", nullable=False)
    status = Column(String, nullable=False)  # e.g., 'completed', 'cancelled', 'refunded'
    
    # Relationship
    customer = relationship("Customer", back_populates="orders")


class RFMFeature(Base):
    """RFM features calculated for customers."""
    __tablename__ = "rfm_features"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), index=True, nullable=False)
    calc_date = Column(DateTime, nullable=False, index=True)
    recency_days = Column(Integer, nullable=False)
    frequency = Column(Integer, nullable=False)
    monetary = Column(Numeric(10, 2), nullable=False)
    
    # Relationship
    customer = relationship("Customer", back_populates="rfm_features")
    
    # Unique constraint: one RFM calculation per customer per date
    __table_args__ = (
        UniqueConstraint('customer_id', 'calc_date', name='uq_customer_calc_date'),
        Index('idx_customer_calc_date', 'customer_id', 'calc_date'),
    )


class CustomerCluster(Base):
    """K-means cluster assignments for customers."""
    __tablename__ = "customer_clusters"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), index=True, nullable=False)
    calc_date = Column(DateTime, nullable=False, index=True)
    cluster_id = Column(Integer, nullable=False)  # Raw K-means label
    segment_name = Column(String, nullable=False)  # Human-friendly label
    cluster_score = Column(String, nullable=True)  # JSON string with metrics (optional)
    
    # Relationship
    customer = relationship("Customer", back_populates="clusters")
    
    # Unique constraint: one cluster assignment per customer per date
    __table_args__ = (
        UniqueConstraint('customer_id', 'calc_date', name='uq_customer_cluster_calc_date'),
        Index('idx_customer_cluster_calc_date', 'customer_id', 'calc_date'),
    )

