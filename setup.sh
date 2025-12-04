#!/bin/bash
# Quick setup script for RFM Segmentation MVP

set -e

echo "Setting up RFM Segmentation MVP..."

# Create data directory if it doesn't exist
mkdir -p data/input

# Copy example CSV files if they don't exist
if [ ! -f data/input/customers.csv ] && [ -f data/input/customers.csv.example ]; then
    cp data/input/customers.csv.example data/input/customers.csv
    echo "Created data/input/customers.csv from example"
fi

if [ ! -f data/input/orders.csv ] && [ -f data/input/orders.csv.example ]; then
    cp data/input/orders.csv.example data/input/orders.csv
    echo "Created data/input/orders.csv from example"
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo ".env file not found. Creating from defaults..."
    cat > .env << 'EOF'
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
API_HOST=0.0.0.0
API_PORT=8701
EOF
    echo "Created .env file with default values"
    echo "Please review and update .env with your settings"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Review and update .env file if needed"
echo "2. Place your CSV files in data/input/ directory"
echo "3. Run: docker-compose up --build"
echo "4. Access API at http://localhost:8701"
echo "5. View dashboard at http://localhost:8701/dashboard"
