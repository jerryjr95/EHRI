import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv
try:
    from src.modules.environment import environment_score
    from src.modules.physiology import physiology_score
    from src.modules.cough import cough_score
    from src.fusion import compute_index
    from src.recommendations import risk_band, advice
    from src.database import get_db, insert_health_reading, insert_index_result
    from src.pollution_service import PollutionDataFetcher, close_session
    from src.scheduler import PollutionScheduler, start_scheduler, stop_scheduler
except ModuleNotFoundError:
    from modules.environment import environment_score
    from modules.physiology import physiology_score
    from modules.cough import cough_score
    from fusion import compute_index
    from recommendations import risk_band, advice
    from database import get_db, insert_health_reading, insert_index_result
    from pollution_service import PollutionDataFetcher, close_session
    from scheduler import PollutionScheduler, start_scheduler, stop_scheduler

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

openapi_tags = [
    {"name": "Health Check", "description": "System health and status endpoints."},
    {"name": "Manual Predictions", "description": "Use manual pollution and health inputs to compute INDEX."},
    {"name": "Live Pollution Data", "description": "Fetch live pollution data and historical values."},
    {"name": "Live Prediction", "description": "Compute INDEX using live pollution and health metrics."}
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger.info("Starting INDEX API...")
    try:
        start_scheduler()
        logger.info("Background pollution scheduler started")
    except Exception as e:
        logger.error(f"Startup scheduler error: {e}")
    yield
    logger.info("Shutting down INDEX API...")
    try:
        stop_scheduler()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Shutdown scheduler error: {e}")
    try:
        await close_session()
        logger.info("HTTP session closed")
    except Exception as e:
        logger.error(f"Session close error: {e}")


app = FastAPI(
    title="INDEX API - Live Pollution & Health Monitoring",
    version="2.0",
    description="INDEX backend service for environmental, physiological, and cough risk fusion.",
    openapi_tags=openapi_tags,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS: restrict credentials when allowing all origins (security fix)
allow_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
allow_origins = [o.strip() for o in allow_origins_env.split(",")]
allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


def dominant_factor(cough: float, environment: float, physiology: float) -> str:
    scores = {"cough": cough, "environment": environment, "body vitals": physiology}
    return max(scores, key=scores.get)


class LivePredictRequest(BaseModel):
    city: str = Field(..., example="Faridabad")
    state: Optional[str] = Field(None, example="Haryana")
    heart_rate: int = Field(..., ge=30, le=200, example=82)
    spo2: int = Field(..., ge=50, le=100, example=95)
    respiratory_rate: int = Field(..., ge=8, le=40, example=18)
    user_id: Optional[str] = Field(None, example="user_123")
    cough_score: Optional[float] = Field(None, ge=0.0, le=10.0, example=6.5)


@app.get("/", tags=["Health Check"])
def home():
    """
    INDEX API root endpoint.
    Returns API information and links to documentation.
    """
    return {
        "message": "INDEX API - Live Pollution & Health Monitoring",
        "version": "2.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "live_pollution": "GET /live-pollution/{city}/{state}",
            "pollution_history": "GET /live-pollution-history/{city}/{state}",
            "predict": "POST /predict-live",
            "user_history": "GET /user-history/{user_id}",
            "status": "GET /status"
        }
    }


@app.get("/live-pollution/{city}/{state}", tags=["Live Pollution Data"], summary="Get latest pollution data")
async def get_live_pollution(city: str, state: str, db=Depends(get_db)):
    logger.info(f"Fetching pollution for {city}, {state}")
    try:
        reading = await PollutionDataFetcher.fetch_pollution_data(city, state)
        if reading:
            logger.info(f"Successfully fetched pollution data for {city}, {state}")
            ts = reading.get("timestamp")
            ts_iso = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else None
            return {
                "timestamp": ts_iso,
                "location": reading["location"],
                "state": reading["state"],
                "pollutants": {
                    "pm25": reading.get("pm25"),
                    "pm10": reading.get("pm10"),
                    "no2": reading.get("no2"),
                    "so2": reading.get("so2"),
                    "o3": reading.get("o3"),
                    "co": reading.get("co"),
                },
                "aqi": reading["aqi"],
                "source": reading.get("source"),
                "station": reading.get("station"),
            }

        logger.warning(f"No live data, trying cache for {city}, {state}")
        query = {
            "location": {"$regex": f"^{city}$", "$options": "i"},
            "state": {"$regex": f"^{state}$", "$options": "i"},
        }
        cached = await db.pollutant_readings.find_one(query, sort=[("timestamp", -1)])
        if cached:
            logger.info(f"Returning cached data for {city}, {state}")
            ts = cached.get("timestamp")
            ts_iso = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else None
            return {
                "timestamp": ts_iso,
                "location": cached["location"],
                "state": cached["state"],
                "pollutants": {
                    "pm25": cached.get("pm25"),
                    "pm10": cached.get("pm10"),
                    "no2": cached.get("no2"),
                    "so2": cached.get("so2"),
                    "o3": cached.get("o3"),
                    "co": cached.get("co"),
                },
                "aqi": cached["aqi"],
                "source": "cached",
            }

        logger.error(f"No pollution data available for {city}, {state}")
        raise HTTPException(status_code=404, detail=f"No pollution data available for {city}, {state}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_live_pollution failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch pollution data")


@app.get("/live-pollution-history/{city}/{state}", tags=["Live Pollution Data"], summary="Get pollution history")
async def get_pollution_history(
    city: str,
    state: str,
    hours: int = Query(24, ge=1, le=168),
    db=Depends(get_db)
):
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = {
            "location": {"$regex": f"^{city}$", "$options": "i"},
            "state": {"$regex": f"^{state}$", "$options": "i"},
            "timestamp": {"$gte": cutoff},
        }
        cursor = db.pollutant_readings.find(query).sort("timestamp", -1)
        readings = []
        async for item in cursor:
            ts = item.get("timestamp")
            readings.append({
                "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else None,
                "pm25": item.get("pm25"),
                "pm10": item.get("pm10"),
                "no2": item.get("no2"),
                "so2": item.get("so2"),
                "o3": item.get("o3"),
                "co": item.get("co"),
                "aqi": item.get("aqi"),
            })
        if not readings:
            raise HTTPException(status_code=404, detail=f"No pollution history available for {city}, {state}")
        return {"city": city, "state": state, "hours": hours, "readings": readings}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_pollution_history failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch pollution history")


@app.get("/user-history/{user_id}", tags=["Live Prediction"], summary="Get INDEX history for a user")
async def get_user_history(
    user_id: str,
    limit: int = Query(50, ge=1, le=500),
    db=Depends(get_db)
):
    try:
        cursor = db.index_results.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
        history = []
        async for item in cursor:
            ts = item.get("timestamp")
            history.append({
                "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else None,
                "location": item["location"],
                "state": item.get("state"),
                "cough_score": item.get("cough_score"),
                "environment_score": item.get("environment_score"),
                "physiology_score": item.get("physiology_score"),
                "index_score": item["index_score"],
                "risk_band": item["risk_band"],
                "dominant_factor": item.get("dominant_factor"),
            })
        return {"user_id": user_id, "history": history}
    except Exception as e:
        logger.error(f"get_user_history failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch user history")


@app.post("/predict-live", tags=["Live Prediction"], summary="Compute INDEX from live pollution and health metrics")
async def predict_live(request: LivePredictRequest, db=Depends(get_db)):
    pollution = await PollutionDataFetcher.fetch_pollution_data(request.city, request.state or request.city)
    if not pollution:
        raise HTTPException(status_code=404, detail=f"No pollution data for {request.city}, {request.state}")

    cough = cough_score(request.cough_score)
    env = environment_score(
        pm25=pollution.get("pm25"),
        pm10=pollution.get("pm10"),
        co=pollution.get("co"),
        no2=pollution.get("no2"),
        so2=pollution.get("so2"),
        o3=pollution.get("o3"),
        live_aqi=pollution.get("aqi"),
    )
    phys = physiology_score(request.heart_rate, request.spo2, request.respiratory_rate)
    final_score = compute_index(cough, env["score"], phys)
    band = risk_band(final_score)
    dominant = dominant_factor(cough, env["score"], phys)

    now = datetime.now(timezone.utc)
    health_doc = {
        "user_id": request.user_id,
        "timestamp": now,
        "heart_rate": request.heart_rate,
        "spo2": request.spo2,
        "respiratory_rate": request.respiratory_rate,
        "physiology_score": phys,
    }
    health_reading_id = None
    try:
        inserted_health = await insert_health_reading(health_doc)
        health_reading_id = inserted_health.get("id")
    except Exception as e:
        logger.warning(f"Failed to store health reading: {e}")

    index_doc = {
        "user_id": request.user_id,
        "timestamp": now,
        "location": request.city,
        "state": request.state or request.city,
        "cough_score": cough,
        "environment_score": env["score"],
        "physiology_score": phys,
        "index_score": final_score,
        "risk_band": band,
        "dominant_factor": dominant,
        "pollution_reading_id": pollution.get("id"),
        "health_reading_id": health_reading_id,
    }
    try:
        await insert_index_result(index_doc)
    except Exception as e:
        logger.warning(f"Failed to store INDEX result: {e}")

    return {
        "timestamp": now.isoformat(),
        "user_id": request.user_id,
        "location": request.city,
        "state": request.state or request.city,
        "pollution": {
            "pm25": pollution.get("pm25"),
            "pm10": pollution.get("pm10"),
            "no2": pollution.get("no2"),
            "so2": pollution.get("so2"),
            "o3": pollution.get("o3"),
            "co": pollution.get("co"),
            "aqi": pollution.get("aqi"),
            "source": pollution.get("source", "unknown"),
        },
        "health": {
            "heart_rate": request.heart_rate,
            "spo2": request.spo2,
            "respiratory_rate": request.respiratory_rate,
        },
        "scores": {
            "cough_score": cough,
            "environment_score": env["score"],
            "physiology_score": phys,
            "index_score": final_score,
        },
        "risk_band": band,
        "dominant_factor": dominant,
        "recommendations": advice(band),
    }


@app.get('/status', tags=['Health Check'], summary='Get current system status')
async def get_status(db=Depends(get_db)):
    try:
        total_predictions = await db.index_results.count_documents({})
        total_readings = await db.pollutant_readings.count_documents({})
        latest_reading = await db.pollutant_readings.find_one({}, sort=[('timestamp', -1)])
        ts = latest_reading['timestamp'] if latest_reading else None
        ts_iso = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else None
        return {
            'status': 'running',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'scheduler': 'active' if PollutionScheduler.is_running() else 'inactive',
            'database': 'connected',
            'statistics': {
                'total_predictions': total_predictions,
                'total_pollution_readings': total_readings,
                'latest_reading_time': ts_iso,
            },
        }
    except Exception as e:
        logger.error(f'MongoDB connection error: {e}')
        raise HTTPException(
            status_code=503,
            detail='Database unavailable'
        )


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
