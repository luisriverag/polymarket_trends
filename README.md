# Polymarket Trends

Real-time visualization dashboard for Polymarket prediction markets.

## Features

- 📊 **Volume Trends** - 30-day trading volume charts
- 🔥 **Hot Events** - Top events by trading volume  
- 🐋 **Whale Trackers** - Top traders by volume and PnL
- 📈 **Market Movers** - Markets with significant price changes
- 🔍 **Insider Signals** - High conviction markets (>70% or <30% probability)
- ✨ **New Markets** - Recently created markets
- 🏆 **Underdog Wins** - Markets where unlikely outcomes resolved

## Tech Stack

- Flask (Python web framework)
- Chart.js for visualizations
- Polymarket Gamma API & Data API

## Installation

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Environment

- Python 3.12+
- Flask, requests, python-dotenv

## License

MIT
