# RFM + K-Means Customer Segmentation MVP

A self-hosted, Dockerized MVP for customer segmentation using RFM (Recency, Frequency, Monetary) analysis combined with K-means clustering.

## Features

- **Data Ingestion**: Import customer and order data from CSV files
- **RFM Calculation**: Automated calculation of Recency, Frequency, and Monetary values
- **K-Means Clustering**: Customer segmentation using machine learning
- **REST API**: Full API for triggering pipelines and querying segments
- **Dashboard**: Simple web dashboard for viewing segment statistics
- **Visualizations**: Interactive and static plots showing customers in clusters
  - 2D scatter plots (Frequency vs Monetary, Recency vs Frequency, Recency vs Monetary)
  - 3D interactive plot showing all RFM dimensions
- **CSV Export**: Export customer lists by segment
- **Dockerized**: Easy deployment with Docker Compose

## Tech Stack

- **Backend**: Python 3.11 + FastAPI
- **Database**: PostgreSQL 15
- **ORM**: SQLAlchemy
- **ML**: scikit-learn
- **Containerization**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- (Optional) Python 3.11+ for local development

### 1. Clone and Setup

```bash
git clone <repository-url>
cd rfm
```

### 2. Configure Environment

Create a `.env` file in the project root (or use environment variables):

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=55432
DB_NAME=rfm_db
DB_USER=rfm_user
DB_PASSWORD=rfm_password

# Application Configuration
RFM_WINDOW_DAYS=365
DEFAULT_K=5
DATA_DIR=./data/input

# API Configuration
API_PORT=8701
```

### 3. Start Services

```bash
docker-compose up --build
```

This will:
- Start PostgreSQL database
- Start the FastAPI application
- Create necessary database tables automatically

The API will be available at `http://localhost:8701`

### 4. Prepare Data

Place your CSV files in the `data/input/` directory:

**`data/input/customers.csv`** (required columns: `customer_id`):
```csv
customer_id,email,country,created_at
C001,customer1@example.com,US,2023-01-15
C002,customer2@example.com,UK,2023-02-20
```

**`data/input/orders.csv`** (required columns: `order_id`, `customer_id`, `order_date`, `order_amount`):
```csv
order_id,customer_id,order_date,order_amount,currency,status
O001,C001,2024-01-10,100.00,EUR,completed
O002,C001,2024-01-05,150.00,EUR,completed
O003,C002,2023-06-15,50.00,EUR,completed
```

### 5. Run the Pipeline

#### Option A: Via API

```bash
curl -X POST "http://localhost:8701/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "calc_date": "2024-01-15T00:00:00",
    "window_days": 365,
    "k": 5
  }'
```

#### Option B: Via CLI (inside container)

```bash
docker-compose exec app python -m app.pipeline.run_full
```

### 6. View Results

- **Dashboard**: Open `http://localhost:8701/dashboard` in your browser (includes visualizations!)
- **API Docs**: Open `http://localhost:8701/docs` for interactive API documentation
- **Health Check**: `http://localhost:8701/health`
- **Visualizations**: 
  - Static plots: `http://localhost:8701/visualization/plot?plot_type=frequency_monetary`
  - Interactive 2D: `http://localhost:8701/visualization/interactive?plot_type=frequency_monetary`
  - Interactive 3D: `http://localhost:8701/visualization/3d`

## API Endpoints

### Health Check
```bash
GET /health
```

### Run Pipeline
```bash
POST /pipeline/run
Body: {
  "calc_date": "2024-01-15T00:00:00",  # optional, defaults to now
  "window_days": 365,                    # optional, defaults to 365
  "k": 5                                 # optional, defaults to 5
}
```

### Get All Segments
```bash
GET /segments?calc_date=2024-01-15T00:00:00
```

### Get Customers in Segment
```bash
GET /segments/{segment_name}/customers?page=1&page_size=100
```

### Get Customer Details
```bash
GET /customers/{customer_id}
```

### Export Segment as CSV
```bash
GET /export/segments/{segment_name}
```

### Get Cluster Visualization (PNG)
```bash
GET /visualization/plot?plot_type=frequency_monetary
# plot_type options: frequency_monetary, recency_frequency, recency_monetary
```

### Get Interactive Cluster Visualization (HTML)
```bash
GET /visualization/interactive?plot_type=frequency_monetary
# Returns interactive Plotly chart
```

### Get 3D Cluster Visualization
```bash
GET /visualization/3d
# Returns interactive 3D Plotly chart showing all RFM dimensions
```

## Local Development

### Setup Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Setup Database

Make sure PostgreSQL is running and create the database:

```bash
createdb rfm_db
```

Or use Docker:

```bash
docker run -d --name postgres \
  -e POSTGRES_USER=rfm_user \
  -e POSTGRES_PASSWORD=rfm_password \
  -e POSTGRES_DB=rfm_db \
  -p 55432:5432 \
  postgres:15-alpine
```

### Initialize Database

```bash
python -c "from app.db import init_db; init_db()"
```

### Run API Server

```bash
python -m app.main
# or
uvicorn app.api:app --reload
```

### Run Pipeline

```bash
python -m app.pipeline.run_full
```

### Run Tests

```bash
pytest tests/
```

## Project Structure

```
rfm/
├── app/
│   ├── __init__.py
│   ├── main.py              # Application entrypoint
│   ├── api.py               # FastAPI endpoints
│   ├── config.py            # Configuration management
│   ├── db.py                # Database connection
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── rfm.py               # RFM calculation logic
│   ├── clustering.py        # K-means clustering
│   ├── ingestion.py         # CSV data ingestion
│   └── pipeline/
│       ├── __init__.py
│       └── run_full.py      # Pipeline orchestration
├── tests/
│   ├── test_rfm.py
│   ├── test_clustering.py
│   └── test_api.py
├── data/
│   └── input/               # Place CSV files here
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Database Schema

### customers
- `id` (PK)
- `customer_id` (unique, indexed)
- `email`
- `country`
- `created_at`

### orders
- `id` (PK)
- `order_id` (unique, indexed)
- `customer_id` (FK, indexed)
- `order_date` (indexed)
- `order_amount`
- `currency`
- `status`

### rfm_features
- `id` (PK)
- `customer_id` (FK, indexed)
- `calc_date` (indexed)
- `recency_days`
- `frequency`
- `monetary`
- Unique constraint: (`customer_id`, `calc_date`)

### customer_clusters
- `id` (PK)
- `customer_id` (FK, indexed)
- `calc_date` (indexed)
- `cluster_id`
- `segment_name`
- `cluster_score` (JSON)
- Unique constraint: (`customer_id`, `calc_date`)

## RFM Calculation

For each customer, RFM is calculated based on orders in a time window (default: last 365 days):

- **Recency**: Days since most recent completed order
- **Frequency**: Count of completed orders in window
- **Monetary**: Sum of order amounts for completed orders

**Convention for customers with no orders**: 
- `recency_days` = window_days + 1 (very high, indicating no activity)
- `frequency` = 0
- `monetary` = 0

## Clustering & Segmentation

K-means clustering is applied to standardized RFM features. Clusters are automatically mapped to segment names:

- **Champions**: Low recency, high frequency, high monetary
- **Loyal Customers**: Low recency, high frequency
- **Big Spenders**: Low recency, high monetary
- **Potential Loyalists**: Low recency, positive frequency
- **At Risk**: High recency, low frequency
- **Lost**: High recency
- **Hibernating**: Low frequency, low monetary
- **Need Attention**: Default for others

## Production Deployment

### On a Linux Server

1. **Clone repository** on your server
2. **Set environment variables** (use `.env` file or export)
3. **Run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

### Scheduled Pipeline Runs

Use cron or a task scheduler to run the pipeline regularly:

```bash
# Example: Run every Monday at 2 AM
0 2 * * 1 docker-compose exec app python -m app.pipeline.run_full
```

Or trigger via API using a cron job:

```bash
0 2 * * 1 curl -X POST http://localhost:8701/pipeline/run
```

### Backup Database

```bash
docker-compose exec db pg_dump -U rfm_user rfm_db > backup.sql
```

### Restore Database

```bash
docker-compose exec -T db psql -U rfm_user rfm_db < backup.sql
```

## Troubleshooting

### Database Connection Issues

- Check that PostgreSQL is running: `docker-compose ps`
- Verify environment variables match docker-compose.yml
- Check database logs: `docker-compose logs db`
- If you see "database does not exist", recreate the database volume: `docker-compose down -v && docker-compose up --build`
- Or create it manually: `docker-compose exec db psql -U rfm_user -d postgres -c "CREATE DATABASE rfm_db;"`

### Pipeline Errors

- Ensure CSV files are in `data/input/` directory
- Check CSV format matches expected columns
- Review API response for error details

### Port Conflicts

- Default host ports: API `8701`, Postgres `55432`
- Adjust `API_PORT` / `DB_PORT` in `.env` (affects docker-compose host bindings)
- If you run a local Postgres on 5432, keeping `DB_PORT=55432` avoids conflicts

## License

MIT License

## Support

For issues and questions, please open an issue in the repository.

