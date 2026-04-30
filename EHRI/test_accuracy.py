import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pollution_service import PollutionDataFetcher, close_session


async def test_waqi():
    print("=" * 50)
    print("Testing WAQI for Delhi, Delhi...")
    print("=" * 50)
    data = await PollutionDataFetcher.fetch_from_waqi('Delhi', 'Delhi')
    if data:
        print(f"Location: {data['location']}")
        print(f"State: {data['state']}")
        print(f"AQI: {data['aqi']}")
        print(f"PM2.5: {data['pm25']}")
        print(f"PM10: {data['pm10']}")
        print(f"NO2: {data['no2']}")
        print(f"SO2: {data['so2']}")
        print(f"O3: {data['o3']}")
        print(f"CO: {data['co']}")
        print(f"Source: {data['source']}")
        print(f"Timestamp: {data['timestamp']}")

        if data['aqi'] is not None:
            print(f"\n[OK] WAQI AQI value present: {data['aqi']}")
        else:
            print("\n[WARN] WAQI AQI is None")
    else:
        print("WAQI: No data returned (check API key)")
    print()


async def test_openweather():
    print("=" * 50)
    print("Testing OpenWeather for Delhi, Delhi...")
    print("=" * 50)
    data = await PollutionDataFetcher.fetch_from_openweather('Delhi', 'Delhi')
    if data:
        print(f"Location: {data['location']}")
        print(f"State: {data['state']}")
        print(f"AQI: {data['aqi']}")
        print(f"PM2.5: {data['pm25']}")
        print(f"PM10: {data['pm10']}")
        print(f"NO2: {data['no2']}")
        print(f"SO2: {data['so2']}")
        print(f"O3: {data['o3']}")
        print(f"CO: {data['co']}")
        print(f"Source: {data['source']}")
        print(f"Timestamp: {data['timestamp']}")

        if data['aqi'] is not None:
            print(f"\n[OK] OpenWeather AQI value present: {data['aqi']} (note: OpenWeather uses 1-5 scale)")
        else:
            print("\n[WARN] OpenWeather AQI is None")
    else:
        print("OpenWeather: No data returned (API key likely not set)")
    print()


async def test_cpcb():
    print("=" * 50)
    print("Testing CPCB for Delhi, Delhi...")
    print("=" * 50)
    data = await PollutionDataFetcher.fetch_from_cpcb('Delhi', 'Delhi')
    if data:
        print(f"Location: {data['location']}")
        print(f"State: {data['state']}")
        print(f"AQI: {data['aqi']}")
        print(f"PM2.5: {data['pm25']}")
        print(f"PM10: {data['pm10']}")
        print(f"NO2: {data['no2']}")
        print(f"SO2: {data['so2']}")
        print(f"O3: {data['o3']}")
        print(f"CO: {data['co']}")
        print(f"Source: {data['source']}")
        print(f"Station: {data.get('station')}")
        print(f"Timestamp: {data['timestamp']}")

        if data['aqi'] is not None:
            print(f"\n[OK] CPCB AQI value present: {data['aqi']}")
        else:
            print("\n[WARN] CPCB AQI is None")
    else:
        print("CPCB: No data returned (API key likely not set or no stations found)")
    print()


async def test_full_pipeline():
    print("=" * 50)
    print("Testing FULL fetch_pollution_data pipeline for Delhi, Delhi...")
    print("=" * 50)
    data = await PollutionDataFetcher.fetch_pollution_data('Delhi', 'Delhi')
    if data:
        print(f"Location: {data['location']}")
        print(f"State: {data['state']}")
        print(f"AQI: {data['aqi']}")
        print(f"PM2.5: {data['pm25']}")
        print(f"PM10: {data['pm10']}")
        print(f"NO2: {data['no2']}")
        print(f"SO2: {data['so2']}")
        print(f"O3: {data['o3']}")
        print(f"CO: {data['co']}")
        print(f"Source: {data['source']}")
        print(f"Timestamp: {data['timestamp']}")

        if data['aqi'] is not None:
            print(f"\n[OK] Final AQI value present: {data['aqi']}")
            print(f"[INFO] Source used: {data['source']}")
        else:
            print("\n[ERROR] Final AQI is None - data validation failed!")
    else:
        print("FULL PIPELINE: No data returned from any source")
    print()


async def main():
    print("\n" + "=" * 50)
    print("INDEX LIVE DATA ACCURACY TEST")
    print("=" * 50)
    print(f"WAQI_API_KEY set: {bool(os.getenv('WAQI_API_KEY'))}")
    print(f"OPENWEATHER_API_KEY set: {bool(os.getenv('OPENWEATHER_API_KEY'))}")
    print(f"CPCB_API_KEY set: {bool(os.getenv('CPCB_API_KEY'))}")
    print()

    await test_cpcb()
    await test_waqi()
    await test_openweather()
    await test_full_pipeline()

    await close_session()
    print("Test complete.")


if __name__ == "__main__":
    asyncio.run(main())
