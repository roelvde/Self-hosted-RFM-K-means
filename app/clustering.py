"""K-means clustering logic for RFM features."""
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
from typing import List, Tuple, Dict
from app.models import RFMFeature, CustomerCluster
from datetime import datetime


def map_cluster_to_segment(
    cluster_id: int,
    centroids: np.ndarray,
    feature_names: List[str] = None
) -> str:
    """
    Map cluster ID to human-friendly segment name based on centroid values.
    
    This is a simple rule-based mapping. In production, you might want
    to use more sophisticated logic or even train a separate classifier.
    
    Assumes features are in order: [recency_days, frequency, monetary]
    Lower recency_days = more recent (better)
    Higher frequency = better
    Higher monetary = better
    
    Args:
        cluster_id: The cluster ID
        centroids: Array of cluster centroids (standardized)
        feature_names: Optional list of feature names
    
    Returns:
        Segment name string
    """
    if feature_names is None:
        feature_names = ['recency_days', 'frequency', 'monetary']
    
    # Get centroid for this cluster
    # Note: centroids are in standardized space, so we interpret:
    # - Negative recency_days (standardized) = low recency (good, recent)
    # - Positive frequency (standardized) = high frequency (good)
    # - Positive monetary (standardized) = high monetary (good)
    
    centroid = centroids[cluster_id]
    recency_std, freq_std, monetary_std = centroid[0], centroid[1], centroid[2]
    
    # Simple rule-based mapping
    # Champions: low recency (negative std), high frequency, high monetary
    # Loyal: low recency, high frequency, medium monetary
    # At Risk: high recency (positive std), low frequency, low monetary
    # etc.
    
    if recency_std < -0.5 and freq_std > 0.5 and monetary_std > 0.5:
        return "Champions"
    elif recency_std < -0.5 and freq_std > 0.5:
        return "Loyal Customers"
    elif recency_std < -0.5 and monetary_std > 0.5:
        return "Big Spenders"
    elif recency_std < 0 and freq_std > 0:
        return "Potential Loyalists"
    elif recency_std > 0.5 and freq_std < -0.5:
        return "At Risk"
    elif recency_std > 0.5:
        return "Lost"
    elif freq_std < -0.5 and monetary_std < -0.5:
        return "Hibernating"
    else:
        return "Need Attention"


def run_kmeans_clustering(
    db: Session,
    calc_date: datetime,
    k: int = 5,
    random_state: int = 42
) -> Tuple[List[CustomerCluster], np.ndarray]:
    """
    Run K-means clustering on RFM features.
    
    Args:
        db: Database session
        calc_date: Calculation date to use for RFM features
        k: Number of clusters
        random_state: Random state for reproducibility
    
    Returns:
        Tuple of (list of CustomerCluster objects, cluster centroids array)
    """
    # Get RFM features for the calculation date
    rfm_features = db.query(RFMFeature).filter(
        RFMFeature.calc_date == calc_date
    ).all()
    
    if len(rfm_features) < k:
        raise ValueError(f"Not enough customers ({len(rfm_features)}) for {k} clusters")
    
    # Extract features as numpy array
    # Features: [recency_days, frequency, monetary]
    X = np.array([
        [rfm.recency_days, rfm.frequency, float(rfm.monetary)]
        for rfm in rfm_features
    ])
    
    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Run K-means
    kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    cluster_labels = kmeans.fit_predict(X_scaled)
    
    # Get centroids (in standardized space)
    centroids_std = kmeans.cluster_centers_
    
    # Transform centroids back to original space for interpretation
    centroids_original = scaler.inverse_transform(centroids_std)
    
    # Create cluster assignments
    cluster_assignments = []
    for i, rfm in enumerate(rfm_features):
        cluster_id = int(cluster_labels[i])
        segment_name = map_cluster_to_segment(cluster_id, centroids_std)
        
        # Store centroid info as JSON string (optional)
        import json
        centroid_info = {
            'recency_days': float(centroids_original[cluster_id][0]),
            'frequency': float(centroids_original[cluster_id][1]),
            'monetary': float(centroids_original[cluster_id][2])
        }
        cluster_score = json.dumps(centroid_info)
        
        cluster_assignment = CustomerCluster(
            customer_id=rfm.customer_id,
            calc_date=calc_date,
            cluster_id=cluster_id,
            segment_name=segment_name,
            cluster_score=cluster_score
        )
        cluster_assignments.append(cluster_assignment)
    
    return cluster_assignments, centroids_original

