#!/bin/bash

# Chuuk Dictionary OCR Complete Startup Script
# Starts all services: MongoDB, React frontend, Flask backend
# Provides real-time status monitoring

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Service ports and paths
COSMOS_PORT=8081
FLASK_PORT=5002
REACT_PORT=5173
PROJECT_DIR="$(pwd)"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/.venv"

# Database type - using Cosmos DB only
DB_TYPE="cosmos"

# PID files for background processes
COSMOS_PID_FILE="/tmp/chuuk_cosmos.pid"
FLASK_PID_FILE="/tmp/chuuk_flask.pid"
REACT_PID_FILE="/tmp/chuuk_react.pid"

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

print_service() {
    echo -e "${CYAN}[SERVICE]${NC} $1"
}

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to wait for service to start
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "Waiting for $service_name to start on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if check_port $port; then
            print_success "$service_name is ready on port $port"
            return 0
        fi
        
        sleep 1
        ((attempt++))
    done
    
    print_error "$service_name failed to start within 30 seconds"
    return 1
}

# Function to stop all services
stop_services() {
    print_status "Stopping all services..."
    
    # Stop React dev server
    if [ -f "$REACT_PID_FILE" ]; then
        local react_pid=$(cat "$REACT_PID_FILE")
        if ps -p $react_pid > /dev/null 2>&1; then
            kill $react_pid 2>/dev/null || true
            print_status "Stopped React dev server"
        fi
        rm -f "$REACT_PID_FILE"
    fi
    
    # Stop Flask server
    if [ -f "$FLASK_PID_FILE" ]; then
        local flask_pid=$(cat "$FLASK_PID_FILE")
        if ps -p $flask_pid > /dev/null 2>&1; then
            kill $flask_pid 2>/dev/null || true
            print_status "Stopped Flask server"
        fi
        rm -f "$FLASK_PID_FILE"
    fi
    
    # Stop Cosmos DB Emulator (Docker container)
    if [ -f "$COSMOS_PID_FILE" ]; then
        local container_id=$(cat "$COSMOS_PID_FILE")
        if docker ps -q -f id="$container_id" | grep -q "$container_id"; then
            docker stop "$container_id" > /dev/null 2>&1 || true
            docker rm "$container_id" > /dev/null 2>&1 || true
            print_status "Stopped Cosmos DB Emulator"
        fi
        rm -f "$COSMOS_PID_FILE"
    fi
    
    # Also stop by name if PID file method fails
    if docker ps | grep -q "azure-cosmos-emulator"; then
        docker stop azure-cosmos-emulator > /dev/null 2>&1 || true
        docker rm azure-cosmos-emulator > /dev/null 2>&1 || true
    fi
    
    # Kill any remaining processes
    pkill -f "flask" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    
    print_success "All services stopped"
}

# Function to check service status
check_service_status() {
    echo -e "\n${PURPLE}=== SERVICE STATUS ===${NC}"
    
    # Azure Cosmos DB status
    local cosmos_uri=$(grep COSMOS_DB_URI .env | cut -d'=' -f2)
    if [[ "$cosmos_uri" == *"azure.com"* ]]; then
        print_success "Azure Cosmos DB: Connected to $cosmos_uri"
    else
        print_error "Azure Cosmos DB: Not configured"
    fi
    
    # Flask status
    if check_port $FLASK_PORT; then
        print_success "Flask API: Running on port $FLASK_PORT"
        echo -e "  ${CYAN}URL:${NC} http://localhost:$FLASK_PORT"
    else
        print_error "Flask API: Not running"
    fi
    
    # React status
    if check_port $REACT_PORT; then
        print_success "React App: Running on port $REACT_PORT"
        echo -e "  ${CYAN}URL:${NC} http://localhost:$REACT_PORT"
    else
        print_error "React App: Not running"
    fi
    
    echo ""
}

# Function to connect to Azure Cosmos DB
start_database() {
    print_service "Using Azure Cosmos DB..."
    
    # Check if we can connect to Azure Cosmos DB
    local cosmos_uri=$(grep COSMOS_DB_URI .env | cut -d'=' -f2)
    if [[ "$cosmos_uri" == *"azure.com"* ]]; then
        print_success "Azure Cosmos DB configured: $cosmos_uri"
        print_status "Database: chuuk-dictionary-cosmos"
        print_status "Resource Group: rg-chuuk-beta-eastus2"
        print_status "Region: East US 2"
        return 0
    else
        print_error "Azure Cosmos DB not configured in .env file"
        return 1
    fi
}

# Function to start Cosmos DB Emulator
start_cosmos_db() {
    print_service "Starting Cosmos DB Emulator..."
    
    if check_port $COSMOS_PORT; then
        print_warning "Cosmos DB Emulator already running on port $COSMOS_PORT"
        return 0
    fi
    
    # Check if Docker is available for Cosmos DB Emulator
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Cosmos DB Emulator requires Docker on macOS/Linux."
        print_status "Install Docker Desktop: https://www.docker.com/products/docker-desktop"
        return 1
    fi
    
    # Check if Cosmos DB container is already running
    if docker ps | grep -q "azure-cosmos-emulator"; then
        print_warning "Cosmos DB Emulator container already running"
        return 0
    fi
    
    print_warning "⚠️  Apple Silicon (ARM64) Detected - Cosmos DB Emulator Compatibility Issue"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    print_status "The official Cosmos DB Emulator has stability issues on ARM64 Macs."
    print_status "For the best development experience, consider these options:"
    echo ""
    print_info "🚀 RECOMMENDED: Use Azure Cosmos DB Free Tier"
    print_status "   • Create a free Cosmos DB account in Azure"
    print_status "   • 1000 RU/s and 25GB storage - completely free"
    print_status "   • Same API as production, no compatibility issues"
    print_status "   • Guide: https://docs.microsoft.com/azure/cosmos-db/free-tier"
    echo ""
    print_info "🔧 ALTERNATIVE: Use MongoDB for local development"
    print_status "   • Install: brew install mongodb-community"
    print_status "   • Same document database concepts"
    print_status "   • Easy migration path to Cosmos DB later"
    echo ""
    print_info "💻 FOR TESTING: Try Docker with Rosetta 2 (may be unstable)"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    
    read -p "Would you like to try Docker anyway? (y/N): " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Skipping Cosmos DB Emulator startup."
        print_info "You can manually set COSMOS_DB_URI in .env to use Azure Cosmos DB"
        return 1
    fi
    
    # Start Cosmos DB Emulator using Docker
    print_status "Starting Cosmos DB Emulator with Docker (this may take a moment to download/start)..."
    
    # Try with platform flag for ARM64, without for x86
    local docker_cmd="docker run -d \
        --name azure-cosmos-emulator \
        $docker_platform \
        -p 8081:8081 -p 10251:10251 -p 10252:10252 -p 10253:10253 -p 10254:10254 \
        -e AZURE_COSMOS_EMULATOR_PARTITION_COUNT=10 \
        -e AZURE_COSMOS_EMULATOR_ENABLE_DATA_PERSISTENCE=true \
        $cosmos_image"
    
    if eval "$docker_cmd" > /tmp/cosmos.log 2>&1; then
        # Get container ID for PID file
        local container_id=$(docker ps -q -f name=azure-cosmos-emulator)
        echo "$container_id" > "$COSMOS_PID_FILE"
    else
        print_error "Failed to start Cosmos DB Emulator with Docker"
        print_status "Check logs with: docker logs azure-cosmos-emulator"
        if [[ "$arch" == "arm64" ]]; then
            print_warning "ARM64 compatibility issue detected. Consider these alternatives:"
            print_status "1. Enable Rosetta 2 emulation in Docker Desktop settings"
            print_status "2. Use a cloud Cosmos DB instance for development"
            print_status "3. Use MongoDB as a local alternative"
        fi
        return 1
    fi
    
    # Cosmos DB takes longer to start
    print_status "Waiting for Cosmos DB Emulator to initialize..."
    local max_attempts=60
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if check_port $COSMOS_PORT; then
            print_success "Cosmos DB Emulator is ready on port $COSMOS_PORT"
            return 0
        fi
        
        sleep 2
        ((attempt++))
    done
    
    print_error "Cosmos DB Emulator failed to start within 2 minutes"
    return 1
}

# Function to start Flask backend
start_flask() {
    print_service "Starting Flask backend..."
    
    if check_port $FLASK_PORT; then
        print_warning "Flask already running on port $FLASK_PORT"
        return 0
    fi
    
    # Check if virtual environment exists
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found at $VENV_DIR"
        print_status "Please run setup first or create virtual environment"
        return 1
    fi
    
    # Set Cosmos DB environment variables
    export DB_TYPE="cosmos"
    export COSMOS_DB_URI="https://localhost:$COSMOS_PORT"
    export COSMOS_DB_KEY="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
    
    # Start Flask in background
    cd "$PROJECT_DIR"
    
    # Start Flask in background with proper environment
    "$VENV_DIR/bin/python" app.py > /tmp/flask.log 2>&1 &
    local flask_pid=$!
    echo $flask_pid > "$FLASK_PID_FILE"
    
    wait_for_service $FLASK_PORT "Flask"
}

# Function to start React frontend
start_react() {
    print_service "Starting React frontend..."
    
    if check_port $REACT_PORT; then
        print_warning "React already running on port $REACT_PORT"
        return 0
    fi
    
    # Check if frontend directory exists
    if [ ! -d "$FRONTEND_DIR" ]; then
        print_error "Frontend directory not found at $FRONTEND_DIR"
        return 1
    fi
    
    # Check if node_modules exists
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        print_error "Node modules not found. Installing dependencies..."
        cd "$FRONTEND_DIR"
        npm install
    fi
    
    # Build React app first
    cd "$FRONTEND_DIR"
    print_status "Building React application..."
    npm run build
    
    # Start React dev server in background
    npm run dev > /tmp/react.log 2>&1 &
    local react_pid=$!
    echo $react_pid > "$REACT_PID_FILE"
    
    wait_for_service $REACT_PORT "React"
}

# Function to show logs
show_logs() {
    echo -e "\n${PURPLE}=== RECENT LOGS ===${NC}"
    
    # Cosmos DB logs
    if [ -f "/tmp/cosmos.log" ]; then
        echo -e "\n${CYAN}Cosmos DB Emulator logs:${NC}"
        tail -5 /tmp/cosmos.log 2>/dev/null || echo "No Cosmos DB logs"
    fi
    
    if [ -f "/tmp/flask.log" ]; then
        echo -e "\n${CYAN}Flask logs:${NC}"
        tail -5 /tmp/flask.log 2>/dev/null || echo "No Flask logs"
    fi
    
    if [ -f "/tmp/react.log" ]; then
        echo -e "\n${CYAN}React logs:${NC}"
        tail -5 /tmp/react.log 2>/dev/null || echo "No React logs"
    fi
}

# Main execution
main() {
    echo -e "${PURPLE}================================================================${NC}"
    echo -e "${PURPLE}           Chuuk Dictionary OCR - Service Manager               ${NC}"
    echo -e "${PURPLE}================================================================${NC}"
    
    # Handle command line arguments
    case "${1:-start}" in
        "start")
            print_status "Starting all services..."
            
            # Start services in order
            start_database || exit 1
            start_flask || exit 1
            start_react || exit 1
            
            check_service_status
            show_logs
            
            echo -e "\n${GREEN}🚀 All services are running!${NC}"
            echo -e "${CYAN}Main Application:${NC} http://localhost:$REACT_PORT"
            echo -e "${CYAN}API Backend:${NC} http://localhost:$FLASK_PORT"
            echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}"
            
            # Keep script running and monitor services
            trap stop_services EXIT INT TERM
            
            while true; do
                sleep 30
                if ! check_port $FLASK_PORT || ! check_port $REACT_PORT; then
                    print_error "One or more services stopped unexpectedly"
                    check_service_status
                    break
                fi
            done
            ;;
            
        "stop")
            stop_services
            ;;
            
        "status")
            check_service_status
            ;;
            
        "logs")
            show_logs
            ;;
            
        "restart")
            stop_services
            sleep 2
            main start
            ;;
            
        *)
            echo "Usage: $0 [start|stop|status|logs|restart]"
            echo "  start   - Start all services (default)"
            echo "  stop    - Stop all services"
            echo "  status  - Show service status"
            echo "  logs    - Show recent logs"
            echo "  restart - Restart all services"
            echo ""
            echo "Database:"
            echo "  Uses Azure Cosmos DB Emulator (localhost:8081)"
            echo "  Data Explorer: https://localhost:8081/_explorer/"
            echo ""
            echo "Example:"
            echo "  ./run.sh start     # Start all services with Cosmos DB"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"