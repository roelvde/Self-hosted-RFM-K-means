"""RFM (Recency, Frequency, Monetary) calculation logic."""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Tuple
from app.models import Customer, Order, RFMFeature


def calculate_rfm(
    db: Session,
    calc_date: datetime,
    window_days: int = 365
) -> List[RFMFeature]:
    """
    Calculate RFM features for all customers.
    
    Args:
        db: Database session
        calc_date: Reference date for calculation
        window_days: Number of days to look back (default: 365)
    
    Returns:
        List of RFMFeature objects (not yet committed to DB)
    
    Convention for customers with no orders in window:
    - recency_days: set to window_days + 1 (very high, indicating no recent activity)
    - frequency: 0
    - monetary: 0
    """
    window_start = calc_date - timedelta(days=window_days)
    
    # Get all customers
    customers = db.query(Customer).all()
    rfm_features = []
    
    for customer in customers:
        # Get orders in the time window with status 'completed'
        orders = db.query(Order).filter(
            and_(
                Order.customer_id == customer.customer_id,
                Order.order_date >= window_start,
                Order.order_date <= calc_date,
                Order.status == 'completed'
            )
        ).all()
        
        if not orders:
            # No orders in window: set high recency, zero frequency and monetary
            recency_days = window_days + 1
            frequency = 0
            monetary = Decimal('0.00')
        else:
            # Calculate recency: days since most recent order
            max_order_date = max(order.order_date for order in orders)
            recency_days = (calc_date - max_order_date).days
            
            # Frequency: number of orders in window
            frequency = len(orders)
            
            # Monetary: sum of order amounts
            monetary = sum(order.order_amount for order in orders)
        
        # Create RFM feature record
        rfm_feature = RFMFeature(
            customer_id=customer.customer_id,
            calc_date=calc_date,
            recency_days=recency_days,
            frequency=frequency,
            monetary=monetary
        )
        rfm_features.append(rfm_feature)
    
    return rfm_features


def get_latest_rfm_features(db: Session, calc_date: datetime) -> List[RFMFeature]:
    """
    Get RFM features for the latest calculation date.
    
    Args:
        db: Database session
        calc_date: The calculation date to retrieve features for
    
    Returns:
        List of RFMFeature objects
    """
    return db.query(RFMFeature).filter(
        RFMFeature.calc_date == calc_date
    ).all()

