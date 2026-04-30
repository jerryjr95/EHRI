import aiohttp
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, Dict

try:
    from src.modules.environment import compute_aqi
    from src.database import insert_pollution_reading
except ModuleNotFoundError:
    from modules.environment import compute_aqi
    from database import insert_pollution_reading

logger = logging.getLogger(__name__)

WAQI_API_KEY = os.getenv("WAQI_API_KEY", "demo")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
CPCB_API_KEY = os.getenv("CPCB_API_KEY", "")

# Shared aiohttp session for connection pooling
_session: Optional[aiohttp.ClientSession] = None


def normalize_pollutant_key(value: str) -> str:
    if not value:
        return ""
    return value.strip().upper().replace("_", "").replace(".", "")


def parse_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_session() -> aiohttp.ClientSession:
    """Get or create the shared aiohttp ClientSession."""
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        _session = aiohttp.ClientSession(timeout=timeout)
    return _session


async def close_session():
    """Close the shared aiohttp session."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


class PollutionDataFetcher:
    """Fetch live pollutant and AQI readings from CPCB, WAQI, and OpenWeather."""

    @staticmethod
    async def fetch_from_cpcb(city: str, state: str = "") -> Optional[Dict]:
        if not CPCB_API_KEY:
            logger.warning("CPCB API key not configured. Skipping CPCB fetch.")
            return None

        url = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
        city_terms = [city.lower()]
        city_aliases = {
            "bangalore": ["bengaluru"],
            "kolkata": ["calcutta"],
            "mumbai": ["bombay"],
            "delhi": ["new delhi"]
        }
        city_terms.extend(city_aliases.get(city.lower(), []))

        try:
            session = get_session()
            async with session.get(
                url,
                params={"api-key": CPCB_API_KEY, "format": "json", "limit": 500},
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"CPCB API returned {resp.status} for {city}")
                    return None

                data = await resp.json()
                records = data.get("records", [])
                if not records:
                    logger.warning(f"No CPCB records for {city}")
                    return None

                matching = []
                for record in records:
                    station_name = (record.get("station") or "").lower()
                    city_name = (record.get("city") or "").lower()
                    state_name = (record.get("state") or "").lower()
                    if any(term in station_name or term in city_name for term in city_terms):
                        if not state or state.lower() in state_name or (city.lower() == "faridabad" and "haryana" in state_name):
                            matching.append(record)

                if not matching:
                    logger.warning(f"No matching CPCB stations for {city}, {state}")
                    return None

                station_bins = {}
                for record in matching:
                    station = record.get("station") or "unknown"
                    if station not in station_bins:
                        station_bins[station] = {
                            "pollutants": {},
                            "last_update": record.get("last_update")
                        }
                    key = normalize_pollutant_key(record.get("pollutant_id") or record.get("pollutant") or "")
                    value = parse_float(record.get("avg_value") or record.get("value"))
                    if value is None:
                        continue
                    if key in {"PM25"}:
                        station_bins[station]["pollutants"]["pm25"] = value
                    elif key == "PM10":
                        station_bins[station]["pollutants"]["pm10"] = value
                    elif key == "NO2":
                        station_bins[station]["pollutants"]["no2"] = value
                    elif key == "SO2":
                        station_bins[station]["pollutants"]["so2"] = value
                    elif key in {"OZONE", "O3"}:
                        station_bins[station]["pollutants"]["o3"] = value
                    elif key == "CO":
                        station_bins[station]["pollutants"]["co"] = value

                best_station = None
                best_pollutants = {}
                best_timestamp = None
                best_aqi = -1
                for station, details in station_bins.items():
                    pollutants = details["pollutants"]
                    if not pollutants:
                        continue
                    station_aqi = compute_aqi(**pollutants)
                    if station_aqi is not None and station_aqi > best_aqi:
                        best_aqi = station_aqi
                        best_station = station
                        best_pollutants = pollutants
                        best_timestamp = details["last_update"]

                if not best_pollutants:
                    logger.warning(f"No valid CPCB pollutant set for {city}")
                    return None

                timestamp = datetime.now(timezone.utc)
                if best_timestamp:
                    try:
                        if "T" in best_timestamp:
                            timestamp = datetime.fromisoformat(best_timestamp.replace("Z", "+00:00"))
                        else:
                            timestamp = datetime.strptime(best_timestamp, "%d-%m-%Y %H:%M:%S")
                            # Make naive datetime UTC-aware to allow subtraction
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to parse CPCB timestamp {best_timestamp}")
                        timestamp = datetime.now(timezone.utc)

                age_hours = (datetime.now(timezone.utc) - timestamp).total_seconds() / 3600
                if age_hours > 6:
                    logger.warning(f"CPCB data for {city} is {age_hours:.1f} hours old; falling back")
                    fallback = await PollutionDataFetcher.fetch_from_waqi(city, state)
                    if fallback:
                        return fallback

                return {
                    "location": city,
                    "state": state or "Unknown",
                    "timestamp": timestamp,
                    "pm25": best_pollutants.get("pm25"),
                    "pm10": best_pollutants.get("pm10"),
                    "no2": best_pollutants.get("no2"),
                    "so2": best_pollutants.get("so2"),
                    "o3": best_pollutants.get("o3"),
                    "co": best_pollutants.get("co"),
                    "aqi": best_aqi,
                    "source": "cpcb",
                    "station": best_station,
                    "last_update": best_timestamp
                }
        except Exception as e:
            logger.error(f"CPCB fetch error for {city}: {e}")
            return None

    @staticmethod
    async def fetch_from_waqi(city: str, state: str = "") -> Optional[Dict]:
        query = f"{city},{state}" if state else city
        encoded_query = urllib.parse.quote(query)
        url = f"https://api.waqi.info/feed/{encoded_query}/"
        try:
            session = get_session()
            async with session.get(url, params={"token": WAQI_API_KEY}) as resp:
                if resp.status != 200:
                    logger.warning(f"WAQI status {resp.status} for {query}")
                    return None
                payload = await resp.json()
                if payload.get("status") != "ok":
                    logger.warning(f"WAQI error for {query}: {payload.get('data')}")
                    if state:
                        return await PollutionDataFetcher.fetch_from_waqi(city, "")
                    return None

                data = payload.get("data", {})
                time_data = data.get("time", {})
                timestamp = datetime.now(timezone.utc)
                if isinstance(time_data.get("s"), str):
                    try:
                        timestamp = datetime.fromisoformat(time_data["s"])
                    except ValueError:
                        pass

                return {
                    "location": data.get("city", {}).get("name", city),
                    "state": state or "Unknown",
                    "timestamp": timestamp,
                    "pm25": data.get("iaqi", {}).get("pm25", {}).get("v"),
                    "pm10": data.get("iaqi", {}).get("pm10", {}).get("v"),
                    "no2": data.get("iaqi", {}).get("no2", {}).get("v"),
                    "so2": data.get("iaqi", {}).get("so2", {}).get("v"),
                    "o3": data.get("iaqi", {}).get("o3", {}).get("v"),
                    "co": data.get("iaqi", {}).get("co", {}).get("v"),
                    "aqi": data.get("aqi"),
                    "source": "waqi"
                }
        except Exception as e:
            logger.error(f"WAQI fetch error for {city},{state}: {e}")
            return None

    @staticmethod
    async def fetch_from_openweather(city: str, state: str = "", lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[Dict]:
        if not OPENWEATHER_API_KEY:
            logger.warning("OpenWeather API key not set. Skipping fallback.")
            return None
        try:
            session = get_session()
            if lat is None or lon is None:
                geo_url = "https://api.openweathermap.org/geo/1.0/direct"
                query = f"{city},{state}" if state else city
                async with session.get(geo_url, params={"q": query, "appid": OPENWEATHER_API_KEY}) as resp:
                    if resp.status != 200:
                        logger.warning(f"OpenWeather geo lookup failed for {query} status {resp.status}")
                        return None
                    geo_data = await resp.json()
                    if geo_data:
                        lat = geo_data[0].get("lat")
                        lon = geo_data[0].get("lon")

            if lat is None or lon is None:
                logger.warning(f"Could not resolve coordinates for {city}, {state}")
                return None

            url = "https://api.openweathermap.org/data/2.5/air_pollution"
            async with session.get(url, params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY}) as resp:
                if resp.status != 200:
                    logger.warning(f"OpenWeather air pollution failed for {city} status {resp.status}")
                    return None
                payload = await resp.json()
                components = payload.get("list", [{}])[0].get("components", {})
                aqi = payload.get("list", [{}])[0].get("main", {}).get("aqi")
                return {
                    "location": city,
                    "state": state or "Unknown",
                    "timestamp": datetime.now(timezone.utc),
                    "pm25": components.get("pm2_5"),
                    "pm10": components.get("pm10"),
                    "no2": components.get("no2"),
                    "so2": components.get("so2"),
                    "o3": components.get("o3"),
                    "co": components.get("co"),
                    "aqi": aqi,
                    "source": "openweather"
                }
        except Exception as e:
            logger.error(f"OpenWeather fetch error for {city},{state}: {e}")
            return None

    @staticmethod
    async def fetch_pollution_data(city: str, state: str) -> Optional[dict]:
        logger.info(f"Fetching pollution data for {city},{state}")

        # Try CPCB first (primary source)
        data = await PollutionDataFetcher.fetch_from_cpcb(city, state)
        if data:
            logger.info(f"Successfully fetched data from CPCB for {city},{state}")
        else:
            logger.warning(f"CPCB failed for {city},{state}, trying WAQI")
            # Try WAQI as first fallback
            data = await PollutionDataFetcher.fetch_from_waqi(city, state)
            if data:
                logger.info(f"Successfully fetched data from WAQI for {city},{state}")
            else:
                logger.warning(f"WAQI failed for {city},{state}, trying OpenWeather")
                # Try OpenWeather as second fallback
                data = await PollutionDataFetcher.fetch_from_openweather(city, state)
                if data:
                    logger.info(f"Successfully fetched data from OpenWeather for {city},{state}")
                else:
                    logger.error(f"All pollution APIs failed for {city},{state}")
                    return None

        # Validate AQI value — preserve externally sourced AQI exactly
        aqi_value = data.get("aqi")
        pollutants = {k: v for k, v in data.items() if k in ("pm25", "pm10", "co", "no2", "so2", "o3") and v is not None}
        source = data.get("source", "unknown")

        if aqi_value is not None and not isinstance(aqi_value, (int, float)):
            logger.warning(f"Non-numeric AQI {aqi_value} for {city},{state}; computing from pollutants")
            aqi_value = compute_aqi(**pollutants)
        elif aqi_value is None and pollutants:
            logger.warning(f"No AQI provided for {city},{state}; computing from pollutants")
            aqi_value = compute_aqi(**pollutants)
        # NOTE: Do NOT clamp AQI from external APIs (WAQI can report >500).
        # Only validate range for internally computed AQI.
        elif aqi_value is not None and source == "unknown" and not (0 <= aqi_value <= 500):
            logger.warning(f"Internally computed AQI {aqi_value} out of range for {city},{state}; clamping")
            aqi_value = max(0, min(500, aqi_value))

        if aqi_value is None and not pollutants:
            logger.error(f"No valid AQI or pollutant data for {city},{state}")
            return None

        payload = {
            "location": data["location"],
            "state": data.get("state", state),
            "timestamp": data["timestamp"],
            "pm25": data.get("pm25"),
            "pm10": data.get("pm10"),
            "co": data.get("co"),
            "no2": data.get("no2"),
            "so2": data.get("so2"),
            "o3": data.get("o3"),
            "aqi": aqi_value,
            "source": data.get("source", "unknown"),
            "station": data.get("station"),
            "last_update": data.get("last_update")
        }

        try:
            stored = await insert_pollution_reading(payload)
            logger.info(f"Stored pollution reading for {city},{state} | AQI={aqi_value} | source={payload['source']}")
            return stored
        except Exception as e:
            logger.warning(f"Failed to store pollution reading for {city},{state}: {e}. Returning live data without storage.")
            return payload

