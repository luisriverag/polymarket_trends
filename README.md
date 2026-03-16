# Polymarket Trends

Real-time visualization dashboard for Polymarket prediction markets.

![Dashboard Preview](https://via.placeholder.com/800x400?text=Polymarket+Trends+Dashboard)

## Features

- 📊 **Volume Trends** - 30-day trading volume charts
- 📈 **Market Sentiment** - Overall bullish/bearish probability analysis with distribution chart
- 🔥 **Hot Events** - Top events by trading volume  
- 🐋 **Whale Trackers** - Top traders with win rate, PnL, and liquidity analysis
- ↩️ **Reversals** - Markets with big price swings (surging, crashing, recovering)
- 🔍 **Insider Signals** - High conviction trades (Strong Yes/No, Hot, Momentum)
- 🏆 **Resolutions** - Tabbed view of Yes/No/Underdog/Blowout outcomes
- 💧 **Liquidity Analysis** - High liquidity markets

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Polymarket Trends                        │
├─────────────────────────────────────────────────────────────┤
│  Flask App (app.py)                                         │
│  ├── fetch_markets() - Data pipeline                         │
│  │   ├── Gamma API: /markets, /events, /tags               │
│  │   └── Data API: /v1/leaderboard                         │
│  ├── Analysis Functions                                     │
│  │   ├── analyze_sentiment() - Probability distribution     │
│  │   ├── analyze_reversals() - Price swing detection        │
│  │   ├── analyze_insiders() - Conviction signals            │
│  │   └── analyze_resolutions() - Outcome tracking          │
│  └── Template Rendering                                     │
│      └── index.html (Jinja2)                                │
├─────────────────────────────────────────────────────────────┤
│  Frontend (static/)                                         │
│  ├── style.css - Dark theme styling                         │
│  └── script.js - Chart.js visualizations                    │
│      ├── Volume chart (30-day bar)                         │
│      ├── Resolution pie chart                               │
│      └── Probability distribution chart                    │
├─────────────────────────────────────────────────────────────┤
│  Data Flow: API → Cache (5min) → Dashboard                 │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Backend**: Flask 3.1, Python 3.12+
- **Frontend**: Chart.js 4.x, Vanilla JS
- **APIs**: Polymarket Gamma API, Data API
- **Caching**: JSON file cache (5-minute TTL)

## Installation

```bash
# Clone and setup
git clone https://github.com/luisriverag/polymarket_trends.git
cd polymarket_trends

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Open http://localhost:5000

## Data Coverage

- **Active Markets**: ~3,000 fetched, 500 displayed
- **New Markets**: ~1,000 fetched, 15 displayed
- **Closed Markets**: ~2,000 fetched
- **Events**: 50 fetched, 12 displayed

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `gamma-api.polymarket.com/markets` | Market data, prices, volume |
| `gamma-api.polymarket.com/events` | Event categories |
| `data-api.polymarket.com/v1/leaderboard` | Trader rankings |

## Auto-Refresh

Data refreshes automatically every 5 minutes. Click "↻ Refresh" for manual refresh.

## License

MIT
