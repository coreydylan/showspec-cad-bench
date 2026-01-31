FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    python3.11 \
    python3-pip \
    python3.11-venv \
    git \
    wget \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install FreeCAD from Ubuntu repos (older but stable version)
RUN apt-get update \
    && apt-get install -y freecad \
    && rm -rf /var/lib/apt/lists/*

# Install Woodworking Workbench
RUN git clone https://github.com/dprojects/Woodworking.git \
    /root/.local/share/FreeCAD/Mod/Woodworking

# Set up Python environment
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ ./api/
COPY templates/ ./templates/
COPY materials/ ./materials/

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
