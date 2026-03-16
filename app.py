import os
import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify
import time
import threading

app = Flask(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

MARKET_CACHE_FILE = "market_cache.json"
ANALYSIS_CACHE_FILE = "analysis_cache.json"
HISTORY_FILE = "market_history.json"

MARKET_CACHE_TTL = 180  # 3 minutes for market data
ANALYSIS_CACHE_TTL = 60  # 1 minute for analysis

_api_cache = {}
_analysis_cache = {}

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

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
        
        is_resolved = market.get("closed") == True and market.get("umaResolutionStatus") == "resolved"
        if is_resolved:
            outcome_prices = parse_prices(market.get("outcomePrices"))
            outcome = None
            if len(outcome_prices) >= 2:
                if outcome_prices[0] == 1.0:
                    outcome = "Yes"
                elif outcome_prices[1] == 1.0:
                    outcome = "No"
            if outcome:
                history[m_id]["outcome"] = outcome
                history[m_id]["resolved_at"] = now
    
    save_history(history)
    return history

def load_market_cache():
    try:
        if os.path.exists(MARKET_CACHE_FILE):
            with open(MARKET_CACHE_FILE, "r") as f:
                data = json.load(f)
                if time.time() - data.get("timestamp", 0) < MARKET_CACHE_TTL:
                    return data.get("data")
    except:
        pass
    return None

def save_market_cache(data):
    with open(MARKET_CACHE_FILE, "w") as f:
        json.dump({"timestamp": time.time(), "data": data}, f)

def load_analysis_cache():
    try:
        if os.path.exists(ANALYSIS_CACHE_FILE):
            with open(ANALYSIS_CACHE_FILE, "r") as f:
                data = json.load(f)
                if time.time() - data.get("timestamp", 0) < ANALYSIS_CACHE_TTL:
                    return data.get("data")
    except:
        pass
    return None

def save_analysis_cache(data):
    with open(ANALYSIS_CACHE_FILE, "w") as f:
        json.dump({"timestamp": time.time(), "data": data}, f)

def fetch_with_retry(url, params=None, max_retries=3, timeout=30):
    cache_key = f"{url}?{json.dumps(params, sort_keys=True)}" if params else url
    
    if cache_key in _api_cache:
        return _api_cache[cache_key]
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
            _api_cache[cache_key] = result
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)

def fetch_clob_markets():
    """Fetch markets from CLOB API which has resolution data"""
    try:
        markets = []
        cursor = ""
        for _ in range(50):  # Get up to 50 pages
            data = fetch_with_retry(f"{CLOB_API}/markets", {"next_cursor": cursor} if cursor else None)
            if not data or not data.get("data"):
                break
            markets.extend(data["data"])
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return markets
    except Exception as e:
        print(f"Error fetching CLOB markets: {e}")
        return []

def get_market_resolution(market_data):
    """Extract resolution outcome from CLOB market data"""
    tokens = market_data.get("tokens", [])
    for token in tokens:
        if token.get("winner"):
            return token.get("outcome", "Yes")
    return None

def fetch_markets():
    cached = load_market_cache()
    if cached:
        return cached
    
    try:
        all_markets = []
        seen_ids = set()
        
        print("Fetching active markets...")
        for offset in range(0, 20000, 200):
            params = {
                "closed": "false",
                "limit": 200,
                "offset": offset
            }
            batch = fetch_with_retry(f"{GAMMA_API}/markets", params=params)
            if not batch:
                continue
            for m in batch:
                if m.get("id") not in seen_ids:
                    seen_ids.add(m.get("id"))
                    all_markets.append(m)
            print(f"  Active offset {offset}: {len(batch)} markets")
            if len(batch) < 200:
                break
        
        POPULAR_TAGS = ["Politics", "Sports", "Crypto", "Tech", "Elections", "US politics", 
                       "Trump", "Global Politics", "AI", "Business", "Entertainment",
                       "Science", "Climate & Weather", "Economics", "Finance", "Music",
                       "Film & TV", "Celebrities", "Soccer", "Basketball", "Football",
                       "Baseball", "Hockey", "Tennis", "Golf", "Boxing/MMA", "Olympics",
                       "Elections 2024", "Elections 2028", "World Elections", "Wars"]
        
        print(f"Fetching markets by {len(POPULAR_TAGS)} tags...")
        for tag in POPULAR_TAGS:
            params_tag = {
                "closed": "false",
                "limit": 100,
                "tag": tag
            }
            try:
                resp_tag = requests.get(f"{GAMMA_API}/markets", params=params_tag, timeout=15)
                if resp_tag.status_code == 200:
                    batch = resp_tag.json()
                    new_count = 0
                    for m in batch:
                        if m.get("id") not in seen_ids:
                            seen_ids.add(m.get("id"))
                            all_markets.append(m)
                            new_count += 1
                    if new_count > 0:
                        print(f"  Tag '{tag}': +{new_count} new markets")
            except:
                continue
        
        print("Fetching events...")
        events = []
        try:
            params_events = {
                "active": "true",
                "closed": "false",
                "limit": 100
            }
            resp_events = requests.get(f"{GAMMA_API}/events", params=params_events, timeout=30)
            if resp_events.status_code == 200:
                events = resp_events.json()
                for event in events:
                    for m in event.get("markets", []):
                        if isinstance(m, dict) and m.get("id") not in seen_ids:
                            seen_ids.add(m.get("id"))
                            all_markets.append(m)
                print(f"  Events: {len(events)} events processed")
        except Exception as e:
            print(f"  Error fetching events: {e}")
            events = []
        
        print("Fetching new markets...")
        all_new_markets = []
        new_seen = set()
        for offset in range(0, 1000, 200):
            params_new = {
                "closed": "false",
                "limit": 200,
                "offset": offset,
                "sortBy": "createdAt"
            }
            try:
                resp_new = requests.get(f"{GAMMA_API}/markets", params=params_new, timeout=30)
                if resp_new.status_code != 200:
                    break
                batch = resp_new.json()
                if not batch:
                    break
                for m in batch:
                    if m.get("id") not in new_seen:
                        new_seen.add(m.get("id"))
                        all_new_markets.append(m)
                print(f"  New offset {offset}: {len(batch)} markets")
                if len(batch) < 200:
                    break
            except:
                break
        
        print("Fetching closed markets...")
        all_closed_markets = []
        for offset in range(0, 3000, 200):
            params_closed = {
                "closed": "true",
                "limit": 200,
                "offset": offset
            }
            try:
                batch = fetch_with_retry(f"{GAMMA_API}/markets", params=params_closed)
                if not batch:
                    continue
                all_closed_markets.extend(batch)
                print(f"  Closed offset {offset}: {len(batch)} markets")
                if len(batch) < 200:
                    break
            except:
                break
        
        print(f"\\nTotal: {len(all_markets)} active, {len(all_new_markets)} new, {len(all_closed_markets)} closed")
        
        data = {
            "markets": all_markets[:10000],
            "new_markets": all_new_markets[:1000],
            "closed_markets": all_closed_markets[:10000],
            "events": events[:100],
            "raw_markets": all_markets,
            "fetched_at": datetime.now().isoformat()
        }
        save_market_cache(data)
        
        # Update historical tracking
        all_for_history = all_markets + all_closed_markets
        update_market_history(all_for_history)
        
        return data
    except Exception as e:
        print(f"Error fetching markets: {e}")
        import traceback
        traceback.print_exc()
        return load_market_cache() or {"markets": [], "new_markets": [], "closed_markets": [], "events": [], "fetched_at": None}

def calculate_volume_history(markets):
    volume_by_cat = {}
    total_24h = 0
    
    keywords = {
        "Politics": ["trump", "biden", "election", "congress", "senate", "president", "political", "democrat", "republican", "ukraine", "russia", "china", "taiwan"],
        "Crypto": ["bitcoin", "btc", "eth", "crypto", "ether", "solana", "dogecoin", "polymarket"],
        "Sports": ["nba", "nfl", "nhl", "soccer", "football", "tennis", "golf", "olympics", "mvp", "champion", "qualify"],
        "Tech": ["ai", "openai", "google", "apple", "microsoft", "meta", "tesla", "launch", "product"],
        "Entertainment": ["album", "music", "movie", "gta", "film", "celebrity", "star", "bond", "release"],
        "Business": ["stock", "market", "economy", "fed", "interest", "recession", "company", "acquisition"],
        "Science": ["climate", "weather", "space", "pandemic", "vaccine", "health"],
        "World": ["will", "happen", "before", "after"]
    }
    
    for market in markets:
        try:
            vol_24h = float(market.get("volume24hr", 0) or 0)
            total_24h += vol_24h
            
            q = market.get("question", "").lower()
            
            assigned = False
            for cat, kws in keywords.items():
                for kw in kws:
                    if kw in q:
                        if cat not in volume_by_cat:
                            volume_by_cat[cat] = 0
                        volume_by_cat[cat] += vol_24h
                        assigned = True
                        break
                if assigned:
                    break
            
            if not assigned:
                if "Other" not in volume_by_cat:
                    volume_by_cat["Other"] = 0
                volume_by_cat["Other"] += vol_24h
        except:
            continue
    
    top_cats = sorted(volume_by_cat.items(), key=lambda x: x[1], reverse=True)[:8]
    
    return {
        "total_24h": total_24h,
        "by_category": top_cats
    }

def analyze_underdogs(closed_markets):
    underdogs = []
    for market in closed_markets:
        try:
            resolution = market.get("outcome")
            if not resolution:
                continue
            
            if resolution == "Yes":
                no_price = market.get("noPrice") or market.get("NoPrice")
                if no_price and float(no_price) > 0.5:
                    underdogs.append({
                        "question": market.get("question", "Unknown"),
                        "outcome": resolution,
                        "probability": (1 - float(no_price)) * 100,
                        "volume": market.get("volume", 0),
                        "end_date": market.get("endDate", "")
                    })
            else:
                yes_price = market.get("yesPrice") or market.get("YesPrice")
                if yes_price and float(yes_price) > 0.5:
                    underdogs.append({
                        "question": market.get("question", "Unknown"),
                        "outcome": resolution,
                        "probability": (1 - float(yes_price)) * 100,
                        "volume": market.get("volume", 0),
                        "end_date": market.get("endDate", "")
                    })
        except:
            continue
    
    return underdogs[:15]

def fetch_leaderboard():
    try:
        all_traders = []
        for period in ["WEEK", "MONTH", "ALL"]:
            for order in ["VOL", "PNL"]:
                params = {"limit": 20, "timePeriod": period, "orderBy": order}
                resp = requests.get(f"{DATA_API}/v1/leaderboard", params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        for t in data:
                            t["period"] = period
                            t["order"] = order
                        all_traders.extend(data)
        
        seen = set()
        unique_traders = []
        for t in all_traders:
            addr = t.get("proxyWallet", "")
            if addr and addr not in seen:
                seen.add(addr)
                unique_traders.append(t)
        
        return unique_traders[:50]
    except Exception as e:
        print(f"Error fetching leaderboard: {e}")
        return []

def fetch_top_holders():
    return []

def parse_prices(prices_data):
    if not prices_data:
        return []
    try:
        if isinstance(prices_data, str):
            prices_data = json.loads(prices_data)
        return [float(p) for p in prices_data]
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
    outcome_prices = parse_prices(market.get("outcomePrices"))
    if outcome_prices and len(outcome_prices) > 0:
        return outcome_prices[0]
    val = market.get("yesPrice")
    if val:
        try:
            return float(val)
        except:
            pass
    return 0.5

def get_no_price(market):
    outcome_prices = parse_prices(market.get("outcomePrices"))
    if outcome_prices and len(outcome_prices) > 1:
        return outcome_prices[1]
    val = market.get("noPrice")
    if val:
        try:
            return float(val)
        except:
            pass
    return 0.5

def analyze_reversals(markets):
    reversals = []
    for market in markets:
        try:
            day_change = float(market.get("oneDayPriceChange", 0) or 0)
            week_change = float(market.get("oneWeekPriceChange", 0) or 0)
            volume = float(market.get("volume24hr", 0) or 0)
            current_price = get_yes_price(market)
            
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
                    slug = market.get("slug", "")
                    market_id = market.get("id", "")
                    
                    # Build URL - prefer slug, fallback to id
                    if slug:
                        url = f"https://polymarket.com/market/{slug}"
                    elif market_id:
                        url = f"https://polymarket.com/market?id={market_id}"
                    else:
                        url = "#"
                    
                    reversals.append({
                        "question": market.get("question", "Unknown")[:55],
                        "day_change": day_change * 100,
                        "week_change": week_change * 100,
                        "volume": volume,
                        "price": current_price * 100,
                        "direction": direction,
                        "url": url
                    })
        except:
            continue
    return sorted(reversals, key=lambda x: abs(x["day_change"]), reverse=True)[:15]

def analyze_sentiment(markets):
    sentiment_data = {
        "overall": 0,
        "count": 0,
        "bullish": 0,
        "bearish": 0,
        "neutral": 0,
        "categories": {},
        "hot_takes": [],
        "distribution": {"0-10": 0, "10-20": 0, "20-30": 0, "30-40": 0, "40-50": 0, "50-60": 0, "60-70": 0, "70-80": 0, "80-90": 0, "90-100": 0}
    }
    
    for market in markets:
        try:
            volume = float(market.get("volume24hr", 0) or 0)
            current_price = get_yes_price(market)
            day_change = float(market.get("oneDayPriceChange", 0) or 0)
            
            prob = current_price * 100
            if prob < 10:
                sentiment_data["distribution"]["0-10"] += 1
            elif prob < 20:
                sentiment_data["distribution"]["10-20"] += 1
            elif prob < 30:
                sentiment_data["distribution"]["20-30"] += 1
            elif prob < 40:
                sentiment_data["distribution"]["30-40"] += 1
            elif prob < 50:
                sentiment_data["distribution"]["40-50"] += 1
            elif prob < 60:
                sentiment_data["distribution"]["50-60"] += 1
            elif prob < 70:
                sentiment_data["distribution"]["60-70"] += 1
            elif prob < 80:
                sentiment_data["distribution"]["70-80"] += 1
            elif prob < 90:
                sentiment_data["distribution"]["80-90"] += 1
            else:
                sentiment_data["distribution"]["90-100"] += 1
            
            sentiment_data["count"] += 1
            sentiment_data["overall"] += current_price
            
            if current_price > 0.6:
                sentiment_data["bullish"] += 1
            elif current_price < 0.4:
                sentiment_data["bearish"] += 1
            else:
                sentiment_data["neutral"] += 1
            
            if volume > 5000 and abs(day_change) > 0.05:
                direction = "📈" if day_change > 0 else "📉"
                sentiment_data["hot_takes"].append({
                    "question": market.get("question", "Unknown")[:50],
                    "price": current_price * 100,
                    "change": day_change * 100,
                    "direction": direction,
                    "url": build_market_url(market)
                })
        except:
            continue
    
    sentiment_data["hot_takes"] = sentiment_data["hot_takes"][:10]
    
    if sentiment_data["count"] > 0:
        sentiment_data["overall"] = sentiment_data["overall"] / sentiment_data["count"]
    else:
        sentiment_data["overall"] = 0.5
    
    return sentiment_data

def analyze_insiders(markets):
    insiders = []
    for market in markets:
        try:
            volume = float(market.get("volume24hr", 0) or 0)
            liquidity = float(market.get("liquidity", 0) or 0)
            current_price = get_yes_price(market)
            day_change = float(market.get("oneDayPriceChange", 0) or 0)
            
            if volume > 500:
                signal = ""
                conviction = 0
                
                if current_price > 0.75:
                    signal = "Strong Yes"
                    conviction = current_price
                elif current_price < 0.25:
                    signal = "Strong No"
                    conviction = 1 - current_price
                elif current_price > 0.60:
                    signal = "Hot Yes"
                    conviction = current_price * 0.5
                elif current_price < 0.40:
                    signal = "Hot No"
                    conviction = (1 - current_price) * 0.5
                elif day_change > 0.02:
                    signal = "Rising"
                    conviction = day_change * 20
                elif day_change < -0.02:
                    signal = "Falling"
                    conviction = abs(day_change) * 20
                
                if signal and conviction > 0.15:
                    insiders.append({
                        "question": market.get("question", "Unknown")[:55],
                        "signal": signal,
                        "conviction": conviction,
                        "probability": current_price * 100,
                        "volume": volume,
                        "liquidity": liquidity,
                        "day_change": day_change * 100,
                        "url": build_market_url(market)
                    })
        except:
            continue
    return sorted(insiders, key=lambda x: x["conviction"], reverse=True)[:15]

def analyze_resolutions(closed_markets, active_markets):
    from datetime import datetime, timedelta
    import re
    resolutions = {
        "resolved": [],
        "pending": []
    }
    
    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)
    
    # Load CLOB markets for resolution data
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
    
    # Load history to find resolved markets
    history = load_history()
    
    # Process all markets for resolved outcomes
    for market in closed_markets + active_markets:
        try:
            m_id = market.get("id", "")
            question = market.get("question", "Unknown")
            slug = market.get("slug", "")
            volume = float(market.get("volume", 0) or 0)
            end_date = market.get("endDate", "")
            
            # Check for resolution via API fields
            is_resolved = market.get("closed") == True and market.get("umaResolutionStatus") == "resolved"
            outcome = None
            
            if is_resolved:
                # Infer outcome from outcomePrices: ["0", "1"] = Yes won, ["1", "0"] = No won
                outcome_prices = parse_prices(market.get("outcomePrices"))
                if len(outcome_prices) >= 2:
                    if outcome_prices[0] == 1.0:
                        outcome = "Yes"
                    elif outcome_prices[1] == 1.0:
                        outcome = "No"
            
            # Also check CLOB as fallback
            if not outcome:
                if slug and slug in clob_by_slug:
                    outcome = get_market_resolution(clob_by_slug[slug])
                elif question.lower() in clob_by_question:
                    outcome = get_market_resolution(clob_by_question[question.lower()])
            
            # Check history as final fallback
            if not outcome and m_id in history:
                outcome = history[m_id].get("outcome", "")
            
            # Track resolved in history for future
            if is_resolved and outcome and m_id not in history:
                history[m_id] = {
                    "question": question,
                    "slug": slug,
                    "outcome": outcome,
                    "end_date": end_date
                }
            
            if not outcome:
                continue
            
            close_price = get_yes_price(market)
            
            # Detect repeat events
            is_repeat = False
            question_lower = question.lower()
            date_patterns = [r'january|february|march|april|may|june|july|august|september|october|november|december', r'\d{4}', r'week\s*\d+', r'month\s*\d+']
            for pattern in date_patterns:
                if re.search(pattern, question_lower):
                    is_repeat = True
                    break
            
            resolutions["resolved"].append({
                "question": question[:60],
                "volume": volume,
                "close_price": close_price * 100,
                "outcome": outcome,
                "resolved_date": end_date[:10] if end_date else "",
                "is_repeat": is_repeat,
                "url": build_market_url(market)
            })
        except:
            continue
    
    # Process active markets for pending resolutions (ended or upcoming)
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
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                end_date_naive = end_dt.replace(tzinfo=None)
                days_until_end = (end_date_naive - now).days
            except:
                continue
            
            # Include both ended (pending) and upcoming (within 7 days)
            if end_date_naive > now and days_until_end > 7:
                continue  # Skip if more than 7 days away
            
            close_price = get_yes_price(market)
            
            # Detect repeat events (check for date patterns in question)
            is_repeat = False
            date_patterns = [
                r'january|february|march|april|may|june|july|august|september|october|november|december',
                r'\d{4}',  # year
                r'week\s*\d+|month\s*\d+|quarter\s*\d+',
                r'20\d{2}',  # specific year format
            ]
            question_lower = question.lower()
            for pattern in date_patterns:
                if re.search(pattern, question_lower):
                    is_repeat = True
                    break
            
            is_upcoming = end_date_naive > now
            
            resolutions["pending"].append({
                "question": question[:60],
                "volume": volume,
                "close_price": close_price * 100,
                "end_date": end_date[:10],
                "is_upcoming": is_upcoming,
                "is_repeat": is_repeat,
                "url": build_market_url(market)
            })
        except:
            continue
    
    # Sort and limit - return more items
    resolutions["resolved"] = sorted(resolutions["resolved"], key=lambda x: x["volume"], reverse=True)[:50]
    resolutions["pending"] = sorted(resolutions["pending"], key=lambda x: x["volume"], reverse=True)[:50]
    
    # Also provide date-sorted versions
    resolutions["resolved_by_date"] = sorted(resolutions["resolved"], key=lambda x: x.get("resolved_date", ""), reverse=True)[:50]
    resolutions["pending_by_date"] = sorted(resolutions["pending"], key=lambda x: x.get("end_date", ""), reverse=True)[:50]
    
    # Save history with resolved markets
    save_history(history)
    
    return resolutions

def analyze_categories(markets):
    categories = {}
    for market in markets:
        tags = market.get("tags", [])
        cat = tags[0] if tags else "Other"
        vol = float(market.get("volume24hr", 0) or 0)
        categories[cat] = categories.get(cat, 0) + vol
    return sorted(categories.items(), key=lambda x: x[1], reverse=True)[:8]

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
        
        # Build URL - events use /event/ path
        if slug:
            url = f"https://polymarket.com/event/{slug}"
        elif market_id:
            url = f"https://polymarket.com/event?id={market_id}"
        else:
            # Try to get from nested markets
            event_markets = event.get("markets", [])
            for m in event_markets:
                if isinstance(m, dict):
                    m_slug = m.get("slug", "")
                    m_id = m.get("id", "")
                    if m_slug:
                        url = f"https://polymarket.com/market/{m_slug}"
                        break
                    elif m_id:
                        url = f"https://polymarket.com/market?id={m_id}"
                        break
            else:
                url = "#"
        
        event_data.append({
            "question": question[:70],
            "slug": slug,
            "volume": total_vol,
            "url": url
        })
    return sorted(event_data, key=lambda x: x["volume"], reverse=True)[:15]

@app.route("/")
def index():
    # Try to load cached market data first (fast from disk)
    cached_data = load_market_cache()
    cached_analysis = load_analysis_cache()
    
    # If we have both caches, serve immediately without API calls
    if cached_data and cached_analysis:
        markets = cached_data.get("markets", [])
        total_volume = sum(float(m.get("volume24hr") or m.get("volume") or 0) for m in markets)
        active_markets = len(markets)
        avg_volume = total_volume / active_markets if active_markets > 0 else 0
        
        return render_template("index.html",
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
                          fetched_at=cached_data.get("fetched_at"))
    
    # Otherwise fetch fresh data
    data = fetch_markets()
    volume_history = calculate_volume_history(data.get("markets", []))
    underdogs = analyze_underdogs(data.get("closed_markets", []))
    
    total_volume = sum(float(m.get("volume24hr") or m.get("volume") or 0) for m in data.get("markets", []))
    active_markets = len(data.get("markets", []))
    avg_volume = total_volume / active_markets if active_markets > 0 else 0
    
    new_markets_data = []
    for m in data.get("new_markets", [])[:15]:
        vol_24hr = m.get("volume24hr")
        vol_total = m.get("volume")
        volume = float(vol_24hr if vol_24hr else (vol_total if vol_total else 0))
        new_markets_data.append({
            "question": m.get("question", "Unknown")[:60],
            "volume": volume,
            "vol": m.get("vol", 0),
            "category": m.get("category") or (m.get("tags", ["General"])[0] if m.get("tags") else "General"),
            "end_date": m.get("endDate", ""),
            "url": build_market_url(m)
        })
    
    leaderboard = fetch_leaderboard()
    top_holders = fetch_top_holders()
    reversals = analyze_reversals(data.get("markets", []))
    insiders = analyze_insiders(data.get("markets", []))
    resolutions = analyze_resolutions(data.get("closed_markets", []), data.get("markets", []))
    
    closed_stats = {
        "yes_resolved": len([r for r in resolutions.get("resolved", []) if r.get("outcome") in ["Yes", "yes"]]),
        "no_resolved": len([r for r in resolutions.get("resolved", []) if r.get("outcome") in ["No", "no"]]),
        "total": len(resolutions.get("resolved", []))
    }
    categories = analyze_categories(data.get("markets", []))
    sentiment = analyze_sentiment(data.get("markets", []))
    
    leaderboard_data = []
    for i, trader in enumerate(leaderboard):
        addr = trader.get("proxyWallet", "")
        vol = float(trader.get("vol", 0) or 0)
        pnl = float(trader.get("pnl", 0) or 0)
        
        # API doesn't provide win rate - don't make it up
        win_rate = None
        
        leaderboard_data.append({
            "rank": i + 1,
            "address": addr[:10] + "..." if addr else "Unknown",
            "full_address": addr,
            "username": trader.get("userName", ""),
            "volume": vol,
            "pnl": pnl,
            "win_rate": win_rate,
            "win_rate": win_rate,
            "period": trader.get("period", "ALL"),
            "url": f"https://polymarket.com/profile/{addr}"
        })
    
    top_traders_yes = []
    top_traders_no = []
    for market in data.get("markets", [])[:50]:
        vol = float(market.get("volume24hr", 0) or 0)
        if vol > 10000:
            price = get_yes_price(market)
            if price > 0.7:
                top_traders_yes.append({
                    "question": market.get("question", "Unknown")[:50],
                    "price": price * 100,
                    "volume": vol,
                    "url": build_market_url(market)
                })
            elif price < 0.3:
                top_traders_no.append({
                    "question": market.get("question", "Unknown")[:50],
                    "price": (1 - price) * 100,
                    "volume": vol,
                    "url": build_market_url(market)
                })
    
    liquidity_analysis = []
    for market in data.get("markets", [])[:100]:
        vol = float(market.get("volume24hr", 0) or 0)
        liq = float(market.get("liquidity", 0) or 0)
        if liq > 5000 and vol > 1000:
            price = get_yes_price(market)
            liquidity_analysis.append({
                "question": market.get("question", "Unknown")[:50],
                "liquidity": liq,
                "volume": vol,
                "price": price * 100,
                "url": build_market_url(market)
            })
    liquidity_analysis = sorted(liquidity_analysis, key=lambda x: x["liquidity"], reverse=True)[:10]
    
    insider_signals = []
    for market in data.get("markets", [])[:30]:
        volume = float(market.get("volume24hr") or market.get("volume") or 0)
        if volume > 50000:
            price = float(market.get("yesPrice") or market.get("YesPrice") or 0.5)
            if price > 0.7:
                insider_signals.append({
                    "question": market.get("question", "Unknown")[:70],
                    "probability": price * 100,
                    "volume": volume,
                    "direction": "Yes",
                    "url": build_market_url(market)
                })
            elif price < 0.3:
                insider_signals.append({
                    "question": market.get("question", "Unknown")[:70],
                    "probability": price * 100,
                    "volume": volume,
                    "direction": "No",
                    "url": build_market_url(market)
                })
    
    events_data = process_events(data.get("events", []), data.get("markets", []))
    
    analysis_data = {
        "volume_history": volume_history,
        "categories": categories,
        "sentiment": sentiment,
        "new_markets": new_markets_data,
        "reversed_markets": reversals,
        "insider_markets": insiders,
        "leaderboard": leaderboard_data,
        "top_holders": top_holders,
        "events": events_data,
        "resolutions": resolutions,
        "closed_stats": closed_stats,
    }
    save_analysis_cache(analysis_data)
    
    return render_template("index.html",
                         volume_history=volume_history,
                         total_volume=total_volume,
                         active_markets=active_markets,
                         avg_volume=avg_volume,
                         new_markets=new_markets_data,
                         underdogs=underdogs,
                         closed_stats=closed_stats,
                         leaderboard=leaderboard_data,
                         top_holders=top_holders,
                         insider_signals=insiders,
                         reversals=reversals,
                         resolutions=resolutions,
                         categories=categories,
                         events=events_data,
                         liquidity_analysis=liquidity_analysis,
                         sentiment=sentiment,
                         fetched_at=data.get("fetched_at"))

@app.route("/api/refresh")
def refresh():
    if os.path.exists(MARKET_CACHE_FILE):
        os.remove(MARKET_CACHE_FILE)
    if os.path.exists(ANALYSIS_CACHE_FILE):
        os.remove(ANALYSIS_CACHE_FILE)
    _api_cache.clear()
    _analysis_cache.clear()
    return jsonify({"status": "cache cleared"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
