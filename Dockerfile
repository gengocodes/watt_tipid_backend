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

# Cloud Run listens on port 8080 by default
EXPOSE 8080

# Cloud Run provides the PORT environment variable.
# If PORT exists, use it.
# Otherwise, default to 8080 for local Docker runs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
