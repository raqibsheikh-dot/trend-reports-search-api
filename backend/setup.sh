#!/bin/bash

# Trend Reports API - Setup Script
# This script automates the initial setup process

set -e  # Exit on error

echo "================================================"
echo "Trend Reports API - Setup Script"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_success "Found Python $PYTHON_VERSION"

# Check for Tesseract
echo ""
echo "Checking for Tesseract OCR..."
if command -v tesseract &> /dev/null; then
    TESSERACT_VERSION=$(tesseract --version | head -n1)
    print_success "Found $TESSERACT_VERSION"
else
    print_warning "Tesseract OCR not found"
    echo "  Install with:"
    echo "    - Mac: brew install tesseract"
    echo "    - Linux: sudo apt-get install tesseract-ocr"
    echo "    - Windows: https://github.com/UB-Mannheim/tesseract/wiki"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for Poppler
echo ""
echo "Checking for Poppler (pdftoimage)..."
if command -v pdftoimage &> /dev/null || command -v pdftoppm &> /dev/null; then
    print_success "Found Poppler tools"
else
    print_warning "Poppler not found"
    echo "  Install with:"
    echo "    - Mac: brew install poppler"
    echo "    - Linux: sudo apt-get install poppler-utils"
    echo "    - Windows: https://github.com/oschwartz10612/poppler-windows/releases"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists. Skipping creation."
else
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
print_success "Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip --quiet
print_success "pip upgraded"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
echo "(This may take 5-10 minutes for first-time installation)"
pip install -r requirements.txt --quiet
print_success "Dependencies installed"

# Create .env file if it doesn't exist
echo ""
echo "Setting up environment variables..."
if [ -f ".env" ]; then
    print_warning ".env file already exists. Skipping creation."
else
    cp .env.example .env

    # Generate secure API key
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    # Replace API_KEY in .env
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/API_KEY=.*/API_KEY=$API_KEY/" .env
    else
        # Linux
        sed -i "s/API_KEY=.*/API_KEY=$API_KEY/" .env
    fi

    print_success ".env file created with secure API key"
    echo "  Your API Key: $API_KEY"
    echo "  (Saved in .env file)"
fi

# Create reports folder if it doesn't exist
echo ""
REPORTS_FOLDER=$(grep REPORTS_FOLDER .env | cut -d'=' -f2)
echo "Checking for reports folder: $REPORTS_FOLDER"
if [ -d "$REPORTS_FOLDER" ]; then
    PDF_COUNT=$(find "$REPORTS_FOLDER" -name "*.pdf" | wc -l | xargs)
    print_success "Found reports folder with $PDF_COUNT PDF files"
else
    mkdir -p "$REPORTS_FOLDER"
    print_warning "Created reports folder: $REPORTS_FOLDER"
    echo "  Please add your PDF files to this folder before running process_pdfs.py"
fi

# Setup complete
echo ""
echo "================================================"
print_success "Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Add your PDF files to: $REPORTS_FOLDER"
echo ""
echo "2. Process PDFs (one-time, takes 1-2 hours):"
echo "   python process_pdfs.py"
echo ""
echo "3. Start the API server:"
echo "   uvicorn main:app --reload"
echo ""
echo "4. Test the API:"
echo "   curl http://localhost:8000/health"
echo ""
echo "5. Read the deployment guide:"
echo "   cat DEPLOYMENT_GUIDE.md"
echo ""
echo "================================================"
