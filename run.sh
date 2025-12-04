#!/bin/bash

# Chuuk Dictionary OCR Run Script
# This script starts the Flask application with proper environment setup

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🚀 Starting Chuuk Dictionary OCR Application..."
echo "==============================================="

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    print_error "app.py not found. Please run this script from the project root directory."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    print_error "Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found. Please run ./setup.sh first."
    exit 1
fi

# Activate virtual environment
print_status "Activating Python virtual environment..."
source .venv/bin/activate

# Load environment variables
print_status "Loading environment variables..."
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check MongoDB connection
print_status "Checking MongoDB connection..."
if ! .venv/bin/python -c "
import pymongo
try:
    client = pymongo.MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=3000)
    client.admin.command('ping')
except Exception as e:
    print(f'MongoDB connection failed: {e}')
    exit(1)
" > /dev/null 2>&1; then
    print_warning "MongoDB connection failed. Attempting to start MongoDB..."
    
    # Try to start MongoDB service
    if command -v brew &> /dev/null; then
        brew services start mongodb/brew/mongodb-community
        sleep 3
        
        # Test again
        if .venv/bin/python -c "
import pymongo
try:
    client = pymongo.MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=3000)
    client.admin.command('ping')
except:
    exit(1)
" > /dev/null 2>&1; then
            print_success "MongoDB started successfully"
        else
            print_error "Failed to start MongoDB. Please check your installation."
            print_error "Try running: brew services restart mongodb/brew/mongodb-community"
            exit 1
        fi
    else
        print_error "MongoDB is not running and Homebrew is not available to start it."
        exit 1
    fi
else
    print_success "MongoDB is running"
fi

# Create uploads directory if it doesn't exist
mkdir -p uploads

# Check for Google Cloud credentials
if [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    print_success "Google Cloud Vision API credentials found"
else
    print_warning "Google Cloud Vision API credentials not found. Using Tesseract OCR only."
fi

# Find available port
PORT=5001
while lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; do
    print_warning "Port $PORT is in use, trying $((PORT + 1))"
    PORT=$((PORT + 1))
done

print_success "Using port $PORT"

# Set Flask environment
export FLASK_ENV=development
export FLASK_DEBUG=1

print_status "Starting Flask development server..."
echo ""
echo "🌐 Application will be available at:"
echo "   http://127.0.0.1:$PORT"
echo "   http://localhost:$PORT"
echo ""
echo "📖 Features available:"
echo "   • Upload dictionary documents (PDF, images)"
echo "   • OCR processing with Tesseract and Google Vision"
echo "   • Automatic word pair extraction and indexing"
echo "   • Search local dictionary and JW.org"
echo "   • MongoDB-powered search with citations"
echo ""
echo "⏹️  Press Ctrl+C to stop the server"
echo ""

# Trap Ctrl+C to provide clean shutdown message
trap 'echo -e "\n🛑 Shutting down application..."; exit 0' INT

# Start the Flask application
.venv/bin/python -c "
import os
from app import app

# Override port from environment or use detected port
port = int(os.environ.get('PORT', $PORT))

print('Connected to MongoDB successfully' if app else '')
print(f'🚀 Starting server on port {port}...')

try:
    app.run(
        debug=True,
        host='0.0.0.0',
        port=port,
        threaded=True,
        use_reloader=True
    )
except KeyboardInterrupt:
    print('\n🛑 Application stopped by user')
except Exception as e:
    print(f'❌ Error starting application: {e}')
    exit(1)
"