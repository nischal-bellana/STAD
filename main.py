import os
import urllib.parse
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis import asyncio as aioredis
from dotenv import load_dotenv

# Import your existing logic
from detector import EarthquakeAnomalyDetector

load_dotenv()

app = FastAPI(
    title="Spatio-Temporal Anomaly Detection API",
    description="Detects earthquake anomalies using STL decomposition and DBSCAN clustering.",
    version="1.0.0"
)

# --- Startup Event: Initialize Redis Cache ---
@app.on_event("startup")
async def startup():
    # Connects to Redis (defaults to the docker service name 'redis', or localhost if running locally)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis = aioredis.from_url(redis_url, encoding="utf8", decode_responses=True)
    FastAPICache.init(RedisBackend(redis), prefix="anomaly-cache")

# --- Helper: Database Connection ---
def get_db_connection():
    password = os.getenv('POSTGRES_PASSWORD', 'postgres')
    encoded_password = urllib.parse.quote_plus(password)
    host = os.getenv('POSTGRES_HOST', 'localhost')
    db = os.getenv('POSTGRES_DB', 'staddb')
    user = os.getenv('POSTGRES_USER', 'postgres')
    return f'postgresql://{user}:{encoded_password}@{host}:5432/{db}'

# --- Endpoints ---
@app.get("/")
def health_check():
    return {"status": "healthy", "service": "Earthquake Anomaly API"}

@app.get("/api/v1/anomalies")
@cache(expire=3600) # Cache the result for 1 hour
async def fetch_anomalies(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format")
):
    try:
        conn_str = get_db_connection()
        detector = EarthquakeAnomalyDetector(conn_str)
        
        # Run your pipeline
        report = detector.run_pipeline(start_date, end_date)
        
        # Handle string responses (like "No data found")
        if isinstance(report, str):
            return JSONResponse(status_code=200, content={"message": report, "data": []})
            
        # Convert DataFrame to JSON-friendly dictionary
        data = report.to_dict(orient="records")
        return {"message": "Success", "data": data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
