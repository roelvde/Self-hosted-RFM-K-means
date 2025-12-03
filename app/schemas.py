"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class CustomerBase(BaseModel):
    """Base customer schema."""
    customer_id: str
    email: Optional[str] = None
    country: Optional[str] = None
    created_at: Optional[datetime] = None


class CustomerCreate(CustomerBase):
    """Schema for creating a customer."""
    pass


class CustomerResponse(CustomerBase):
    """Schema for customer response."""
    id: int
    
    model_config = {"from_attributes": True}


class OrderBase(BaseModel):
    """Base order schema."""
    order_id: str
    customer_id: str
    order_date: datetime
    order_amount: Decimal
    currency: str = "EUR"
    status: str


class OrderCreate(OrderBase):
    """Schema for creating an order."""
    pass


class OrderResponse(OrderBase):
    """Schema for order response."""
    id: int
    
    model_config = {"from_attributes": True}


class RFMFeatureResponse(BaseModel):
    """Schema for RFM feature response."""
    customer_id: str
    calc_date: datetime
    recency_days: int
    frequency: int
    monetary: Decimal
    
    model_config = {"from_attributes": True}


class ClusterResponse(BaseModel):
    """Schema for cluster assignment response."""
    customer_id: str
    calc_date: datetime
    cluster_id: int
    segment_name: str
    cluster_score: Optional[str] = None
    
    model_config = {"from_attributes": True}


class CustomerDetailResponse(BaseModel):
    """Schema for detailed customer response with RFM and segment."""
    customer_id: str
    email: Optional[str]
    country: Optional[str]
    rfm: Optional[RFMFeatureResponse] = None
    segment: Optional[ClusterResponse] = None
    
    model_config = {"from_attributes": True}


class SegmentStats(BaseModel):
    """Schema for segment statistics."""
    segment_name: str
    cluster_id: int
    customer_count: int
    avg_recency_days: float
    avg_frequency: float
    avg_monetary: float


class SegmentListResponse(BaseModel):
    """Schema for segment list response."""
    calc_date: datetime
    segments: List[SegmentStats]


class PipelineRunRequest(BaseModel):
    """Schema for pipeline run request."""
    calc_date: Optional[datetime] = Field(default_factory=datetime.now)
    window_days: Optional[int] = None
    k: Optional[int] = None


class PipelineRunResponse(BaseModel):
    """Schema for pipeline run response."""
    status: str
    calc_date: datetime
    window_days: int
    k: int
    customers_processed: int
    clusters_created: int
    message: str


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    database: Optional[str] = None

