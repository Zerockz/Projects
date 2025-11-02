# Use the official Python image as a base
FROM python:3.10-slim

# Set env for cleaner logs & caches
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TOKENIZERS_PARALLELISM=false \
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies first (better build cache)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application files
COPY . .

# Expose the port the Flask app runs on
EXPOSE 5000

# (Optional) Healthcheck 
# Optional simple healthcheck
HEALTHCHECK CMD curl -fs http://127.0.0.1:5000/health || exit 1


# Command to run the Flask application
CMD ["python", "app.py"]
