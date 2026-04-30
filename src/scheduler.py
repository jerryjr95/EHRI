import logging
import asyncio
import os
from datetime import datetime
from typing import List, Tuple

try:
    from src.pollution_service import PollutionDataFetcher
except ModuleNotFoundError:
    from pollution_service import PollutionDataFetcher

logger = logging.getLogger(__name__)

SCHEDULER_INTERVAL_MINUTES = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", 30))
MONITORED_CITIES_STR = os.getenv(
    "MONITORED_CITIES_WITH_STATES",
    "Delhi,Delhi;Mumbai,Maharashtra;Bangalore,Karnataka;Chennai,Tamil Nadu;Kolkata,West Bengal"
)


def parse_monitored_cities(cities_str: str) -> List[Tuple[str, str]]:
    """Parse MONITORED_CITIES_WITH_STATES env var into list of (city, state) tuples."""
    cities = []
    if not cities_str:
        return cities
    for city_state in cities_str.split(";"):
        parts = city_state.split(",")
        if len(parts) >= 2:
            city = parts[0].strip()
            state = parts[1].strip()
            if city and state:
                cities.append((city, state))
        elif len(parts) == 1:
            city = parts[0].strip()
            if city:
                cities.append((city, city))
    if not cities:
        logger.warning("No valid monitored cities configured. Scheduler will not fetch data.")
    return cities


MONITORED_CITIES = parse_monitored_cities(MONITORED_CITIES_STR)


class PollutionScheduler:
    """Async scheduler for live pollution reads using asyncio."""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._running = False
            cls._instance._task = None
        return cls._instance

    async def start(self):
        async with self._lock:
            if self._running:
                logger.warning("Scheduler already running")
                return
            try:
                self._running = True
                self._task = asyncio.create_task(self._poll_loop())
                logger.info(f"Pollution scheduler started, fetching every {SCHEDULER_INTERVAL_MINUTES} minutes")
            except Exception as e:
                self._running = False
                logger.error(f"Error starting scheduler: {e}")
                raise

    async def stop(self):
        async with self._lock:
            if not self._running:
                return
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None
            logger.info("Pollution scheduler stopped")

    async def _poll_loop(self):
        """Main polling loop that runs indefinitely until stopped."""
        while self._running:
            try:
                await self._fetch_all_cities()
            except Exception as e:
                logger.error(f"Error during city fetch cycle: {e}")
            # Sleep in small increments to allow responsive shutdown
            for _ in range(SCHEDULER_INTERVAL_MINUTES * 60):
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def _fetch_all_cities(self):
        """Fetch pollution data for all monitored cities concurrently."""
        logger.info(f"Fetching pollution data for {len(MONITORED_CITIES)} cities")
        tasks = []
        for city, state in MONITORED_CITIES:
            tasks.append(self._fetch_with_error_handling(city, state))
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Pollution data fetch completed")

    async def _fetch_with_error_handling(self, city: str, state: str):
        """Fetch data for a single city with error handling."""
        try:
            await PollutionDataFetcher.fetch_pollution_data(city, state)
        except Exception as e:
            logger.error(f"Error fetching data for {city}, {state}: {e}")

    @classmethod
    def is_running(cls) -> bool:
        """Check if the scheduler is currently running."""
        return cls._instance is not None and cls._instance._running


# Global scheduler instance
pollution_scheduler = PollutionScheduler()


def start_scheduler():
    """Synchronous wrapper to start scheduler (for lifespan)."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(pollution_scheduler.start())
    except RuntimeError:
        # No running loop, create one
        asyncio.run(pollution_scheduler.start())


def stop_scheduler():
    """Synchronous wrapper to stop scheduler (for lifespan)."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(pollution_scheduler.stop())
    except RuntimeError:
        asyncio.run(pollution_scheduler.stop())

