# Dockerfile for backend (api/worker)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed (uncomment if you need build tools)
# RUN apt-get update && apt-get install -y build-essential

# Copy requirements file first for caching
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for API (FastAPI/Uvicorn)
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]