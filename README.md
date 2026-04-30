# INDEX (Environmental Health Risk Index) API

A FastAPI-based service for real-time air pollution monitoring and health risk assessment using official Indian pollution data from CPCB (Central Pollution Control Board).

## Features

- **Real-time Pollution Data**: Fetches live air quality data from CPCB for accurate Indian pollution monitoring
- **Health Risk Assessment**: Calculates INDEX scores based on pollution levels and health parameters
- **Multiple Data Sources**: Prioritizes CPCB for Indian cities, with fallbacks to WAQI and OpenWeather
- **RESTful API**: Clean, documented endpoints with automatic OpenAPI documentation
- **Background Scheduling**: Automated data collection and processing
- **MongoDB Database**: Persistent storage for historical data and predictions

## Quick Start

### Prerequisites
- Python 3.8+
- CPCB API Key (get from [CPCB website](https://cpcb.nic.in/))

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd INDEX
```

2. Create virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
- Create a `.env` file in the repository root.
- Add your API keys and MongoDB settings as shown in the configuration section.

5. Run the application:
```bash
cd src
python app.py
```

Alternatively, run with Uvicorn:
```bash
cd src
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

6. Stop the application:
- Press `Ctrl+C` in the terminal running the server.

The API will be available at `http://localhost:8000` with documentation at `http://localhost:8000/docs`.

## API Endpoints

### Live Pollution Data
- `GET /live-pollution/{city}/{state}` - Get current pollution data
- `GET /live-pollution-history/{city}/{state}?hours=24` - Get historical data

### INDEX Predictions
- `POST /predict-live` - Compute INDEX prediction for current conditions

### User History
- `GET /user-history/{user_id}` - Get INDEX history for a user

### System Status
- `GET /status` - System health and statistics

## Data Sources

The API uses a hierarchical approach for data sources:

1. **CPCB (Central Pollution Control Board)** - Official Indian government data, most accurate for Indian cities
2. **WAQI (World Air Quality Index)** - Global air quality data
3. **OpenWeather** - Weather-based pollution estimates

For Indian cities, CPCB data is prioritized to ensure values match exactly with cpcb.gov.in.

## Configuration

Create a `.env` file with the following variables:

```env
# CPCB API Configuration
CPCB_API_KEY=your_cpcb_api_key_here

# Optional: Fallback APIs
WAQI_API_KEY=your_waqi_api_key_here
OPENWEATHER_API_KEY=your_openweather_api_key_here

# MongoDB Database
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=index_db

# Scheduler
SCHEDULER_INTERVAL_MINUTES=30
MONITORED_CITIES_WITH_STATES=Delhi,Delhi;Mumbai,Maharashtra;Bangalore,Karnataka;Chennai,Tamil Nadu;Kolkata,West Bengal
```

## Development

### Project Structure
```
src/
├── app.py              # Main FastAPI application
├── config.py           # Configuration management
├── database.py         # Database models and connections
├── pollution_service.py # External API integrations
├── fusion.py           # INDEX calculation logic
├── scheduler.py        # Background task scheduling
└── modules/            # Health parameter modules
    ├── cough.py
    ├── environment.py
    └── physiology.py
```

### Testing
```bash
# Run tests
pytest

# Check API documentation
open http://localhost:8000/docs
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.
