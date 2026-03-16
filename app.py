import os
import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify
import time

app = Flask(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

CACHE_FILE = "cache.json"
CACHE_DURATION = 300

def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                if time.time() - data.get("timestamp", 0) < CACHE_DURATION:
                    return data.get("data")
    except:
        pass
    return None

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump({"timestamp": time.time(), "data": data}, f)

def fetch_markets():
    cached = load_cache()
    if cached:
        return cached
    
    try:
        all_markets = []
        seen_ids = set()
        
        print("Fetching active markets...")
        for offset in range(0, 2000, 200):
            params = {
                "closed": "false",
                "limit": 200,
                "offset": offset
            }
            resp = requests.get(f"{GAMMA_API}/markets", params=params, timeout=30)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
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
        for offset in range(0, 2000, 200):
            params_closed = {
                "closed": "true",
                "limit": 200,
                "offset": offset
            }
            try:
                resp_closed = requests.get(f"{GAMMA_API}/markets", params=params_closed, timeout=30)
                resp_closed.raise_for_status()
                batch = resp_closed.json()
                if not batch:
                    break
                all_closed_markets.extend(batch)
                print(f"  Closed offset {offset}: {len(batch)} markets")
                if len(batch) < 200:
                    break
            except:
                break
        
        print(f"\\nTotal: {len(all_markets)} active, {len(all_new_markets)} new, {len(all_closed_markets)} closed")
        
        data = {
            "markets": all_markets[:500],
            "new_markets": all_new_markets[:200],
            "closed_markets": all_closed_markets[:500],
            "events": events[:50],
            "fetched_at": datetime.now().isoformat()
        }
        save_cache(data)
        return data
    except Exception as e:
        print(f"Error fetching markets: {e}")
        import traceback
        traceback.print_exc()
        return load_cache() or {"markets": [], "new_markets": [], "closed_markets": [], "events": [], "fetched_at": None}
        events = []
        if resp_events.status_code == 200:
            events = resp_events.json()
        
        data = {
            "markets": all_markets[:100],
            "new_markets": all_new_markets[:50],
            "closed_markets": all_closed_markets[:100],
            "events": events[:30],
            "fetched_at": datetime.now().isoformat()
        }
        save_cache(data)
        return data
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return load_cache() or {"markets": [], "new_markets": [], "closed_markets": [], "events": [], "fetched_at": None}

def calculate_volume_history(markets):
    volume_by_day = {}
    for market in markets:
        volume = market.get("volume24hr") or market.get("volume") or 0
        if volume:
            day = datetime.now().strftime("%Y-%m-%d")
            volume_by_day[day] = volume_by_day.get(day, 0) + float(volume)
    
    history = []
    for i in range(29, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        history.append({
            "date": day,
            "volume": volume_by_day.get(day, 0)
        })
    return history

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
        
        return unique_traders[:20]
    except Exception as e:
        print(f"Error fetching leaderboard: {e}")
        return []

def fetch_top_holders():
    return []

def get_yes_price(market):
    outcome_prices = market.get("outcomePrices", [])
    if outcome_prices and len(outcome_prices) > 0:
        try:
            return float(outcome_prices[0])
        except:
            pass
    val = market.get("yesPrice")
    if val:
        try:
            return float(val)
        except:
            pass
    return 0.5

def get_no_price(market):
    outcome_prices = market.get("outcomePrices", [])
    if outcome_prices and len(outcome_prices) > 1:
        try:
            return float(outcome_prices[1])
        except:
            pass
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
                    reversals.append({
                        "question": market.get("question", "Unknown")[:55],
                        "day_change": day_change * 100,
                        "week_change": week_change * 100,
                        "volume": volume,
                        "price": current_price * 100,
                        "direction": direction,
                        "url": f"https://polymarket.com/event/{market.get('slug', '')}"
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
        "hot_takes": []
    }
    
    for market in markets:
        try:
            volume = float(market.get("volume24hr", 0) or 0)
            if volume < 1000:
                continue
                
            current_price = get_yes_price(market)
            day_change = float(market.get("oneDayPriceChange", 0) or 0)
            
            sentiment_data["count"] += 1
            sentiment_data["overall"] += current_price
            
            if current_price > 0.6:
                sentiment_data["bullish"] += 1
            elif current_price < 0.4:
                sentiment_data["bearish"] += 1
            else:
                sentiment_data["neutral"] += 1
            
            tags = market.get("tags", [])
            cat = tags[0] if tags else "Other"
            if cat not in sentiment_data["categories"]:
                sentiment_data["categories"][cat] = {"yes": 0, "no": 0, "count": 0}
            sentiment_data["categories"][cat]["count"] += 1
            sentiment_data["categories"][cat]["yes"] += current_price
            
            if abs(day_change) > 0.05 and volume > 5000:
                direction = "📈" if day_change > 0 else "📉"
                sentiment_data["hot_takes"].append({
                    "question": market.get("question", "Unknown")[:50],
                    "price": current_price * 100,
                    "change": day_change * 100,
                    "direction": direction,
                    "url": f"https://polymarket.com/event/{market.get('slug', '')}"
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
                        "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                    })
        except:
            continue
    return sorted(insiders, key=lambda x: x["conviction"], reverse=True)[:15]

def analyze_resolutions(closed_markets):
    resolutions = {
        "yes": [],
        "no": [],
        "underdogs": [],
        "blowouts": []
    }
    
    for market in closed_markets:
        try:
            outcome = market.get("outcome", "")
            if not outcome:
                continue
            
            question = market.get("question", "Unknown")
            volume = float(market.get("volume", 0) or 0)
            
            if outcome == "Yes":
                close_price = get_yes_price(market)
                resolutions["yes"].append({
                    "question": question[:60],
                    "volume": volume,
                    "close_price": close_price * 100,
                    "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                })
                
                if close_price < 0.5 and volume > 1000:
                    resolutions["underdogs"].append({
                        "question": question[:60],
                        "close_price": close_price * 100,
                        "volume": volume,
                        "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                    })
                elif close_price > 0.85 and volume > 1000:
                    resolutions["blowouts"].append({
                        "question": question[:60],
                        "close_price": close_price * 100,
                        "volume": volume,
                        "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                    })
            else:
                close_price = get_no_price(market)
                resolutions["no"].append({
                    "question": question[:60],
                    "volume": volume,
                    "close_price": close_price * 100,
                    "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                })
                
                if close_price < 0.5 and volume > 1000:
                    resolutions["underdogs"].append({
                        "question": question[:60],
                        "close_price": close_price * 100,
                        "volume": volume,
                        "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                    })
                elif close_price > 0.85 and volume > 1000:
                    resolutions["blowouts"].append({
                        "question": question[:60],
                        "close_price": close_price * 100,
                        "volume": volume,
                        "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                    })
        except:
            continue
    
    resolutions["yes"] = resolutions["yes"][:10]
    resolutions["no"] = resolutions["no"][:10]
    resolutions["underdogs"] = resolutions["underdogs"][:10]
    resolutions["blowouts"] = resolutions["blowouts"][:10]
    
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
        
        if not slug:
            event_markets = event.get("markets", [])
            for m in event_markets:
                if isinstance(m, dict):
                    slug = m.get("slug", "")
                    break
        
        event_data.append({
            "question": question[:70],
            "slug": slug,
            "volume": total_vol,
            "url": f"https://polymarket.com/event/{slug}" if slug else "#"
        })
    return sorted(event_data, key=lambda x: x["volume"], reverse=True)[:15]

@app.route("/")
def index():
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
            "url": f"https://polymarket.com/event/{m.get('slug', '')}"
        })
    
    closed_stats = {
        "yes_resolved": sum(1 for m in data.get("closed_markets", []) if m.get("outcome") == "Yes"),
        "no_resolved": sum(1 for m in data.get("closed_markets", []) if m.get("outcome") == "No"),
        "total": len(data.get("closed_markets", []))
    }
    
    leaderboard = fetch_leaderboard()
    top_holders = fetch_top_holders()
    reversals = analyze_reversals(data.get("markets", []))
    insiders = analyze_insiders(data.get("markets", []))
    resolutions = analyze_resolutions(data.get("closed_markets", []))
    categories = analyze_categories(data.get("markets", []))
    sentiment = analyze_sentiment(data.get("markets", []))
    
    leaderboard_data = []
    for i, trader in enumerate(leaderboard):
        addr = trader.get("proxyWallet", "")
        vol = float(trader.get("vol", 0) or 0)
        pnl = float(trader.get("pnl", 0) or 0)
        trades = int(trader.get("tradeCount", 0) or 0)
        win_rate = float(trader.get("winRate", 0) or 0) * 100
        
        leaderboard_data.append({
            "rank": i + 1,
            "address": addr[:10] + "..." if addr else "Unknown",
            "full_address": addr,
            "username": trader.get("userName", ""),
            "volume": vol,
            "pnl": pnl,
            "trades": trades,
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
                    "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                })
            elif price < 0.3:
                top_traders_no.append({
                    "question": market.get("question", "Unknown")[:50],
                    "price": (1 - price) * 100,
                    "volume": vol,
                    "url": f"https://polymarket.com/event/{market.get('slug', '')}"
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
                "url": f"https://polymarket.com/event/{market.get('slug', '')}"
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
                    "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                })
            elif price < 0.3:
                insider_signals.append({
                    "question": market.get("question", "Unknown")[:70],
                    "probability": price * 100,
                    "volume": volume,
                    "direction": "No",
                    "url": f"https://polymarket.com/event/{market.get('slug', '')}"
                })
    
    events_data = process_events(data.get("events", []), data.get("markets", []))
    
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
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    return jsonify({"status": "cache cleared"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
