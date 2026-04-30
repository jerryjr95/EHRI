import math

# CPCB breakpoint logic for multiple pollutants


def pm25_subindex(pm25):
    if pm25 <= 30:
        return (50/30) * pm25
    elif pm25 <= 60:
        return 51 + ((100-51)/(60-31))*(pm25-31)
    elif pm25 <= 90:
        return 101 + ((200-101)/(90-61))*(pm25-61)
    elif pm25 <= 120:
        return 201 + ((300-201)/(120-91))*(pm25-91)
    elif pm25 <= 250:
        return 301 + ((400-301)/(250-121))*(pm25-121)
    else:
        return 401 + ((500-401)/(500-251))*(pm25-251)


def pm10_subindex(pm10):
    if pm10 <= 50:
        return (50/50) * pm10
    elif pm10 <= 100:
        return 51 + ((100-51)/(100-51))*(pm10-51)
    elif pm10 <= 250:
        return 101 + ((200-101)/(250-101))*(pm10-101)
    elif pm10 <= 350:
        return 201 + ((300-201)/(350-251))*(pm10-251)
    elif pm10 <= 430:
        return 301 + ((400-301)/(430-351))*(pm10-351)
    else:
        return 401 + ((500-401)/(500-431))*(pm10-431)


def co_subindex(co):
    if co <= 1:
        return (50/1) * co
    elif co <= 2:
        return 51 + ((100-51)/(2-1))*(co-1)
    elif co <= 10:
        return 101 + ((200-101)/(10-2))*(co-2)
    elif co <= 17:
        return 201 + ((300-201)/(17-10))*(co-10)
    elif co <= 34:
        return 301 + ((400-301)/(34-17))*(co-17)
    else:
        return 401 + ((500-401)/(50-34))*(co-34)


def no2_subindex(no2):
    if no2 <= 40:
        return (50/40) * no2
    elif no2 <= 80:
        return 51 + ((100-51)/(80-40))*(no2-40)
    elif no2 <= 180:
        return 101 + ((200-101)/(180-80))*(no2-80)
    elif no2 <= 280:
        return 201 + ((300-201)/(280-180))*(no2-180)
    elif no2 <= 400:
        return 301 + ((400-301)/(400-280))*(no2-280)
    else:
        return 401 + ((500-401)/(500-400))*(no2-400)


def so2_subindex(so2):
    if so2 <= 40:
        return (50/40) * so2
    elif so2 <= 80:
        return 51 + ((100-51)/(80-40))*(so2-40)
    elif so2 <= 380:
        return 101 + ((200-101)/(380-80))*(so2-80)
    elif so2 <= 800:
        return 201 + ((300-201)/(800-380))*(so2-380)
    elif so2 <= 1600:
        return 301 + ((400-301)/(1600-800))*(so2-800)
    else:
        return 401 + ((500-401)/(2000-1600))*(so2-1600)


def o3_subindex(o3):
    if o3 <= 50:
        return (50/50) * o3
    elif o3 <= 100:
        return 51 + ((100-51)/(100-50))*(o3-50)
    elif o3 <= 168:
        return 101 + ((200-101)/(168-100))*(o3-100)
    elif o3 <= 208:
        return 201 + ((300-201)/(208-168))*(o3-168)
    elif o3 <= 748:
        return 301 + ((400-301)/(748-208))*(o3-208)
    else:
        return 401 + ((500-401)/(1000-748))*(o3-748)


def compute_aqi(pm25=None, pm10=None, co=None, no2=None, so2=None, o3=None):
    """
    Compute AQI from multiple pollutants using CPCB breakpoints.
    Returns the maximum subindex among all provided pollutants, or None if no data.
    """
    subindices = []

    if pm25 is not None:
        subindices.append(pm25_subindex(pm25))
    if pm10 is not None:
        subindices.append(pm10_subindex(pm10))
    if co is not None:
        subindices.append(co_subindex(co))
    if no2 is not None:
        subindices.append(no2_subindex(no2))
    if so2 is not None:
        subindices.append(so2_subindex(so2))
    if o3 is not None:
        subindices.append(o3_subindex(o3))

    if not subindices:
        return None
    return round(max(subindices), 2)


def aqi_to_index(aqi):
    # Convert AQI (0-500) to score (1-10) for normalized comparison
    if aqi is None or not isinstance(aqi, (int, float)):
        return 1.0
    score = min(10, max(1, aqi / 50))
    return round(score, 2)


def environment_score(pm25=None, pm10=None, co=None, no2=None, so2=None, o3=None, live_aqi=None):
    """
    Compute environment score from multiple pollutants.

    If live_aqi is provided from WAQI/OpenWeather API, use it directly.
    This ensures AQI matches the government/official API source exactly.
    Otherwise compute AQI from individual pollutant values using CPCB standards.
    """
    # Validate live_aqi type
    if live_aqi is not None and not isinstance(live_aqi, (int, float)):
        live_aqi = None

    if live_aqi is not None:
        # Use live AQI from API - this is the authoritative value
        aqi = live_aqi
    else:
        # Compute AQI only if live value not available
        aqi = compute_aqi(pm25=pm25, pm10=pm10, co=co, no2=no2, so2=so2, o3=o3)

    # Ensure AQI is valid (between 0-500)
    aqi = max(0, min(500, aqi)) if aqi is not None else 0

    idx = aqi_to_index(aqi)
    return {
        "aqi": aqi,
        "score": idx,
        "pollutants": {
            "pm25": pm25,
            "pm10": pm10,
            "co": co,
            "no2": no2,
            "so2": so2,
            "o3": o3
        }
    }

