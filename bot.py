import ccxt
import pandas as pd
import time

exchange = ccxt.delta({
    'apiKey': 'D76ksMoFEatQDZqwBZEQXkgnrxhaTD',
    'secret': 'QDIRMP80CfaVfjvM0lLzcM1wafJI69e6QcdT4OusixH3XD4yMTUP8PQh5oP4',
})

SYMBOL = 'BTC/USD:USD'
TIMEFRAME = '5m'
LOT = 1
tpRatio = 1.618

# STATE VARIABLES (same as Pine)
scLow = None
arHigh = None
bcHigh = None
arLow = None

springReady = False
utadReady = False
springStop = None
utadStop = None


def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    return df


def place_order(side, sl, tp):
    try:
        print(f"\n🔥 {side.upper()} ORDER")

        exchange.create_order(SYMBOL, 'market', side, LOT)

        # SL
        exchange.create_order(
            SYMBOL, 'stop_market',
            'sell' if side == 'buy' else 'buy',
            LOT,
            params={'stop_price': sl, 'reduce_only': True}
        )

        # TP
        exchange.create_order(
            SYMBOL, 'take_profit_market',
            'sell' if side == 'buy' else 'buy',
            LOT,
            params={'stop_price': tp, 'reduce_only': True}
        )

        print(f"✅ Entry | SL: {sl} | TP: {tp}")

    except Exception as e:
        print("❌ Order Error:", e)


print("🤖 WYCKOFF BOT START")

while True:
    try:
        df = get_data()

        high = df['high']
        low = df['low']
        close = df['close']
        volume = df['volume']

        # LAST CANDLE
        h = high.iloc[-1]
        l = low.iloc[-1]
        c = close.iloc[-1]

        avgVol = volume.rolling(20).mean().iloc[-1]
        isVolSpike = volume.iloc[-1] > avgVol * 1.2

        # ===== ACCUMULATION =====
        if scLow is None or l < scLow:
            scLow = l
            arHigh = None

        if scLow and (arHigh is None or h > arHigh):
            arHigh = h

        # SPRING
        if scLow and l < scLow and c > scLow and isVolSpike:
            springReady = True
            springStop = l
            print("🟢 SPRING DETECT")

        # ===== DISTRIBUTION =====
        if bcHigh is None or h > bcHigh:
            bcHigh = h
            arLow = None

        if bcHigh and (arLow is None or l < arLow):
            arLow = l

        # UTAD
        if bcHigh and h > bcHigh and c < bcHigh and isVolSpike:
            utadReady = True
            utadStop = h
            print("🔴 UTAD DETECT")

        # ===== ENTRY =====

        # BUY
        if springReady and arHigh and c > arHigh:
            risk = c - springStop
            if risk > 0:
                tp = c + (risk * tpRatio)
                place_order('buy', springStop, tp)
                springReady = False

        # SELL
        if utadReady and arLow and c < arLow:
            risk = utadStop - c
            if risk > 0:
                tp = c - (risk * tpRatio)
                place_order('sell', utadStop, tp)
                utadReady = False

        print("⏳ Waiting next candle...")
        time.sleep(300)

    except Exception as e:
        print("❌ Error:", e)
        time.sleep(10)
