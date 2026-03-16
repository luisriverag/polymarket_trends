# Polymarket Trend Visualizer - Specification

## Project Overview
- **Project name**: Polymarket Trend Visualizer
- **Type**: Flask web application
- **Core functionality**: Real-time visualization of Polymarket prediction market trends including volumes, new markets, whale activity, price reversals, insider signals, and resolution outcomes
- **Target users**: Traders, analysts, and prediction market enthusiasts

## UI/UX Specification

### Layout Structure
- **Header**: Fixed top navigation with logo and section links
- **Hero**: Market summary stats banner (24h volume, active markets, avg volume, resolved counts)
- **Main content**:
  - Volume trends chart (full width, 30-day bar chart)
  - Hot Events grid (top events by volume)
  - Whale Trackers (two-column: top traders by volume, top holders)
  - Reversals section (price swing detection)
  - Insider Signals (high conviction trades)
  - Two-column: New Markets table + Resolutions with tabs
- **Footer**: Data attribution and auto-refresh info

### Responsive Breakpoints
- Desktop: 1200px+
- Tablet: 768px - 1199px
- Mobile: < 768px

### Visual Design
- **Color Palette**:
  - Background: #0d1117 (dark)
  - Card background: #161b22
  - Primary accent: #58a6ff (blue)
  - Success/Yes: #3fb950 (green)
  - Danger/No: #f85149 (red)
  - Underdog highlight: #d29922 (amber)
  - Text primary: #c9d1d9
  - Text secondary: #8b949e
  - Border: #30363d

- **Typography**:
  - Font family: "JetBrains Mono", "Fira Code", monospace
  - Headings: 700 weight
  - Body: 400 weight, 14px base

- **Spacing**: 8px base unit

- **Visual effects**:
  - Cards: subtle border, glow on hover
  - Charts: smooth animations
  - Tables: row hover highlighting
  - Tab transitions

### Components
1. **Stat Cards**: 5 cards (24h Volume, Active Markets, Avg Volume, Resolved Yes, Resolved No)
2. **Volume Chart**: 30-day bar chart with Chart.js
3. **Hot Events Grid**: 12 event cards with volume
4. **Whale Trackers**: Two columns - Top Traders, Top Holders (10 each)
5. **Reversals Grid**: 15 cards showing price swings (Surging, Crashing, Recovering, Pulling Back)
6. **Insider Signals Grid**: 15 cards with signal type, probability, day change
7. **New Markets Table**: 15 rows with question, category, volume
8. **Resolution Section**: Tabbed interface (Yes, No, Underdogs, Blowouts) + doughnut chart

## Functionality Specification

### Core Features
1. **Volume Trends**: 30-day trading volume chart
2. **Hot Events**: Top 12 events by volume from API
3. **Whale Trackers**: 
   - Top 20 traders from leaderboard API (weekly/monthly/all-time, volume/PnL)
   - Deduplicated by wallet address
4. **Reversals Detection**:
   - Recovering: day < -10% + week > +2%
   - Pulling Back: day > +10% + week < -2%
   - Surging: day > +8%
   - Crashing: day < -8%
   - Min volume: $1000
5. **Insider Signals**:
   - Strong Yes: price > 80%
   - Strong No: price < 20%
   - Hot Yes: price > 65% + positive day change
   - Hot No: price < 35% + negative day change
   - Rising Yes: momentum up
   - Falling No: momentum down
6. **New Markets Feed**: 15 newest markets by creation date
7. **Resolutions**: Tabbed view (Yes/No/Underdogs/Blowouts)

### Data Fetching
- **Gamma API**: `https://gamma-api.polymarket.com`
  - `/markets` - Paginated (200 per page, up to 2000)
  - `/events` - Active events with markets
  - `/tags` - Market categories
- **Data API**: `https://data-api.polymarket.com`
  - `/v1/leaderboard` - Trader rankings
- **Caching**: 5-minute cache with JSON file

### User Interactions
- Volume chart hover tooltips
- Click cards to open market on Polymarket
- Resolution tabs switch between Yes/No/Underdogs/Blowouts
- Refresh button triggers cache clear + reload
- Auto-refresh every 5 minutes

### Edge Cases
- API timeout: Use cached data with timestamp
- Empty results: Show empty state message
- Resolution data unavailable: Show "No data" message (API limitation)

## Data Coverage
- Active markets: ~3000 fetched, 500 displayed
- New markets: ~1000 fetched, 200 displayed  
- Closed markets: ~2000 fetched, 500 displayed
- Events: 100 fetched, 50 displayed

## Acceptance Criteria
1. ✅ Homepage loads within 3 seconds
2. ✅ Volume chart displays 30 days of data
3. ✅ Hot Events shows 12 top events
4. ✅ Whales section shows 10+ traders
5. ✅ Reversals detects price swings (3+ cards showing)
6. ✅ Insiders shows high conviction signals
7. ✅ New markets table shows 15 recent markets
8. ✅ Resolution tabs work correctly
9. ✅ Auto-refresh every 5 minutes
10. ✅ Responsive design for mobile/tablet
11. ✅ Dark theme consistent throughout
12. ✅ GitHub repo updated

## Tech Stack
- Flask 3.1
- Chart.js 4.x
- Polymarket Gamma & Data APIs
- Python 3.12+

## Files
- `app.py` - Main Flask application
- `templates/index.html` - Dashboard template
- `static/style.css` - Styling
- `static/script.js` - Charts and interactions
- `requirements.txt` - Dependencies
- `README.md` - Project documentation
