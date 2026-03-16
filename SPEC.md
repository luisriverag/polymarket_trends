# Polymarket Trend Visualizer - Specification

## Project Overview
- **Project name**: Polymarket Trend Visualizer
- **Type**: Flask web application
- **Core functionality**: Visualize prediction market trends from Polymarket including trading volumes, new markets, and resolution outcomes (underdog analysis)
- **Target users**: Traders, analysts, and prediction market enthusiasts

## UI/UX Specification

### Layout Structure
- **Header**: Fixed top navigation with logo and nav links
- **Hero**: Market summary stats banner
- **Main content**: 
  - Volume trends chart (full width)
  - Two-column layout: New markets table + Resolution analysis
- **Footer**: Minimal with data attribution

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

- **Spacing**: 8px base unit (8, 16, 24, 32, 48)

- **Visual effects**:
  - Cards: subtle border, slight glow on hover
  - Charts: smooth animations
  - Tables: row hover highlighting

### Components
1. **Stat Cards**: Display key metrics (total volume, active markets, avg. volume)
2. **Volume Chart**: Line/bar chart showing daily trading volume over time
3. **New Markets Table**: Recent markets with volume, close date, category
4. **Resolution Analysis**: Pie chart showing Yes vs No resolutions, highlight underdog outcomes
5. **Market Cards**: Individual market display with odds and volume

## Functionality Specification

### Core Features
1. **Volume Trends**: Display trading volume over last 30 days
2. **New Markets Feed**: List of recently created markets sorted by creation date
3. **Resolution Underdog Analysis**: Show markets where the less likely outcome won (high odds at resolution)

### Data Fetching
- Use Polymarket Gamma API: `https://gamma-api.polymarket.com`
- Endpoints:
  - `/markets` - Get all markets with volume, created date
  - `/events` - Get events with market info
  - Query params: `active=true`, `closed=false`, limit, offset

### User Interactions
- View volume chart with hover tooltips
- Sort/filter new markets by volume or date
- Click resolution cards to see market details
- Auto-refresh data every 5 minutes

### Edge Cases
- API timeout: Show cached data with "last updated" timestamp
- No resolved markets: Display message explaining data availability
- Empty results: Show empty state with explanation

## Acceptance Criteria
1. Homepage loads within 3 seconds showing volume chart
2. Volume chart displays last 30 days of data
3. New markets table shows at least 10 recent markets
4. Resolution section shows underdog analysis (markets where outcome had <50% probability at close)
5. All data updates automatically every 5 minutes
6. Responsive design works on mobile devices
7. Dark theme is consistent across all pages
