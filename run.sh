#!/bin/bash

# Chuuk Dictionary OCR Complete Setup and Run Script
# This script handles both setup and running the Flask application

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

print_header() {
    echo -e "${PURPLE}[SETUP]${NC} $1"
}

# Setup function
setup_environment() {
    print_header "🚀 Chuuk Dictionary OCR with AI Translation Setup"
    print_status "Setting up complete environment with Helsinki-NLP and Ollama..."
    
    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed. Please install Python 3.8+ first."
        exit 1
    fi
    
    print_status "Python version: $(python3 --version)"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        print_status "Creating Python virtual environment..."
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_status "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    print_status "Activating virtual environment..."
    source venv/bin/activate
    
    # Upgrade pip
    print_status "Upgrading pip..."
    python -m pip install --upgrade pip
    
    # Install requirements
    print_status "Installing Python packages (this may take several minutes)..."
    pip install -r requirements.txt
    
    # Check if Ollama is installed
    if command -v ollama &> /dev/null; then
        print_success "Ollama is already installed"
        
        # Check if Ollama service is running
        if pgrep -f "ollama" > /dev/null; then
            print_success "Ollama service is running"
        else
            print_status "Starting Ollama service..."
            if command -v brew &> /dev/null; then
                brew services start ollama
            else
                print_warning "Please start Ollama service manually: ollama serve"
            fi
        fi
    else
        print_status "Installing Ollama..."
        if command -v brew &> /dev/null; then
            brew install ollama
            brew services start ollama
            print_success "Ollama installed and started via Homebrew"
        else
            print_warning "Homebrew not found. Please install Ollama manually:"
            print_warning "Visit https://ollama.com/download"
        fi
    fi
    
    # Wait for Ollama to be ready
    print_status "Waiting for Ollama service to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
            print_success "Ollama service is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_warning "Ollama service not responding. You may need to start it manually."
            break
        fi
        sleep 2
    done
    
    # Pull Llama model
    print_status "Pulling Llama 3.2 3B model (this will take several minutes)..."
    if command -v ollama &> /dev/null; then
        ollama pull llama3.2:3b || print_warning "Failed to pull Llama model. You can do this later with: ollama pull llama3.2:3b"
    else
        print_warning "Ollama not available. Please install and run: ollama pull llama3.2:3b"
    fi
    
    # Create necessary directories
    print_status "Creating project directories..."
    mkdir -p uploads
    mkdir -p models
    mkdir -p training_data
    mkdir -p logs
    
    # Create .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        print_status "Creating .env configuration file..."
        cat > .env << EOF
# Flask configuration
FLASK_ENV=development
MAX_CONTENT_LENGTH=16777216
UPLOAD_FOLDER=uploads

# Database configuration
MONGODB_URI=mongodb://localhost:27017/chuuk_dictionary

# Training configuration
TRAINING_DATA_DIR=training_data
MODELS_DIR=models

# JW.org API settings
JWORG_BASE_URL=https://www.jw.org
JWORG_LANGUAGES=chk,en

# Helsinki-NLP model settings
HELSINKI_BASE_MODEL=Helsinki-NLP/opus-mt-mul-en
HELSINKI_REVERSE_MODEL=Helsinki-NLP/opus-mt-en-mul
EOF
        print_success ".env file created"
    else
        print_status ".env file already exists"
    fi
    
    # Test Helsinki-NLP models
    print_status "Testing Helsinki-NLP model availability..."
    python3 << 'PYTHON_EOF'
try:
    from transformers import AutoTokenizer
    print("✅ Helsinki-NLP libraries available")
    tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-mul-en")
    print("✅ Helsinki-NLP models accessible")
except Exception as e:
    print(f"💡 Helsinki-NLP models will download when needed: {e}")
PYTHON_EOF

    print_success "Setup completed successfully!"
}

# Clear database function
clear_database() {
    print_status "Clearing MongoDB database..."
    # Only try to clear if pymongo is available
    if python -c "import pymongo" 2>/dev/null; then
        python3 << 'PYTHON_EOF'
import pymongo
try:
    client = pymongo.MongoClient('mongodb://localhost:27017/')
    client.drop_database('chuuk_dictionary')
    print("✅ Database cleared successfully")
except Exception as e:
    print(f"⚠️ Failed to clear database: {e}")
PYTHON_EOF
    else
        print_status "Skipping database clear - pymongo not yet installed"
    fi
}

echo "🚀 Starting Chuuk Dictionary OCR Application..."
echo "==============================================="

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    print_error "app.py not found. Please run this script from the project root directory."
    exit 1
fi

# Run setup if virtual environment doesn't exist
if [ ! -d "venv" ]; then
    print_header "🛠️ First time setup detected - running full setup..."
    setup_environment
    # Clear database after setup
    clear_database
else
    # Clear database on subsequent runs
    clear_database
fi

# Activate virtual environment
print_status "Activating Python virtual environment..."
source venv/bin/activate

# Load environment variables
print_status "Loading environment variables..."
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check MongoDB connection
print_status "Checking MongoDB connection..."
if ! python -c "
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
        if python -c "
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
            exit 1
        fi
    else
        print_error "MongoDB is not running and Homebrew is not available to start it."
        exit 1
    fi
else
    print_success "MongoDB is running"
fi

# Test Helsinki-NLP integration
print_status "Testing Helsinki-NLP translator integration..."
python -c "
try:
    from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator
    translator = HelsinkiChuukeseTranslator()
    print('✅ Helsinki-NLP translator ready')
except Exception as e:
    print(f'⚠️ Helsinki-NLP translator warning: {e}')
    print('💡 Models will download when first used')
"

# Create uploads directory if it doesn't exist
mkdir -p uploads

# Find available port
PORT=5002
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
echo "   • OCR processing with Tesseract"
echo "   • Helsinki-NLP translation models for Chuukese"
echo "   • Ollama LLM for conversational AI"
echo "   • Automatic word pair extraction and indexing"
echo "   • MongoDB-powered search with citations"
echo ""
echo "⏹️  Press Ctrl+C to stop the server"
echo ""

# Trap Ctrl+C to provide clean shutdown message
trap 'echo -e "\n🛑 Shutting down application..."; exit 0' INT

# Start the Flask application
python -c "
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