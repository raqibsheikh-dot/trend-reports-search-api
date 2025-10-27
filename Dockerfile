# Multi-stage build for Trend Intelligence Platform Backend
# This Dockerfile is at the root level for Render.com deployment

FROM python:3.10-slim as builder

# Install system dependencies for PDF processing and OCR
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements from backend directory
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.10-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code from backend directory
COPY --chown=appuser:appuser backend/*.py .
COPY --chown=appuser:appuser backend/routers ./routers
COPY --chown=appuser:appuser backend/services ./services

# Create app directory and set permissions
# Note: Render will mount disk at /var/data automatically
RUN mkdir -p /app && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Set environment variables to reduce memory usage
ENV PYTORCH_ENABLE_MPS_FALLBACK=1
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1

# Run the application
# Use PORT env var from Render, default to 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
