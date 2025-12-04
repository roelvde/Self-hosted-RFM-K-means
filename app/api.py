"""FastAPI endpoints for RFM segmentation."""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, HTMLResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
from typing import Optional, List
from datetime import datetime
import csv
import io
from app.db import get_db, init_db
from app import visualization
from app.schemas import (
    HealthResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    SegmentListResponse,
    SegmentStats,
    CustomerDetailResponse,
    RFMFeatureResponse,
    ClusterResponse
)
from app.models import Customer, RFMFeature, CustomerCluster, Order
from app.pipeline.run_full import run_full_pipeline
from app.config import settings

app = FastAPI(title="RFM Segmentation API", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint met basisstatistieken."""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Basisstatistieken (best-effort; bij fouten vallen we terug op None)
    latest_calc_date = db.query(func.max(CustomerCluster.calc_date)).scalar()
    total_customers = db.query(func.count(Customer.id)).scalar()
    total_orders = db.query(func.count(Order.id)).scalar()
    total_clusters = db.query(func.count(CustomerCluster.id)).scalar()
    
    # HealthResponse is bewust minimaal gehouden (status + database);
    # we geven extra info terug als losse velden in de JSON-respons.
    base = HealthResponse(status="ok", database=db_status)
    return {
        **base.model_dump(),
        "latest_calc_date": latest_calc_date,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "total_clusters": total_clusters,
    }


@app.post("/pipeline/run", response_model=PipelineRunResponse)
async def run_pipeline(
    request: Optional[PipelineRunRequest] = None,
    db: Session = Depends(get_db)
):
    """Trigger the full RFM + clustering pipeline."""
    if request is None:
        request = PipelineRunRequest()
    
    calc_date = request.calc_date or datetime.now()
    window_days = request.window_days or settings.RFM_WINDOW_DAYS
    k = request.k or settings.DEFAULT_K
    
    # Run pipeline
    results = run_full_pipeline(calc_date=calc_date, window_days=window_days, k=k)
    
    if results['status'] == 'error':
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {results.get('errors', [])}")
    
    customers_processed = results.get('rfm', {}).get('customers_processed', 0)
    clusters_created = results.get('clustering', {}).get('clusters_created', k)
    
    return PipelineRunResponse(
        status=results['status'],
        calc_date=calc_date,
        window_days=window_days,
        k=k,
        customers_processed=customers_processed,
        clusters_created=clusters_created,
        message="Pipeline completed successfully" if results['status'] == 'success' else "Pipeline completed with warnings"
    )


@app.get("/segments", response_model=SegmentListResponse)
async def get_segments(
    calc_date: Optional[datetime] = Query(None, description="Calculation date. If not provided, uses latest."),
    db: Session = Depends(get_db)
):
    """Get list of all segments with statistics."""
    # If calc_date not provided, get the latest one
    if calc_date is None:
        latest_calc = db.query(func.max(CustomerCluster.calc_date)).scalar()
        if latest_calc is None:
            raise HTTPException(status_code=404, detail="No segments found. Run pipeline first.")
        calc_date = latest_calc
    
    # Get segment statistics
    segment_stats = db.query(
        CustomerCluster.segment_name,
        CustomerCluster.cluster_id,
        func.count(CustomerCluster.customer_id).label('customer_count'),
        func.avg(RFMFeature.recency_days).label('avg_recency_days'),
        func.avg(RFMFeature.frequency).label('avg_frequency'),
        func.avg(RFMFeature.monetary).label('avg_monetary')
    ).join(
        RFMFeature,
        and_(
            CustomerCluster.customer_id == RFMFeature.customer_id,
            CustomerCluster.calc_date == RFMFeature.calc_date
        )
    ).filter(
        CustomerCluster.calc_date == calc_date
    ).group_by(
        CustomerCluster.segment_name,
        CustomerCluster.cluster_id
    ).all()
    
    segments = [
        SegmentStats(
            segment_name=stat.segment_name,
            cluster_id=stat.cluster_id,
            customer_count=stat.customer_count,
            avg_recency_days=float(stat.avg_recency_days or 0),
            avg_frequency=float(stat.avg_frequency or 0),
            avg_monetary=float(stat.avg_monetary or 0)
        )
        for stat in segment_stats
    ]
    
    return SegmentListResponse(calc_date=calc_date, segments=segments)


@app.get("/segments/{segment_name}/customers")
async def get_segment_customers(
    segment_name: str,
    calc_date: Optional[datetime] = Query(None, description="Calculation date. If not provided, uses latest."),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get paginated list of customers in a segment."""
    # If calc_date not provided, get the latest one
    if calc_date is None:
        latest_calc = db.query(func.max(CustomerCluster.calc_date)).scalar()
        if latest_calc is None:
            raise HTTPException(status_code=404, detail="No segments found. Run pipeline first.")
        calc_date = latest_calc
    
    # Get customers in segment
    offset = (page - 1) * page_size
    
    customers = db.query(Customer, RFMFeature, CustomerCluster).join(
        CustomerCluster,
        and_(
            Customer.customer_id == CustomerCluster.customer_id,
            CustomerCluster.calc_date == calc_date,
            CustomerCluster.segment_name == segment_name
        )
    ).join(
        RFMFeature,
        and_(
            Customer.customer_id == RFMFeature.customer_id,
            RFMFeature.calc_date == calc_date
        )
    ).offset(offset).limit(page_size).all()
    
    results = []
    for customer, rfm, cluster in customers:
        results.append({
            'customer_id': customer.customer_id,
            'email': customer.email,
            'country': customer.country,
            'recency_days': rfm.recency_days,
            'frequency': rfm.frequency,
            'monetary': float(rfm.monetary),
            'segment_name': cluster.segment_name,
            'cluster_id': cluster.cluster_id
        })
    
    return {
        'segment_name': segment_name,
        'calc_date': calc_date,
        'page': page,
        'page_size': page_size,
        'customers': results
    }


@app.get("/customers/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(
    customer_id: str,
    calc_date: Optional[datetime] = Query(None, description="Calculation date. If not provided, uses latest."),
    db: Session = Depends(get_db)
):
    """Get customer details with RFM and segment information."""
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    
    # If calc_date not provided, get the latest one
    if calc_date is None:
        latest_calc = db.query(func.max(RFMFeature.calc_date)).filter(
            RFMFeature.customer_id == customer_id
        ).scalar()
        if latest_calc is None:
            return CustomerDetailResponse(
                customer_id=customer.customer_id,
                email=customer.email,
                country=customer.country,
                rfm=None,
                segment=None
            )
        calc_date = latest_calc
    
    # Get RFM features
    rfm_feature = db.query(RFMFeature).filter(
        and_(
            RFMFeature.customer_id == customer_id,
            RFMFeature.calc_date == calc_date
        )
    ).first()
    
    # Get cluster assignment
    cluster = db.query(CustomerCluster).filter(
        and_(
            CustomerCluster.customer_id == customer_id,
            CustomerCluster.calc_date == calc_date
        )
    ).first()
    
    rfm_response = RFMFeatureResponse.model_validate(rfm_feature) if rfm_feature else None
    cluster_response = ClusterResponse.model_validate(cluster) if cluster else None
    
    return CustomerDetailResponse(
        customer_id=customer.customer_id,
        email=customer.email,
        country=customer.country,
        rfm=rfm_response,
        segment=cluster_response
    )


@app.get("/export/segments/{segment_name}")
async def export_segment(
    segment_name: str,
    calc_date: Optional[datetime] = Query(None, description="Calculation date. If not provided, uses latest."),
    db: Session = Depends(get_db)
):
    """Export segment customers as CSV."""
    # If calc_date not provided, get the latest one
    if calc_date is None:
        latest_calc = db.query(func.max(CustomerCluster.calc_date)).scalar()
        if latest_calc is None:
            raise HTTPException(status_code=404, detail="No segments found. Run pipeline first.")
        calc_date = latest_calc
    
    # Get all customers in segment
    customers = db.query(Customer, CustomerCluster).join(
        CustomerCluster,
        and_(
            Customer.customer_id == CustomerCluster.customer_id,
            CustomerCluster.calc_date == calc_date,
            CustomerCluster.segment_name == segment_name
        )
    ).all()
    
    if not customers:
        raise HTTPException(status_code=404, detail=f"No customers found in segment '{segment_name}'")
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['customer_id', 'email', 'country', 'segment_name'])
    
    # Write data
    for customer, cluster in customers:
        writer.writerow([
            customer.customer_id,
            customer.email or '',
            customer.country or '',
            cluster.segment_name
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=segment_{segment_name}_{calc_date.date()}.csv"
        }
    )


@app.get("/dashboard")
async def dashboard(db: Session = Depends(get_db)):
    """Eenvoudig HTML-dashboard met kernstatistieken en segmentoverzicht."""
    # Get latest calc_date
    latest_calc = db.query(func.max(CustomerCluster.calc_date)).scalar()
    total_customers = db.query(func.count(Customer.id)).scalar()
    total_orders = db.query(func.count(Order.id)).scalar()
    total_clusters = db.query(func.count(CustomerCluster.id)).scalar()

    if latest_calc is None:
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>RFM Segmentation Dashboard</title></head>
        <body>
            <h1>RFM Segmentation Dashboard</h1>
            <p>No segments found. Please run the pipeline first.</p>
            <p><strong>Total customers:</strong> %d</p>
            <p><strong>Total orders:</strong> %d</p>
            <p><a href="/docs">API Documentation</a></p>
        </body>
        </html>
        """ % (total_customers or 0, total_orders or 0)
        return HTMLResponse(content=html)
    
    # Get segment statistics
    segment_stats = db.query(
        CustomerCluster.segment_name,
        CustomerCluster.cluster_id,
        func.count(CustomerCluster.customer_id).label('customer_count'),
        func.avg(RFMFeature.recency_days).label('avg_recency_days'),
        func.avg(RFMFeature.frequency).label('avg_frequency'),
        func.avg(RFMFeature.monetary).label('avg_monetary')
    ).join(
        RFMFeature,
        and_(
            CustomerCluster.customer_id == RFMFeature.customer_id,
            CustomerCluster.calc_date == RFMFeature.calc_date
        )
    ).filter(
        CustomerCluster.calc_date == latest_calc
    ).group_by(
        CustomerCluster.segment_name,
        CustomerCluster.cluster_id
    ).all()
    
    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>RFM Segmentation Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #4CAF50; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            h1 {{ color: #333; }}
            .stats {{ margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>RFM Segmentation Dashboard</h1>
        <div class="stats">
            <p><strong>Calculation Date:</strong> {latest_calc.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>
                <strong>Total customers:</strong> {total_customers or 0} |
                <strong>Total orders:</strong> {total_orders or 0} |
                <strong>Total cluster assignments:</strong> {total_clusters or 0}
            </p>
            <p>
                <a href="/docs">API Documentation</a> | 
                <a href="/health">Health Check</a> |
                <a href="/visualization/interactive?plot_type=frequency_monetary">View Interactive Plot</a> |
                <a href="/visualization/3d">View 3D Plot</a>
            </p>
        </div>
        
        <h2>Cluster Visualizations</h2>
        <div style="margin: 20px 0;">
            <h3>Frequency vs Monetary</h3>
            <img src="/visualization/plot?plot_type=frequency_monetary" alt="Frequency vs Monetary" style="max-width: 100%; border: 1px solid #ddd; padding: 10px; background: white;">
            <p style="margin-top: 10px;">
                <a href="/visualization/interactive?plot_type=frequency_monetary" target="_blank">View Interactive Version</a>
            </p>
        </div>
        
        <div style="margin: 20px 0;">
            <h3>Recency vs Frequency</h3>
            <img src="/visualization/plot?plot_type=recency_frequency" alt="Recency vs Frequency" style="max-width: 100%; border: 1px solid #ddd; padding: 10px; background: white;">
            <p style="margin-top: 10px;">
                <a href="/visualization/interactive?plot_type=recency_frequency" target="_blank">View Interactive Version</a>
            </p>
        </div>
        
        <div style="margin: 20px 0;">
            <h3>Recency vs Monetary</h3>
            <img src="/visualization/plot?plot_type=recency_monetary" alt="Recency vs Monetary" style="max-width: 100%; border: 1px solid #ddd; padding: 10px; background: white;">
            <p style="margin-top: 10px;">
                <a href="/visualization/interactive?plot_type=recency_monetary" target="_blank">View Interactive Version</a>
            </p>
        </div>
        
        <h2>Segment Statistics</h2>
        <table>
            <thead>
                <tr>
                    <th>Segment Name</th>
                    <th>Cluster ID</th>
                    <th>Customer Count</th>
                    <th>Avg Recency (days)</th>
                    <th>Avg Frequency</th>
                    <th>Avg Monetary</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for stat in segment_stats:
        html += f"""
                <tr>
                    <td>{stat.segment_name}</td>
                    <td>{stat.cluster_id}</td>
                    <td>{stat.customer_count}</td>
                    <td>{stat.avg_recency_days:.1f}</td>
                    <td>{stat.avg_frequency:.1f}</td>
                    <td>{stat.avg_monetary:.2f}</td>
                </tr>
        """
    
    html += """
            </tbody>
        </table>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)


@app.get("/visualization/plot")
async def get_plot(
    plot_type: str = Query("frequency_monetary", description="Plot type: frequency_monetary, recency_frequency, or recency_monetary"),
    calc_date: Optional[datetime] = Query(None, description="Calculation date. If not provided, uses latest."),
    db: Session = Depends(get_db)
):
    """Get a matplotlib PNG plot of customers in clusters."""
    plot_buffer = visualization.create_matplotlib_plot(db, calc_date, plot_type)
    return Response(
        content=plot_buffer.read(),
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename=rfm_clusters_{plot_type}.png"
        }
    )


@app.get("/visualization/interactive")
async def get_interactive_plot(
    plot_type: str = Query("frequency_monetary", description="Plot type: frequency_monetary, recency_frequency, or recency_monetary"),
    calc_date: Optional[datetime] = Query(None, description="Calculation date. If not provided, uses latest."),
    db: Session = Depends(get_db)
):
    """Get an interactive Plotly HTML plot of customers in clusters."""
    html_content = visualization.create_plotly_plot(db, calc_date, plot_type)
    return HTMLResponse(content=html_content)


@app.get("/visualization/3d")
async def get_3d_plot(
    calc_date: Optional[datetime] = Query(None, description="Calculation date. If not provided, uses latest."),
    db: Session = Depends(get_db)
):
    """Get an interactive 3D Plotly plot showing all RFM dimensions."""
    html_content = visualization.create_3d_plotly_plot(db, calc_date)
    return HTMLResponse(content=html_content)

