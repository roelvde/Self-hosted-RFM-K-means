"""Data ingestion logic for CSV files."""
import pandas as pd
import os
from pathlib import Path
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from app.models import Customer, Order
from app.config import settings


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime object."""
    if pd.isna(date_str) or date_str is None or date_str == '':
        return None
    
    # Try common date formats
    for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y', '%m/%d/%Y']:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    
    # If all fail, try pandas parser
    try:
        return pd.to_datetime(date_str)
    except:
        return None


def ingest_customers_from_csv(db: Session, csv_path: Optional[str] = None) -> int:
    """
    Ingest customers from CSV file.
    
    Expected CSV columns:
    - customer_id (required)
    - email (optional)
    - country (optional)
    - created_at (optional, will be parsed)
    
    Args:
        db: Database session
        csv_path: Path to CSV file. If None, uses settings.DATA_DIR/customers.csv
    
    Returns:
        Number of customers ingested/updated
    """
    if csv_path is None:
        csv_path = os.path.join(settings.DATA_DIR, "customers.csv")
    
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Customers CSV not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    # Validate required columns
    if 'customer_id' not in df.columns:
        raise ValueError("CSV must contain 'customer_id' column")
    
    count = 0
    for _, row in df.iterrows():
        customer_id = str(row['customer_id']).strip()
        if not customer_id:
            continue
        
        # Check if customer exists
        existing = db.query(Customer).filter(Customer.customer_id == customer_id).first()
        
        if existing:
            # Update existing customer
            if 'email' in df.columns and pd.notna(row.get('email')):
                existing.email = str(row['email']).strip()
            if 'country' in df.columns and pd.notna(row.get('country')):
                existing.country = str(row['country']).strip()
            if 'created_at' in df.columns:
                existing.created_at = parse_date(row.get('created_at'))
        else:
            # Create new customer
            customer = Customer(
                customer_id=customer_id,
                email=str(row['email']).strip() if 'email' in df.columns and pd.notna(row.get('email')) else None,
                country=str(row['country']).strip() if 'country' in df.columns and pd.notna(row.get('country')) else None,
                created_at=parse_date(row.get('created_at')) if 'created_at' in df.columns else None
            )
            db.add(customer)
            count += 1
    
    db.commit()
    return count


def ingest_orders_from_csv(db: Session, csv_path: Optional[str] = None) -> int:
    """
    Ingest orders from CSV file.
    
    Expected CSV columns:
    - order_id (required)
    - customer_id (required)
    - order_date (required, will be parsed)
    - order_amount (required)
    - currency (optional, defaults to 'EUR')
    - status (optional, defaults to 'completed')
    
    Args:
        db: Database session
        csv_path: Path to CSV file. If None, uses settings.DATA_DIR/orders.csv
    
    Returns:
        Number of orders ingested/updated
    """
    if csv_path is None:
        csv_path = os.path.join(settings.DATA_DIR, "orders.csv")
    
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Orders CSV not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    # Validate required columns
    required_cols = ['order_id', 'customer_id', 'order_date', 'order_amount']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"CSV must contain columns: {', '.join(missing)}")
    
    count = 0
    for _, row in df.iterrows():
        order_id = str(row['order_id']).strip()
        if not order_id:
            continue
        
        # Check if order exists
        existing = db.query(Order).filter(Order.order_id == order_id).first()
        
        customer_id = str(row['customer_id']).strip()
        order_date = parse_date(row['order_date'])
        if order_date is None:
            raise ValueError(f"Invalid order_date for order {order_id}")
        
        order_amount = float(row['order_amount'])
        currency = str(row.get('currency', 'EUR')).strip() if pd.notna(row.get('currency')) else 'EUR'
        status = str(row.get('status', 'completed')).strip() if pd.notna(row.get('status')) else 'completed'
        
        if existing:
            # Update existing order
            existing.customer_id = customer_id
            existing.order_date = order_date
            existing.order_amount = order_amount
            existing.currency = currency
            existing.status = status
        else:
            # Create new order
            order = Order(
                order_id=order_id,
                customer_id=customer_id,
                order_date=order_date,
                order_amount=order_amount,
                currency=currency,
                status=status
            )
            db.add(order)
            count += 1
    
    db.commit()
    return count


def ingest_all(db: Session) -> dict:
    """
    Ingest all data from CSV files.
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with ingestion results
    """
    results = {
        'customers_ingested': 0,
        'orders_ingested': 0,
        'errors': []
    }
    
    try:
        results['customers_ingested'] = ingest_customers_from_csv(db)
    except Exception as e:
        results['errors'].append(f"Customer ingestion error: {str(e)}")
    
    try:
        results['orders_ingested'] = ingest_orders_from_csv(db)
    except Exception as e:
        results['errors'].append(f"Order ingestion error: {str(e)}")
    
    return results

