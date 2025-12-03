"""Full pipeline orchestration: ingest -> RFM -> clustering."""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from app.db import SessionLocal
from app.config import settings
from app import ingestion, rfm, clustering
from app.models import RFMFeature, CustomerCluster


def run_full_pipeline(
    calc_date: Optional[datetime] = None,
    window_days: Optional[int] = None,
    k: Optional[int] = None
) -> dict:
    """
    Run the complete pipeline: ingest -> RFM -> clustering.
    
    Args:
        calc_date: Reference date for RFM calculation (default: now)
        window_days: RFM window in days (default: from settings)
        k: Number of clusters (default: from settings)
    
    Returns:
        Dictionary with pipeline execution results
    """
    if calc_date is None:
        calc_date = datetime.now()
    if window_days is None:
        window_days = settings.RFM_WINDOW_DAYS
    if k is None:
        k = settings.DEFAULT_K
    
    db = SessionLocal()
    results = {
        'status': 'success',
        'calc_date': calc_date.isoformat(),
        'window_days': window_days,
        'k': k,
        'ingestion': {},
        'rfm': {},
        'clustering': {},
        'errors': []
    }
    
    try:
        # Step 1: Ingest data
        try:
            ingestion_results = ingestion.ingest_all(db)
            results['ingestion'] = ingestion_results
        except Exception as e:
            results['errors'].append(f"Ingestion error: {str(e)}")
            results['ingestion'] = {'error': str(e)}
        
        # Step 2: Calculate RFM
        try:
            # Delete existing RFM features for this calc_date (idempotency)
            db.query(RFMFeature).filter(RFMFeature.calc_date == calc_date).delete()
            
            rfm_features = rfm.calculate_rfm(db, calc_date, window_days)
            db.add_all(rfm_features)
            db.commit()
            
            results['rfm'] = {
                'customers_processed': len(rfm_features)
            }
        except Exception as e:
            db.rollback()
            results['errors'].append(f"RFM calculation error: {str(e)}")
            results['rfm'] = {'error': str(e)}
        
        # Step 3: Run clustering
        try:
            # Delete existing cluster assignments for this calc_date (idempotency)
            db.query(CustomerCluster).filter(CustomerCluster.calc_date == calc_date).delete()
            
            cluster_assignments, centroids = clustering.run_kmeans_clustering(
                db, calc_date, k
            )
            db.add_all(cluster_assignments)
            db.commit()
            
            results['clustering'] = {
                'customers_clustered': len(cluster_assignments),
                'clusters_created': k
            }
        except Exception as e:
            db.rollback()
            results['errors'].append(f"Clustering error: {str(e)}")
            results['clustering'] = {'error': str(e)}
        
        if results['errors']:
            results['status'] = 'partial_success'
        
    except Exception as e:
        results['status'] = 'error'
        results['errors'].append(f"Pipeline error: {str(e)}")
    finally:
        db.close()
    
    return results


if __name__ == "__main__":
    """CLI entrypoint for running the pipeline."""
    import sys
    
    # Parse command line arguments (simple version)
    calc_date = None
    window_days = None
    k = None
    
    if len(sys.argv) > 1:
        # Simple argument parsing (can be enhanced)
        for arg in sys.argv[1:]:
            if arg.startswith('--window-days='):
                window_days = int(arg.split('=')[1])
            elif arg.startswith('--k='):
                k = int(arg.split('=')[1])
            elif arg.startswith('--calc-date='):
                from datetime import datetime
                calc_date = datetime.fromisoformat(arg.split('=')[1])
    
    results = run_full_pipeline(calc_date=calc_date, window_days=window_days, k=k)
    
    print("Pipeline execution completed:")
    print(f"Status: {results['status']}")
    print(f"Calc date: {results['calc_date']}")
    print(f"Window days: {results['window_days']}")
    print(f"K: {results['k']}")
    print(f"Ingestion: {results['ingestion']}")
    print(f"RFM: {results['rfm']}")
    print(f"Clustering: {results['clustering']}")
    if results['errors']:
        print(f"Errors: {results['errors']}")

