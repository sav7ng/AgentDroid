# Multi-stage build for smaller final image
FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       g++ \
       libc6-dev \
       libffi-dev \
       libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Final stage
FROM python:3.13-slim AS runtime

# Set the working directory in the container
WORKDIR /app

# Install only runtime dependencies for OpenCV and health check
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libgl1 \
       libglib2.0-0 \
       libsm6 \
       libxext6 \
       libxrender1 \
       libgomp1 \
       curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application files (order optimized for caching)
# Copy less frequently changed files first
COPY core/ ./core/
COPY middleware/ ./middleware/
COPY static/ ./static/
COPY env/ ./env/
COPY utils/ ./utils/
COPY agents/ ./agents/
COPY agent_core.py .
COPY main.py .

# Create output directory
RUN mkdir -p agent_outputs

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run main.py when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
