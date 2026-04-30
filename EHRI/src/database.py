import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "index_db")
MONGODB_MAX_POOL_SIZE = int(os.getenv("MONGODB_MAX_POOL_SIZE", "50"))
MONGODB_TIMEOUT_MS = int(os.getenv("MONGODB_TIMEOUT_MS", "5000"))
MONGODB_TLS_ALLOW_INVALID = os.getenv("MONGODB_TLS_ALLOW_INVALID_CERTIFICATES", "false").lower() == "true"

client_kwargs = dict(
    maxPoolSize=MONGODB_MAX_POOL_SIZE,
    serverSelectionTimeoutMS=MONGODB_TIMEOUT_MS,
)
if MONGODB_TLS_ALLOW_INVALID:
    client_kwargs["tlsAllowInvalidCertificates"] = True

client = AsyncIOMotorClient(MONGODB_URI, **client_kwargs)
db = client[MONGODB_DB]

# Track connection health for quick checks
_db_connected = False


async def ping_database() -> bool:
    """Check if MongoDB connection is alive."""
    global _db_connected
    try:
        await client.admin.command("ping")
        _db_connected = True
        return True
    except Exception:
        _db_connected = False
        return False


async def setup_indexes():
    """Create indexes on frequently queried fields for performance."""
    try:
        await db.pollutant_readings.create_index("location")
        await db.pollutant_readings.create_index("state")
        await db.pollutant_readings.create_index("timestamp")
        await db.pollutant_readings.create_index([("location", 1), ("state", 1), ("timestamp", -1)])
        await db.index_results.create_index("user_id")
        await db.index_results.create_index("timestamp")
        await db.health_readings.create_index("user_id")
        await db.health_readings.create_index("timestamp")
    except Exception as e:
        raise RuntimeError(f"Failed to create database indexes: {e}")


async def get_db() -> AsyncGenerator:
    """FastAPI dependency that yields the MongoDB database."""
    if not _db_connected:
        await ping_database()
    yield db


async def insert_pollution_reading(payload: dict) -> dict:
    payload.setdefault("created_at", datetime.now(timezone.utc))
    result = await db.pollutant_readings.insert_one(payload)
    payload["id"] = str(result.inserted_id)
    return payload


async def insert_health_reading(payload: dict) -> dict:
    payload.setdefault("created_at", datetime.now(timezone.utc))
    result = await db.health_readings.insert_one(payload)
    payload["id"] = str(result.inserted_id)
    return payload


async def insert_index_result(payload: dict) -> dict:
    payload.setdefault("created_at", datetime.now(timezone.utc))
    result = await db.index_results.insert_one(payload)
    payload["id"] = str(result.inserted_id)
    return payload


def serialize_document(document: dict) -> Optional[dict]:
    if not document:
        return None
    document["id"] = str(document.pop("_id"))
    return document
