#!/bin/bash

# Azure Cosmos DB Setup for Development
# This script helps you set up a free Azure Cosmos DB instance for development

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

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
    echo -e "${PURPLE}================================================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================================================${NC}"
}

# Check if Azure CLI is installed
check_azure_cli() {
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI not found."
        print_status "Install with: brew install azure-cli"
        print_status "Or download from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        return 1
    fi
    
    # Check if logged in
    if ! az account show &> /dev/null; then
        print_warning "Not logged into Azure CLI."
        print_status "Please run: az login"
        return 1
    fi
    
    print_success "Azure CLI is ready"
    return 0
}

# Create Cosmos DB account
create_cosmos_db() {
    local resource_group="$1"
    local account_name="$2"
    local location="${3:-eastus}"
    
    print_status "Creating Cosmos DB account: $account_name"
    
    # Create resource group if it doesn't exist
    if ! az group show --name "$resource_group" &> /dev/null; then
        print_status "Creating resource group: $resource_group"
        az group create --name "$resource_group" --location "$location"
    fi
    
    # Create Cosmos DB account with MongoDB API
    print_status "Creating Cosmos DB account (this may take a few minutes)..."
    az cosmosdb create \
        --name "$account_name" \
        --resource-group "$resource_group" \
        --kind MongoDB \
        --locations regionName="$location" \
        --enable-free-tier true \
        --default-consistency-level "Session"
    
    print_success "Cosmos DB account created successfully!"
}

# Get connection details
get_connection_details() {
    local resource_group="$1"
    local account_name="$2"
    
    print_status "Retrieving connection details..."
    
    # Get connection string
    local connection_string=$(az cosmosdb keys list \
        --name "$account_name" \
        --resource-group "$resource_group" \
        --type connection-strings \
        --query "connectionStrings[0].connectionString" \
        --output tsv)
    
    # Get endpoint and key separately for Cosmos DB SQL API
    local endpoint=$(az cosmosdb show \
        --name "$account_name" \
        --resource-group "$resource_group" \
        --query "documentEndpoint" \
        --output tsv)
    
    local primary_key=$(az cosmosdb keys list \
        --name "$account_name" \
        --resource-group "$resource_group" \
        --query "primaryMasterKey" \
        --output tsv)
    
    # Update .env file
    print_status "Updating .env file with connection details..."
    
    # Create backup of .env
    cp .env .env.backup
    
    # Update .env file
    cat > .env << EOF
# Database Configuration - Using Azure Cosmos DB
DB_TYPE=cosmos

# Azure Cosmos DB Configuration
COSMOS_DB_URI=$endpoint
COSMOS_DB_KEY=$primary_key

# MongoDB API connection (alternative)
MONGODB_URI=$connection_string

# Flask configuration
FLASK_ENV=development
MAX_CONTENT_LENGTH=16777216
UPLOAD_FOLDER=uploads

# Note: Google Cloud credentials are optional for basic functionality
# GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
EOF

    print_success "Environment configuration updated!"
    echo -e "\n${CYAN}Connection Details:${NC}"
    echo -e "  ${CYAN}Endpoint:${NC} $endpoint"
    echo -e "  ${CYAN}Database:${NC} $account_name"
    echo -e "  ${CYAN}Resource Group:${NC} $resource_group"
    echo -e "\n${GREEN}✅ Your .env file has been updated with the connection details${NC}"
}

# Main setup function
main() {
    print_header "Azure Cosmos DB Setup for Chuuk Dictionary OCR"
    
    echo "This script will help you set up a free Azure Cosmos DB instance for development."
    echo ""
    
    # Get user input
    read -p "Enter resource group name (or press Enter for 'chuuk-dictionary-rg'): " resource_group
    resource_group=${resource_group:-"chuuk-dictionary-rg"}
    
    read -p "Enter Cosmos DB account name (must be globally unique): " account_name
    if [[ -z "$account_name" ]]; then
        print_error "Account name is required"
        exit 1
    fi
    
    read -p "Enter Azure region (or press Enter for 'eastus'): " location
    location=${location:-"eastus"}
    
    echo ""
    print_status "Configuration:"
    echo -e "  ${CYAN}Resource Group:${NC} $resource_group"
    echo -e "  ${CYAN}Account Name:${NC} $account_name"
    echo -e "  ${CYAN}Location:${NC} $location"
    echo ""
    
    read -p "Continue with this configuration? (y/N): " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Setup cancelled."
        exit 0
    fi
    
    # Check prerequisites
    if ! check_azure_cli; then
        exit 1
    fi
    
    # Create Cosmos DB
    if create_cosmos_db "$resource_group" "$account_name" "$location"; then
        get_connection_details "$resource_group" "$account_name"
        
        echo ""
        print_success "🚀 Azure Cosmos DB setup complete!"
        print_status "You can now run: ./run.sh start"
        print_status "Monitor your usage at: https://portal.azure.com"
        
        print_warning "💰 Cost Information:"
        print_status "• Free tier includes 1000 RU/s and 25GB storage"
        print_status "• Monitor usage to avoid unexpected charges"
        print_status "• Delete resources when not needed: az group delete --name $resource_group"
        
    else
        print_error "Failed to create Cosmos DB account"
        exit 1
    fi
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi