#!/bin/bash

# Chuuk Dictionary OCR Setup Script
# This script installs all dependencies and sets up the environment

set -e  # Exit on any error

echo "🚀 Setting up Chuuk Dictionary OCR Application..."
echo "================================================="

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

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This setup script is designed for macOS. Please install dependencies manually on other systems."
    exit 1
fi

# 1. Check for Homebrew
print_status "Checking for Homebrew..."
if ! command -v brew &> /dev/null; then
    print_warning "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    print_success "Homebrew is installed"
fi

# 2. Install system dependencies
print_status "Installing system dependencies..."

# Install Python 3.11+ if not available
if ! command -v python3 &> /dev/null || ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    print_warning "Installing Python..."
    brew install python@3.11
fi

# Install Tesseract OCR
print_status "Installing Tesseract OCR..."
brew install tesseract

# Install additional language packs for Tesseract
print_status "Installing Tesseract language packs..."
brew install tesseract-lang || print_warning "Some language packs may not be available"

# Install Poppler for PDF processing
print_status "Installing Poppler for PDF processing..."
brew install poppler

# Install MongoDB
print_status "Installing MongoDB..."
brew tap mongodb/brew
brew install mongodb-community

# 3. Create Python virtual environment
print_status "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment already exists"
fi

# Activate virtual environment
source .venv/bin/python3 || source .venv/bin/activate

# 4. Upgrade pip
print_status "Upgrading pip..."
.venv/bin/python -m pip install --upgrade pip

# 5. Install Python dependencies
print_status "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    .venv/bin/pip install -r requirements.txt
    print_success "Python dependencies installed"
else
    print_error "requirements.txt not found!"
    exit 1
fi

# 6. Create uploads directory
print_status "Creating uploads directory..."
mkdir -p uploads
print_success "Uploads directory created"

# 7. Check for .env file
print_status "Checking environment configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_warning "Created .env from .env.example. Please review and update as needed."
    else
        print_warning "No .env file found. Creating basic configuration..."
        cat > .env << EOF
# Google Cloud Vision API credentials path
GOOGLE_APPLICATION_CREDENTIALS=ai-llms-vision-c5adc62aac84.json

# Flask configuration
FLASK_SECRET_KEY=dev-secret-key-change-in-production
FLASK_ENV=development

# Upload configuration
MAX_CONTENT_LENGTH=1073741824
UPLOAD_FOLDER=uploads

# MongoDB configuration
MONGODB_URI=mongodb://localhost:27017/
EOF
    fi
    print_success "Environment configuration ready"
else
    print_success ".env file already exists"
fi

# 8. Start MongoDB service
print_status "Starting MongoDB service..."
brew services start mongodb/brew/mongodb-community
sleep 3  # Give MongoDB time to start

print_success "MongoDB service started"

# 9. Test installations
echo ""
echo "🧪 Running installation tests..."
echo "================================="

# Test Python
print_status "Testing Python installation..."
if .venv/bin/python -c "import sys; print(f'Python {sys.version}')"; then
    print_success "Python is working"
else
    print_error "Python test failed"
    exit 1
fi

# Test essential Python packages
print_status "Testing Python packages..."
required_packages=("flask" "pytesseract" "pymongo" "pdf2image" "google.cloud.vision" "PIL")
for package in "${required_packages[@]}"; do
    if .venv/bin/python -c "import $package" 2>/dev/null; then
        print_success "✓ $package"
    else
        print_error "✗ $package failed to import"
    fi
done

# Test Tesseract
print_status "Testing Tesseract OCR..."
if command -v tesseract &> /dev/null; then
    tesseract_version=$(tesseract --version 2>&1 | head -n1)
    print_success "Tesseract: $tesseract_version"
else
    print_error "Tesseract not found"
    exit 1
fi

# Test MongoDB connection
print_status "Testing MongoDB connection..."
if .venv/bin/python -c "
import pymongo
try:
    client = pymongo.MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print('MongoDB connection successful')
except Exception as e:
    print(f'MongoDB connection failed: {e}')
    exit(1)
" > /dev/null 2>&1; then
    print_success "MongoDB connection successful"
else
    print_error "MongoDB connection failed. Check if MongoDB is running."
fi

# Test Flask app imports
print_status "Testing Flask application..."
if .venv/bin/python -c "
import sys
sys.path.append('.')
try:
    from app import app
    from dictionary_db import DictionaryDB
    from ocr_processor import OCRProcessor
    print('Flask app imports successful')
except Exception as e:
    print(f'Flask app test failed: {e}')
    exit(1)
" > /dev/null 2>&1; then
    print_success "Flask application ready"
else
    print_error "Flask application test failed"
fi

# Test Google Cloud Vision (if credentials exist)
if [ -f "ai-llms-vision-c5adc62aac84.json" ]; then
    print_status "Testing Google Cloud Vision API..."
    export GOOGLE_APPLICATION_CREDENTIALS="ai-llms-vision-c5adc62aac84.json"
    if .venv/bin/python -c "
from google.cloud import vision
try:
    client = vision.ImageAnnotatorClient()
    print('Google Vision client created successfully')
except Exception as e:
    print(f'Google Vision test failed: {e}')
" > /dev/null 2>&1; then
        print_success "Google Cloud Vision API ready"
    else
        print_warning "Google Cloud Vision API test failed (credentials may be invalid)"
    fi
else
    print_warning "Google Cloud Vision credentials not found. OCR will use Tesseract only."
fi

echo ""
echo "🎉 Setup Complete!"
echo "=================="
print_success "All components have been installed and tested successfully!"
echo ""
echo "📋 What was installed:"
echo "  ✓ Python virtual environment (.venv)"
echo "  ✓ Python dependencies (Flask, OCR libraries, MongoDB driver)"
echo "  ✓ Tesseract OCR with language packs"
echo "  ✓ Poppler PDF processing"
echo "  ✓ MongoDB database server"
echo "  ✓ Environment configuration (.env)"
echo ""
echo "🚀 To run the application:"
echo "   ./run.sh"
echo ""
echo "🌐 The app will be available at: http://127.0.0.1:5001"
echo ""
print_warning "Remember to review your .env file and update any configuration as needed!"