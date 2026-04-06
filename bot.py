import ccxt
import pandas as pd
import ta
import time
from datetime import datetime, timezone

API_KEY    = 'D76ksMoFEatQDZqwBZEQXkgnrxhaTD'
API_SECRET = 'QDIRMP80CfaVfjvM0lLzcM1wafJI69e6QcdT4OusixH3XD4yMTUP8PQh5oP4'

exchange = ccxt.delta({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'urls': {
        'api': {
            'public':  'https://api.india.delta.exchange',
            'private': 'https://api.india.delta.exchange',
        },
    },
})

SYMBOLS   = ['BTC/USD:USD','SOL/USD:USD']
TIMEFRAME = '5m'
LOT_SIZE  = 1

last_signal_time = {s: None for s in SYMBOLS}

def seconds_to_candle_close():
    now = datetime.now(timezone.utc)
    seconds = now.minute * 60 + now.second
    remaining = 300 - (seconds % 300)
    if remaining < 3:
        remaining += 300
    return remaining

def wait_for_candle_close():
    remaining = seconds_to_candle_close()
    print(f"⏳ C3 close mein: {remaining//60}m {remaining%60}s")
    time.sleep(remaining + 2)

def get_candles(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=500)
        if len(ohlcv) < 25:
            return None
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        bb = ta.volatility.BollingerBands(df['close'], window=20)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_mid']   = bb.bollinger_mavg()
        return df
    except Exception as e:
        print(f"❌ Candle Error: {e}")
        return None

def get_live_price(symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return float(ticker['last'])
    except:
        return None

def get_live_bb(symbol):
    try:
        df = get_candles(symbol)
        if df is None:
            return None, None
        return float(df.iloc[-1]['bb_lower']), float(df.iloc[-1]['bb_upper'])
    except:
        return None, None

def close_position(symbol, side):
    try:
        close_side = 'sell' if side == 'buy' else 'buy'
        positions = exchange.fetch_positions([symbol])
        for pos in positions:
            size = abs(float(pos['contracts']))
            if size > 0:
                order = exchange.create_order(
                    symbol, 'market', close_side, size,
                    params={'reduce_only': True}
                )
                print(f"✅ Position Close: {order['id']}")
                return
        print("⚠️ Koi Position Nahi!")
    except Exception as e:
        print(f"❌ Close Error: {e}")

def check_signal(df):
    # df.iloc[-1] = C4 (ban rahi hai — ignore)
    # df.iloc[-2] = C3 (abhi close hui) ← ENTRY YAHAN
    # df.iloc[-3] = C2
    # df.iloc[-4] = C1
    c1 = df.iloc[-4]
    c2 = df.iloc[-3]
    c3 = df.iloc[-2]  # ← C3 just closed

    # ══ SELL ══
    c1_green      = float(c1['close']) > float(c1['open'])
    c1_above_sma  = float(c1['close']) > float(c1['bb_mid'])
    c2_red        = float(c2['close']) < float(c2['open'])
    c2_above_sma  = float(c2['close']) > float(c2['bb_mid'])
    c2_open_ok    = float(c1['close']) <= float(c2['open']) < float(c1['high'])
    c2_close_ok   = float(c1['open'])  < float(c2['close']) < float(c1['close'])
    c1_upper_wick = float(c1['high'])  - float(c1['close'])
    c2_upper_wick = float(c2['high'])  - float(c2['open'])
    wick_ok_sell  = c2_upper_wick < c1_upper_wick if c1_upper_wick > 0 else True
    c3_red        = float(c3['close']) < float(c3['open'])
    c3_above_sma  = float(c3['close']) > float(c3['bb_mid'])
    c3_breaks_low = float(c3['close']) < float(c2['low'])

    special_sell = (
        c1_green and c1_above_sma and
        abs(float(c1['high']) - float(c2['open'])) < 0.01 * float(c1['high']) and
        c2_red and c2_above_sma and
        c3_red and c3_above_sma and c3_breaks_low
    )

    sell_signal = ((
        c1_green and c1_above_sma and
        c2_red and c2_above_sma and
        c2_open_ok and c2_close_ok and wick_ok_sell and
        c3_red and c3_above_sma and c3_breaks_low
    ) or special_sell)

    # ══ BUY ══
    c1_red         = float(c1['close']) < float(c1['open'])
    c1_below_sma   = float(c1['close']) < float(c1['bb_mid'])
    c2_green       = float(c2['close']) > float(c2['open'])
    c2_below_sma   = float(c2['close']) < float(c2['bb_mid'])
    c2_open_ok_b   = float(c1['close']) >= float(c2['open']) > float(c1['low'])
    c2_close_ok_b  = float(c1['close']) > float(c2['close']) > float(c1['open'])
    c1_lower_wick  = float(c1['open'])  - float(c1['low'])
    c2_lower_wick  = float(c2['open'])  - float(c2['low'])
    wick_ok_buy    = c2_lower_wick < c1_lower_wick if c1_lower_wick > 0 else True
    c3_green       = float(c3['close']) > float(c3['open'])
    c3_below_sma   = float(c3['close']) < float(c3['bb_mid'])
    c3_breaks_high = float(c3['close']) > float(c2['high'])

    special_buy = (
        c1_red and c1_below_sma and
        abs(float(c1['low']) - float(c2['open'])) < 0.01 * float(c1['low']) and
        c2_green and c2_below_sma and
        c3_green and c3_below_sma and c3_breaks_high
    )

    buy_signal = ((
        c1_red and c1_below_sma and
        c2_green and c2_below_sma and
        c2_open_ok_b and c2_close_ok_b and wick_ok_buy and
        c3_green and c3_below_sma and c3_breaks_high
    ) or special_buy)

    # C3 close = entry price
    entry = float(c3['close'])
    sl_sell = float(c1['high'])
    sl_buy  = float(c1['low'])
    c3_time = int(c3['time'])

    return sell_signal, buy_signal, entry, sl_sell, sl_buy, c3_time

def track_trade(symbol, side, sl):
    print(f"\n📊 {symbol} Tracking — {side.upper()} | SL:{sl}")
    while True:
        try:
            time.sleep(10)  # Har 10 sec mein check

            price = get_live_price(symbol)
            if price is None:
                continue

            bb_lower, bb_upper = get_live_bb(symbol)
            if bb_lower is None:
                continue

            target = bb_lower if side == 'sell' else bb_upper
            now_str = datetime.now().strftime('%H:%M:%S')
            print(f"[{now_str}] 💰{price} 🎯{target:.2f} 🛑{sl}")

            # TARGET HIT
            if side == 'sell' and price <= target:
                print(f"🎯 TARGET HIT! {symbol} PROFIT!")
                close_position(symbol, side)
                break
            elif side == 'buy' and price >= target:
                print(f"🎯 TARGET HIT! {symbol} PROFIT!")
                close_position(symbol, side)
                break

            # SL HIT
            if side == 'sell' and price >= sl:
                print(f"🛑 SL HIT! {symbol} LOSS!")
                close_position(symbol, side)
                break
            elif side == 'buy' and price <= sl:
                print(f"🛑 SL HIT! {symbol} LOSS!")
                close_position(symbol, side)
                break

        except Exception as e:
            print(f"❌ Track Error: {e}")
            time.sleep(30)

def place_order(symbol, side, entry, sl, df):
    target = float(df.iloc[-2]['bb_lower']) if side == 'sell' else float(df.iloc[-2]['bb_upper'])
    now_str = datetime.now().strftime('%H:%M:%S')
    print(f"\n{'═'*42}")
    print(f"🔔 [{now_str}] {symbol} {side.upper()}")
    print(f"💰 Entry  : {entry}  ← C3 Close")
    print(f"🛑 SL     : {sl}  ← C1 {'High' if side=='sell' else 'Low'}")
    print(f"🎯 Target : {target}  ← BB {'Lower' if side=='sell' else 'Upper'}")
    print(f"{'═'*42}\n")
    try:
        order = exchange.create_order(symbol, 'market', side, LOT_SIZE)
        print(f"✅ Order Placed: {order['id']}")
        track_trade(symbol, side, sl)
    except Exception as e:
        print(f"❌ Order Error: {e}")

print("🤖 Bot Start! BTC + ETH + SOL")
print("✅ C3 Close par entry hogi")
print("✅ Har 10 sec mein Target/SL check hoga\n")

while True:
    try:
        wait_for_candle_close()
        now_str = datetime.now().strftime('%H:%M:%S')
        print(f"\n🕐 [{now_str}] C3 Close! Signal Check...\n")

        for symbol in SYMBOLS:
            try:
                df = get_candles(symbol)
                if df is None:
                    continue

                sell, buy, entry, sl_sell, sl_buy, c3_time = check_signal(df)

                if (sell or buy) and last_signal_time[symbol] == c3_time:
                    print(f"  {symbol} — Same candle skip")
                    continue

                if sell:
                    print(f"  📉 SELL! {symbol}")
                    last_signal_time[symbol] = c3_time
                    place_order(symbol, 'sell', entry, sl_sell, df)
                elif buy:
                    print(f"  📈 BUY! {symbol}")
                    last_signal_time[symbol] = c3_time
                    place_order(symbol, 'buy', entry, sl_buy, df)
                else:
                    print(f"  {symbol} — No Signal")

            except Exception as e:
                print(f"❌ {symbol} Error: {e}")

    except Exception as e:
        print("❌ Main Error:", e)
        time.sleep(60)
