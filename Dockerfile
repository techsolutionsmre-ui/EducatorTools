# Stage 1: Build the React Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Create Python Backend Environment
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies (curl for health checks, libgl1-mesa-glx/libglib2.0-0 for PyMuPDF rendering fallback if needed)
RUN apt-get update && apt-get install -y \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy React build artifacts to frontend/dist (where main.py expects it)
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy python backend code to backend/
COPY backend/ ./backend

# Create data volume folder for SQLite persistence
RUN mkdir -p /app/backend/data

EXPOSE 8000

# Set environment variable to run python from backend dir
ENV PYTHONPATH=/app/backend

# Run FastAPI via Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
