FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONPATH /app
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
# Note: Since the context might be the project root, we should be careful.
# Usually, Dockerfiles are at the root or in their respective subdirectories.
# If I place this inside 'backend/', I copy 'backend/'.
# If I place it in root, I copy everything.
# Let's place it in root as 'Dockerfile.backend' or in 'backend/Dockerfile'.
# The plan says 'backend/Dockerfile'.

COPY backend/ ./backend/

# Expose the port the app runs on
EXPOSE 8001

# Command to run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
