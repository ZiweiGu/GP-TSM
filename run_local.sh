#!/bin/bash
# Script to run GP-TSM Flask app locally

cd "$(dirname "$0")"
source venv/bin/activate
echo "Starting GP-TSM Flask app..."
echo "The app will be available at: http://localhost:5001"
echo "(You can change the port by setting PORT environment variable)"
echo "Press Ctrl+C to stop the server"
echo ""
python3 app.py

