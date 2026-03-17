import sqlite3
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

app = Flask(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

DB_FILE = "polymarket.db"

MARKET_CACHE_TTL = 180
ANALYSIS_CACHE_TTL = 60
API_CACHE_TTL = 300

_api_cache = {}
_api_cache_time = {}


def is_cache_valid(key):
    if key not in _api_cache or key not in _api_cache_time:
        return False
    return time.time() - _api_cache_time[key] < API_CACHE_TTL


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS analysis_cache (key TEXT PRIMARY KEY, data TEXT, timestamp REAL)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS market_history (id TEXT PRIMARY KEY, question TEXT, slug TEXT, outcome TEXT, end_date TEXT, first_seen TEXT, last_seen TEXT, resolved_at TEXT)"""
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_market_history_slug ON market_history(slug)"""
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_market_history_outcome ON market_history(outcome)"""
    )
    conn.commit()
    conn.close()


def get_db():
    return sqlite3.connect(DB_FILE)


def load_market_cache():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT data, timestamp FROM analysis_cache WHERE key = 'markets'")
        row = c.fetchone()
        conn.close()
        if row and time.time() - row[1] < MARKET_CACHE_TTL:
            import json

            return json.loads(row[0])
    except:
        pass
    return None


def save_market_cache(data):
    try:
        import json

        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO analysis_cache VALUES (?, ?, ?)",
            ("markets", json.dumps(data), time.time()),
        )
        conn.commit()
        conn.close()
    except:
        pass


def load_analysis_cache():
    try:
        import json

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT data, timestamp FROM analysis_cache WHERE key = 'analysis'")
        row = c.fetchone()
        conn.close()
        if row and time.time() - row[1] < ANALYSIS_CACHE_TTL:
            return json.loads(row[0])
    except:
        pass
    return None


def save_analysis_cache(data):
    try:
        import json

        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO analysis_cache VALUES (?, ?, ?)",
            ("analysis", json.dumps(data), time.time()),
        )
        conn.commit()
        conn.close()
    except:
        pass


def load_history():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT id, question, slug, outcome, end_date, first_seen, last_seen, resolved_at FROM market_history"
        )
        rows = c.fetchall()
        conn.close()
        history = {}
        for row in rows:
            history[row[0]] = {
                "question": row[1],
                "slug": row[2],
                "outcome": row[3],
                "end_date": row[4],
                "first_seen": row[5],
                "last_seen": row[6],
                "resolved_at": row[7],
            }
        return history
    except:
        return {}


def save_history(history):
    try:
        conn = get_db()
        c = conn.cursor()
        for m_id, data in history.items():
            c.execute(
                "INSERT OR REPLACE INTO market_history VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    m_id,
                    data.get("question"),
                    data.get("slug"),
                    data.get("outcome"),
                    data.get("end_date"),
                    data.get("first_seen"),
                    data.get("last_seen"),
                    data.get("resolved_at"),
                ),
            )
        conn.commit()
        conn.close()
    except:
        pass


def update_market_history(markets):
    history = load_history()
    now = datetime.now().isoformat()
    for market in markets:
        m_id = market.get("id", "")
        if not m_id:
            continue
        end_date = market.get("endDate", "")
        if m_id not in history:
            history[m_id] = {
                "question": market.get("question", ""),
                "slug": market.get("slug", ""),
                "first_seen": now,
                "end_date": end_date,
            }
        history[m_id]["last_seen"] = now
        is_resolved = (
            market.get("closed") == True
            and market.get("umaResolutionStatus") == "resolved"
        )
        if is_resolved:
            outcome_prices = parse_prices(market.get("outcomePrices"))
            outcome = None
            if len(outcome_prices) >= 2:
                if outcome_prices[0] >= 0.99:
                    outcome = "Yes"
                elif outcome_prices[1] >= 0.99:
                    outcome = "No"
            if outcome:
                history[m_id]["outcome"] = outcome
                history[m_id]["resolved_at"] = now
    save_history(history)
    return history


def fetch_with_retry(url, params=None, max_retries=3, timeout=30):
    cache_key = f"{url}?{str(params)}" if params else url
    if is_cache_valid(cache_key):
        return _api_cache[cache_key]
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
            _api_cache[cache_key] = result
            _api_cache_time[cache_key] = time.time()
            return result
        except:
            if attempt < max_retries - 1:
                time.sleep(1)
    return None


def fetch_clob_markets():
    try:
        markets = []
        cursor = ""
        for _ in range(20):
            data = fetch_with_retry(
                f"{CLOB_API}/markets", {"next_cursor": cursor} if cursor else None
            )
            if not data or not data.get("data"):
                break
            markets.extend(data["data"])
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return markets
    except:
        return []


def get_market_resolution(market_data):
    tokens = market_data.get("tokens", [])
    for token in tokens:
        if token.get("winner"):
            return token.get("outcome", "Yes")
    return None


def parse_prices(prices_str):
    import json

    if not prices_str:
        return []
    try:
        if isinstance(prices_str, str):
            return [float(p) for p in json.loads(prices_str)]
        return [float(p) for p in prices_str]
    except:
        return []


def build_market_url(market):
    slug = market.get("slug", "")
    market_id = market.get("id", "")
    if slug:
        return f"https://polymarket.com/market/{slug}"
    elif market_id:
        return f"https://polymarket.com/market?id={market_id}"
    return "#"


def get_yes_price(market):
    prices = parse_prices(market.get("outcomePrices"))
    if prices:
        return prices[0]
    return 0.5


init_db()


def fetch_markets():
    cached = load_market_cache()
    if cached:
        return cached

    try:
        all_markets = []
        seen_ids = set()

        for offset in range(0, 20000, 200):
            params = {"closed": "false", "limit": 200, "offset": offset}
            batch = fetch_with_retry(f"{GAMMA_API}/markets", params=params)
            if not batch:
                continue
            for m in batch:
                if m.get("id") not in seen_ids:
                    seen_ids.add(m.get("id"))
                    all_markets.append(m)
            if len(batch) < 200:
                break

        all_new_markets = sorted(
            all_markets, key=lambda m: m.get("createdAt", ""), reverse=True
        )[:1000]

        all_closed_markets = []
        for offset in range(0, 5000, 200):
            params = {"closed": "true", "limit": 200, "offset": offset}
            try:
                batch = fetch_with_retry(f"{GAMMA_API}/markets", params=params)
                if not batch:
                    break
                all_closed_markets.extend(batch)
                if len(batch) < 200:
                    break
            except:
                break

        events = (
            fetch_with_retry(
                f"{GAMMA_API}/events",
                {"active": "true", "closed": "false", "limit": 100},
            )
            or []
        )

        import json

        data = {
            "markets": all_markets[:10000],
            "new_markets": all_new_markets[:1000],
            "closed_markets": all_closed_markets[:10000],
            "events": events[:100],
            "raw_markets": all_markets,
            "fetched_at": datetime.now().isoformat(),
        }
        save_market_cache(data)

        all_for_history = all_markets + all_closed_markets
        update_market_history(all_for_history)

        return data

    except Exception as e:
        print(f"Error fetching markets: {e}")
        return load_market_cache() or {
            "markets": [],
            "new_markets": [],
            "closed_markets": [],
            "events": [],
            "fetched_at": None,
        }


def calculate_volume_history(markets):
    volume_by_cat = {}
    total_24h = 0
    for market in markets:
        vol = float(market.get("volume24hr") or 0)
        total_24h += vol
        cat = market.get("category") or (
            market.get("tags", ["Other"])[0] if market.get("tags") else "Other"
        )
        volume_by_cat[cat] = volume_by_cat.get(cat, 0) + vol
    sorted_cats = sorted(volume_by_cat.items(), key=lambda x: x[1], reverse=True)[:8]
    return {"total_24h": total_24h, "by_category": sorted_cats}


def analyze_underdogs(closed_markets):
    underdogs = []
    for market in closed_markets:
        try:
            volume = float(market.get("volume", 0) or 0)
            if volume > 1000:
                prices = parse_prices(market.get("outcomePrices"))
                if prices and prices[0] < 0.3:
                    underdogs.append(
                        {
                            "question": market.get("question", "")[:55],
                            "volume": volume,
                            "price": prices[0] * 100,
                            "url": build_market_url(market),
                        }
                    )
        except:
            continue
    return sorted(underdogs, key=lambda x: x["price"])[:15]


def analyze_reversals(markets):
    reversals = []
    for market in markets:
        try:
            day_change = float(market.get("oneDayPriceChange", 0) or 0)
            week_change = float(market.get("oneWeekPriceChange", 0) or 0)
            volume = float(market.get("volume24hr", 0) or 0)
            if volume > 1000:
                reversal_score = 0
                direction = ""
                if day_change < -0.10 and week_change > 0.02:
                    reversal_score = abs(day_change) + abs(week_change)
                    direction = "↩️ Recovering"
                elif day_change > 0.10 and week_change < -0.02:
                    reversal_score = abs(day_change) + abs(week_change)
                    direction = "↪️ Pulling Back"
                elif day_change > 0.08:
                    reversal_score = abs(day_change)
                    direction = "🚀 Surging"
                elif day_change < -0.08:
                    reversal_score = abs(day_change)
                    direction = "💥 Crashing"
                if reversal_score > 0.05:
                    reversals.append(
                        {
                            "question": market.get("question", "")[:55],
                            "day_change": day_change * 100,
                            "week_change": week_change * 100,
                            "volume": volume,
                            "price": get_yes_price(market) * 100,
                            "direction": direction,
                            "url": build_market_url(market),
                        }
                    )
        except:
            continue
    return sorted(reversals, key=lambda x: abs(x["day_change"]), reverse=True)[:15]


def analyze_insiders(markets):
    insiders = []
    for market in markets:
        try:
            volume = float(market.get("volume24hr", 0) or 0)
            liquidity = float(market.get("liquidity", 0) or 0)
            if volume > 50000 and liquidity > 100000:
                price = get_yes_price(market)
                if 0.4 < price < 0.6:
                    insiders.append(
                        {
                            "question": market.get("question", "")[:55],
                            "volume": volume,
                            "price": price * 100,
                            "liquidity": liquidity,
                            "url": build_market_url(market),
                        }
                    )
        except:
            continue
    return sorted(insiders, key=lambda x: x["volume"], reverse=True)[:10]


def analyze_categories(markets):
    categories = {}
    for market in markets:
        cat = market.get("category") or (
            market.get("tags", ["Other"])[0] if market.get("tags") else "Other"
        )
        vol = float(market.get("volume24hr") or 0)
        categories[cat] = categories.get(cat, 0) + vol
    return sorted(categories.items(), key=lambda x: x[1], reverse=True)


def analyze_sentiment(markets):
    sentiment = {"bullish": 0, "bearish": 0, "neutral": 0, "overall": 0.5}
    total = 0
    distribution = {
        "0-10%": 0,
        "10-20%": 0,
        "20-30%": 0,
        "30-40%": 0,
        "40-50%": 0,
        "50-60%": 0,
        "60-70%": 0,
        "70-80%": 0,
        "80-90%": 0,
        "90-100%": 0,
    }
    for market in markets:
        price = get_yes_price(market)
        sentiment["overall"] += price
        total += 1
        if price > 0.6:
            sentiment["bullish"] += 1
        elif price < 0.4:
            sentiment["bearish"] += 1
        else:
            sentiment["neutral"] += 1

        bucket = int(price * 10)
        bucket = min(bucket, 9)
        bucket_labels = [
            "0-10%",
            "10-20%",
            "20-30%",
            "30-40%",
            "40-50%",
            "50-60%",
            "60-70%",
            "70-80%",
            "80-90%",
            "90-100%",
        ]
        distribution[bucket_labels[bucket]] += 1

    if total > 0:
        sentiment["overall"] = sentiment["overall"] / total
    sentiment["distribution"] = distribution
    return sentiment


def process_events(events, markets):
    event_data = []
    for event in events:
        question = event.get("title") or event.get("question") or "Unknown Event"
        volumes = event.get("volume")
        try:
            if volumes is None:
                total_vol = 0
            elif isinstance(volumes, dict):
                total_vol = sum(float(v) for v in volumes.values()) if volumes else 0
            elif isinstance(volumes, (int, float)):
                total_vol = float(volumes)
            else:
                total_vol = 0
        except:
            total_vol = 0

        slug = event.get("slug", "")
        market_id = event.get("id", "")

        if slug:
            url = f"https://polymarket.com/event/{slug}"
        elif market_id:
            url = f"https://polymarket.com/event?id={market_id}"
        else:
            event_markets = event.get("markets", [])
            url = "#"
            for m in event_markets:
                if isinstance(m, dict):
                    m_slug = m.get("slug", "")
                    if m_slug:
                        url = f"https://polymarket.com/market/{m_slug}"
                        break

        event_data.append(
            {"question": question[:70], "slug": slug, "volume": total_vol, "url": url}
        )
    return sorted(event_data, key=lambda x: x["volume"], reverse=True)[:15]


def fetch_leaderboard():
    try:
        data = fetch_with_retry(
            f"{DATA_API}/v1/leaderboard", {"limit": 50, "orderBy": "PNL"}
        )
        return (
            data
            if isinstance(data, list)
            else data.get("leaderboard", [])
            if data
            else []
        )
    except:
        return []


def fetch_leaderboard_by_volume():
    try:
        data = fetch_with_retry(
            f"{DATA_API}/v1/leaderboard", {"limit": 50, "orderBy": "VOL"}
        )
        return (
            data
            if isinstance(data, list)
            else data.get("leaderboard", [])
            if data
            else []
        )
    except:
        return []


def fetch_top_holders():
    try:
        data = fetch_with_retry(f"{DATA_API}/top-holders", {"limit": 20})
        return data.get("topHolders", []) if data else []
    except:
        return []


def analyze_resolutions(closed_markets, active_markets):
    import re

    resolutions = {"resolved": [], "pending": []}
    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)

    clob_markets = fetch_clob_markets()
    clob_by_slug = {}
    clob_by_question = {}
    for m in clob_markets:
        slug = m.get("market_slug", "")
        if slug:
            clob_by_slug[slug] = m
        q = m.get("question", "").lower()
        if q:
            clob_by_question[q] = m

    history = load_history()

    all_markets = closed_markets + active_markets

    for market in all_markets:
        try:
            m_id = market.get("id", "")
            question = market.get("question", "Unknown")
            slug = market.get("slug", "")
            volume = float(market.get("volume", 0) or 0)
            end_date = market.get("endDate", "")

            is_closed = market.get("closed") == True
            is_resolved_api = market.get("umaResolutionStatus") == "resolved"

            outcome = None
            outcome_prices = parse_prices(market.get("outcomePrices"))
            has_prices = len(outcome_prices) >= 2

            if has_prices:
                if outcome_prices[0] > 0.5 and outcome_prices[0] > outcome_prices[1]:
                    outcome = "Yes"
                elif outcome_prices[1] > 0.5 and outcome_prices[1] > outcome_prices[0]:
                    outcome = "No"

            if not outcome:
                if slug and slug in clob_by_slug:
                    outcome = get_market_resolution(clob_by_slug[slug])
                elif question.lower() in clob_by_question:
                    outcome = get_market_resolution(clob_by_question[question.lower()])

            if not outcome and m_id in history:
                outcome = history[m_id].get("outcome", "")

            if not outcome:
                continue

            close_price = get_yes_price(market)

            is_repeat = False
            date_patterns = [
                r"january|february|march|april|may|june|july|august|september|october|november|december",
                r"\d{4}",
                r"week\s*\d+",
                r"month\s*\d+",
            ]
            question_lower = question.lower()
            for pattern in date_patterns:
                if re.search(pattern, question_lower):
                    is_repeat = True
                    break

            if is_closed or is_resolved_api:
                resolutions["resolved"].append(
                    {
                        "question": question[:60],
                        "volume": volume,
                        "close_price": close_price * 100,
                        "outcome": outcome,
                        "resolved_date": end_date[:10] if end_date else "",
                        "is_repeat": is_repeat,
                        "url": build_market_url(market),
                    }
                )
        except Exception as e:
            print(f"Error processing market: {e}")
            continue

    for market in active_markets:
        try:
            question = market.get("question", "Unknown")
            volume = float(market.get("volume", 0) or 0)
            end_date = market.get("endDate", "")
            outcome = market.get("outcome", "")

            if outcome:
                continue
            if not end_date:
                continue

            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                end_date_naive = end_dt.replace(tzinfo=None)
                days_until_end = (end_date_naive - now).days
            except:
                continue

            if end_date_naive > now and days_until_end > 7:
                continue

            close_price = get_yes_price(market)

            is_repeat = False
            date_patterns = [
                r"january|february|march|april|may|june|july|august|september|october|november|december",
                r"\d{4}",
                r"week\s*\d+",
                r"month\s*\d+",
            ]
            question_lower = question.lower()
            for pattern in date_patterns:
                if re.search(pattern, question_lower):
                    is_repeat = True
                    break

            is_upcoming = end_date_naive > now

            resolutions["pending"].append(
                {
                    "question": question[:60],
                    "volume": volume,
                    "close_price": close_price * 100,
                    "end_date": end_date[:10],
                    "is_repeat": is_repeat,
                    "is_upcoming": is_upcoming,
                    "url": build_market_url(market),
                }
            )
        except Exception as e:
            print(f"Error processing pending: {e}")
            continue

    resolutions["resolved"] = sorted(
        resolutions["resolved"], key=lambda x: x["volume"], reverse=True
    )[:50]
    resolutions["pending"] = sorted(
        resolutions["pending"], key=lambda x: x["volume"], reverse=True
    )[:50]
    resolutions["resolved_by_date"] = sorted(
        resolutions["resolved"], key=lambda x: x.get("resolved_date", ""), reverse=True
    )[:50]
    resolutions["pending_by_date"] = sorted(
        resolutions["pending"], key=lambda x: x.get("end_date", ""), reverse=True
    )[:50]

    save_history(history)

    return resolutions


@app.route("/")
def index():
    cached_data = load_market_cache()
    cached_analysis = load_analysis_cache()

    if cached_data and cached_analysis:
        markets = cached_data.get("markets", [])
        total_volume = sum(
            float(m.get("volume24hr") or m.get("volume") or 0) for m in markets
        )
        active_markets = len(markets)
        avg_volume = total_volume / active_markets if active_markets > 0 else 0

        return render_template(
            "index.html",
            markets=markets,
            volume_history=cached_analysis.get("volume_history"),
            total_volume=total_volume,
            active_markets=active_markets,
            avg_volume=avg_volume,
            categories=cached_analysis.get("categories"),
            sentiment=cached_analysis.get("sentiment"),
            new_markets=cached_analysis.get("new_markets"),
            reversals=cached_analysis.get("reversed_markets", []),
            insider_signals=cached_analysis.get("insider_markets", []),
            leaderboard=cached_analysis.get("leaderboard"),
            top_holders=cached_analysis.get("top_holders"),
            events=cached_analysis.get("events"),
            resolutions=cached_analysis.get("resolutions"),
            closed_stats=cached_analysis.get("closed_stats"),
            fetched_at=cached_data.get("fetched_at"),
        )

    data = fetch_markets()
    volume_history = calculate_volume_history(data.get("markets", []))
    underdogs = analyze_underdogs(data.get("closed_markets", []))

    total_volume = sum(
        float(m.get("volume24hr") or m.get("volume") or 0)
        for m in data.get("markets", [])
    )
    active_markets = len(data.get("markets", []))
    avg_volume = total_volume / active_markets if active_markets > 0 else 0

    new_markets_data = []
    for m in data.get("new_markets", [])[:15]:
        vol_24hr = m.get("volume24hr")
        vol_total = m.get("volume")
        volume = float(vol_24hr if vol_24hr else (vol_total if vol_total else 0))
        new_markets_data.append(
            {
                "question": m.get("question", "Unknown")[:60],
                "volume": volume,
                "vol": m.get("vol", 0),
                "category": m.get("category")
                or (m.get("tags", ["General"])[0] if m.get("tags") else "General"),
                "end_date": m.get("endDate", ""),
                "url": build_market_url(m),
            }
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        leaderboard_future = executor.submit(fetch_leaderboard)
        top_holders_future = executor.submit(fetch_top_holders)

        leaderboard = leaderboard_future.result()
        top_holders = top_holders_future.result()

    reversals = analyze_reversals(data.get("markets", []))
    insiders = analyze_insiders(data.get("markets", []))
    resolutions = analyze_resolutions(
        data.get("closed_markets", []), data.get("markets", [])
    )

    closed_stats = {
        "yes_resolved": len(
            [
                r
                for r in resolutions.get("resolved", [])
                if r.get("outcome") in ["Yes", "yes"]
            ]
        ),
        "no_resolved": len(
            [
                r
                for r in resolutions.get("resolved", [])
                if r.get("outcome") in ["No", "no"]
            ]
        ),
        "total": len(resolutions.get("resolved", [])),
    }
    categories = analyze_categories(data.get("markets", []))
    sentiment = analyze_sentiment(data.get("markets", []))

    leaderboard_data = []
    for i, trader in enumerate(leaderboard):
        addr = trader.get("proxyWallet", "")
        vol = float(trader.get("vol", 0) or 0)
        pnl = float(trader.get("pnl", 0) or 0)
        rank = int(trader.get("rank", i + 1)) if trader.get("rank") else (i + 1)
        profile = trader.get("profile", {})
        win_rate = profile.get("winRate") if profile else None

        leaderboard_data.append(
            {
                "rank": rank,
                "address": addr[:10] + "..." if addr else "Unknown",
                "full_address": addr,
                "username": trader.get("userName", ""),
                "volume": vol,
                "pnl": pnl,
                "win_rate": win_rate,
                "url": f"https://polymarket.com/profile/{addr}" if addr else "#",
            }
        )

    events_data = process_events(data.get("events", []), data.get("markets", []))

    top_holder_data = []
    for holder in top_holders:
        addr = holder.get("address", "")
        top_holder_data.append(
            {
                "address": addr[:10] + "..." if addr else "Unknown",
                "volume": float(holder.get("volume", 0) or 0),
                "url": f"https://polymarket.com/profile/{addr}" if addr else "#",
            }
        )

    liquidity_analysis = []
    for market in data.get("markets", [])[:10]:
        liquidity_analysis.append(
            {
                "question": market.get("question", "")[:45],
                "liquidity": float(market.get("liquidity", 0) or 0),
                "volume": float(market.get("volume24hr", 0) or 0),
                "url": build_market_url(market),
            }
        )

    analysis_data = {
        "volume_history": volume_history,
        "categories": categories,
        "sentiment": sentiment,
        "new_markets": new_markets_data,
        "reversed_markets": reversals,
        "insider_markets": insiders,
        "leaderboard": leaderboard_data,
        "top_holders": top_holder_data,
        "events": events_data,
        "resolutions": resolutions,
        "closed_stats": closed_stats,
    }
    save_analysis_cache(analysis_data)

    return render_template(
        "index.html",
        volume_history=volume_history,
        total_volume=total_volume,
        active_markets=active_markets,
        avg_volume=avg_volume,
        new_markets=new_markets_data,
        underdogs=underdogs,
        closed_stats=closed_stats,
        leaderboard=leaderboard_data,
        top_holders=top_holder_data,
        insider_signals=insiders,
        reversals=reversals,
        resolutions=resolutions,
        categories=categories,
        events=events_data,
        liquidity_analysis=liquidity_analysis,
        sentiment=sentiment,
        fetched_at=data.get("fetched_at"),
    )


@app.route("/api/refresh")
def refresh():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM analysis_cache")
        conn.commit()
        conn.close()
        _api_cache.clear()
    except:
        pass
    return jsonify({"status": "cache cleared"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
