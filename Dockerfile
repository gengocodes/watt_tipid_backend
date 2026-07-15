FROM python:3.12-slim

WORKDIR /app

# Create a non-root user for security
# Running containers as root is a security risk because
# a compromised application would have root privileges
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

COPY requirements.txt .

# --no-cache-dir prevents pip from storing unnecessary cache files
RUN pip install --no-cache-dir \
    -r requirements.txt


# Copy application source code
COPY ./app ./app

# Change ownership of application files
# so the non-root user can access them
RUN chown -R appuser:appgroup /app

# Switch from root to the non-root user
USER appuser

# Document that the container listens on port 8000
# This does not actually publish the port;
# docker-compose.yml handles that
EXPOSE 8000

# Start FastAPI using Uvicorn
# app.main:app means:
# - app = package/folder
# - main = main.py
# - app = FastAPI instance inside main.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
