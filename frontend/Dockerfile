# frontend/Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN python -m venv .venv && . ./.venv/bin/activate && pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app.py .

# Expose Streamlit port
EXPOSE 8501

# Command to run the app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
