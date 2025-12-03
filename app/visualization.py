"""Visualization utilities for RFM clusters."""
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Tuple
from datetime import datetime
import io
import base64
from app.models import Customer, RFMFeature, CustomerCluster


def get_cluster_data(db: Session, calc_date: Optional[datetime] = None):
    """
    Get RFM and cluster data for visualization.
    
    Returns:
        List of dicts with customer_id, recency_days, frequency, monetary, segment_name, cluster_id
    """
    # If calc_date not provided, get the latest one
    if calc_date is None:
        latest_calc = db.query(func.max(CustomerCluster.calc_date)).scalar()
        if latest_calc is None:
            return []
        calc_date = latest_calc
    
    # Get all customers with RFM and cluster data
    results = db.query(
        Customer.customer_id,
        RFMFeature.recency_days,
        RFMFeature.frequency,
        RFMFeature.monetary,
        CustomerCluster.segment_name,
        CustomerCluster.cluster_id
    ).join(
        RFMFeature,
        Customer.customer_id == RFMFeature.customer_id
    ).join(
        CustomerCluster,
        Customer.customer_id == CustomerCluster.customer_id
    ).filter(
        RFMFeature.calc_date == calc_date,
        CustomerCluster.calc_date == calc_date
    ).all()
    
    return [
        {
            'customer_id': r.customer_id,
            'recency_days': r.recency_days,
            'frequency': r.frequency,
            'monetary': float(r.monetary),
            'segment_name': r.segment_name,
            'cluster_id': r.cluster_id
        }
        for r in results
    ]


def create_matplotlib_plot(
    db: Session,
    calc_date: Optional[datetime] = None,
    plot_type: str = "frequency_monetary"
) -> io.BytesIO:
    """
    Create a matplotlib plot of customers in clusters.
    
    Args:
        db: Database session
        calc_date: Calculation date (default: latest)
        plot_type: Type of plot - "frequency_monetary", "recency_frequency", or "recency_monetary"
    
    Returns:
        BytesIO buffer containing PNG image
    """
    data = get_cluster_data(db, calc_date)
    
    if not data:
        # Create empty plot with message
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No cluster data available.\nPlease run the pipeline first.', 
                ha='center', va='center', fontsize=14)
        ax.set_xticks([])
        ax.set_yticks([])
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()
        buf.seek(0)
        return buf
    
    # Extract data
    recency = [d['recency_days'] for d in data]
    frequency = [d['frequency'] for d in data]
    monetary = [d['monetary'] for d in data]
    segments = [d['segment_name'] for d in data]
    
    # Get unique segments for color mapping
    unique_segments = sorted(set(segments))
    colors = plt.cm.Set3(range(len(unique_segments)))
    segment_colors = {seg: colors[i] for i, seg in enumerate(unique_segments)}
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot based on type
    if plot_type == "frequency_monetary":
        x_data, x_label = frequency, "Frequency"
        y_data, y_label = monetary, "Monetary Value"
    elif plot_type == "recency_frequency":
        x_data, x_label = recency, "Recency (days)"
        y_data, y_label = frequency, "Frequency"
    elif plot_type == "recency_monetary":
        x_data, x_label = recency, "Recency (days)"
        y_data, y_label = monetary, "Monetary Value"
    else:
        x_data, x_label = frequency, "Frequency"
        y_data, y_label = monetary, "Monetary Value"
    
    # Plot each segment
    for segment in unique_segments:
        indices = [i for i, s in enumerate(segments) if s == segment]
        ax.scatter(
            [x_data[i] for i in indices],
            [y_data[i] for i in indices],
            c=[segment_colors[segment]],
            label=segment,
            alpha=0.6,
            s=50
        )
    
    ax.set_xlabel(x_label, fontsize=12)
    ax.set_ylabel(y_label, fontsize=12)
    ax.set_title(f'Customer Clusters - {x_label} vs {y_label}', fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buf.seek(0)
    return buf


def create_plotly_plot(
    db: Session,
    calc_date: Optional[datetime] = None,
    plot_type: str = "frequency_monetary"
) -> str:
    """
    Create an interactive Plotly plot of customers in clusters.
    
    Args:
        db: Database session
        calc_date: Calculation date (default: latest)
        plot_type: Type of plot - "frequency_monetary", "recency_frequency", or "recency_monetary"
    
    Returns:
        HTML string with embedded Plotly plot
    """
    data = get_cluster_data(db, calc_date)
    
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No cluster data available.<br>Please run the pipeline first.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig.to_html(include_plotlyjs='cdn')
    
    # Extract data
    recency = [d['recency_days'] for d in data]
    frequency = [d['frequency'] for d in data]
    monetary = [d['monetary'] for d in data]
    segments = [d['segment_name'] for d in data]
    customer_ids = [d['customer_id'] for d in data]
    
    # Create hover text
    hover_text = [
        f"Customer: {cid}<br>Segment: {seg}<br>Recency: {r} days<br>Frequency: {f}<br>Monetary: ${m:.2f}"
        for cid, seg, r, f, m in zip(customer_ids, segments, recency, frequency, monetary)
    ]
    
    # Determine axes based on plot type
    if plot_type == "frequency_monetary":
        x_data, x_label = frequency, "Frequency"
        y_data, y_label = monetary, "Monetary Value ($)"
    elif plot_type == "recency_frequency":
        x_data, x_label = recency, "Recency (days)"
        y_data, y_label = frequency, "Frequency"
    elif plot_type == "recency_monetary":
        x_data, x_label = recency, "Recency (days)"
        y_data, y_label = monetary, "Monetary Value ($)"
    else:
        x_data, x_label = frequency, "Frequency"
        y_data, y_label = monetary, "Monetary Value ($)"
    
    # Create scatter plot
    fig = px.scatter(
        x=x_data,
        y=y_data,
        color=segments,
        hover_name=customer_ids,
        hover_data={
            'Recency (days)': recency,
            'Frequency': frequency,
            'Monetary ($)': [f"${m:.2f}" for m in monetary]
        },
        labels={
            'x': x_label,
            'y': y_label,
            'color': 'Segment'
        },
        title=f'Customer Clusters - {x_label} vs {y_label}',
        width=1000,
        height=700
    )
    
    fig.update_traces(marker=dict(size=8, opacity=0.7))
    fig.update_layout(
        title_font_size=16,
        title_x=0.5,
        hovermode='closest'
    )
    
    return fig.to_html(include_plotlyjs='cdn')


def create_3d_plotly_plot(db: Session, calc_date: Optional[datetime] = None) -> str:
    """
    Create a 3D interactive Plotly plot showing all RFM dimensions.
    
    Args:
        db: Database session
        calc_date: Calculation date (default: latest)
    
    Returns:
        HTML string with embedded 3D Plotly plot
    """
    data = get_cluster_data(db, calc_date)
    
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No cluster data available.<br>Please run the pipeline first.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig.to_html(include_plotlyjs='cdn')
    
    # Extract data
    recency = [d['recency_days'] for d in data]
    frequency = [d['frequency'] for d in data]
    monetary = [d['monetary'] for d in data]
    segments = [d['segment_name'] for d in data]
    customer_ids = [d['customer_id'] for d in data]
    
    # Create 3D scatter plot
    fig = go.Figure()
    
    # Plot each segment separately for better legend
    unique_segments = sorted(set(segments))
    for segment in unique_segments:
        indices = [i for i, s in enumerate(segments) if s == segment]
        fig.add_trace(go.Scatter3d(
            x=[recency[i] for i in indices],
            y=[frequency[i] for i in indices],
            z=[monetary[i] for i in indices],
            mode='markers',
            name=segment,
            text=[customer_ids[i] for i in indices],
            hovertemplate='<b>%{text}</b><br>' +
                         'Recency: %{x} days<br>' +
                         'Frequency: %{y}<br>' +
                         'Monetary: $%{z:.2f}<br>' +
                         '<extra></extra>',
            marker=dict(
                size=5,
                opacity=0.7
            )
        ))
    
    fig.update_layout(
        title='Customer Clusters - 3D RFM View',
        scene=dict(
            xaxis_title='Recency (days)',
            yaxis_title='Frequency',
            zaxis_title='Monetary Value ($)'
        ),
        width=1000,
        height=800,
        title_x=0.5
    )
    
    return fig.to_html(include_plotlyjs='cdn')

