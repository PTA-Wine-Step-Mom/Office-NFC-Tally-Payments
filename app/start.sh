#!/bin/sh
# Startup script for Docker container

# Initialize database if it doesn't exist
python -c "from database import init_db; init_db()"

# Start Flask application
exec python app.py
