import requests
import time
import threading
import pandas as pd
import pandas_ta as ta
from flask import Flask
import telegram

# === KONFIGURASI ===
PAIRS = ["vra_idr", "alt_idr", "zkj_idr", "wozx_idr", "krd_idr", "skya_idr"]
INTERVAL = 60  # Detik antar polling
INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]
CANDLES = 100

TELEGRAM_TOKEN = "7950867729:AAE8KCxGgFhZMr6qUpMl1baZ8IdALf9akLk"
CHAT_ID = "1144241819"
bot = telegram.Bot(token=TELEGRAM_TOKEN)

app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Bot sinyal teknikal + volume/harga aktif"

# Fungsi ambang sensitivitas per interval
def get_min_score(interval):
    if interval in ["1m", "5m"]:
        return 70
    elif interval in ["15m", "1h"]:
        return 80
    else:
        return 90

# Ambil data OHLCV
def fetch_ohlcv(pair, interval):
    try:
        url = f"https://indodax.com/api/chart/{pair}/{interval}"
        response = requests.get(url)
        data = response.json()["chart"]
        df = pd.DataFrame(data)
        df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        df = df.astype(float)
        return df.tail(CANDLES)
    except Exception as e:
        print(f"[ERROR] Fetch OHLCV {pair}-{interval}: {e}")
        return None

# Hitung skor sinyal
def calculate_signal_score(pair, df):
    score_buy, score_sell = 0, 0
    try:
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.rsi(length=14, append=True)
        macd = ta.macd(df["close"])
        df = pd.concat([df, macd], axis=1)
        last = df.iloc[-1]
        price = last["close"]

        if last["EMA_9"] > last["EMA_21"]:
            score_buy += 25
        if last["RSI_14"] < 30:
            score_buy += 20
        if last["MACD_12_26_9"] > last["MACDs_12_26_9"]:
            score_buy += 30
        if price < 100:
            score_buy += 15

        if last["EMA_9"] < last["EMA_21"]:
            score_sell += 25
        if last["RSI_14"] > 70:
            score_sell += 20
        if last["MACD_12_26_9"] < last["MACDs_12_26_9"]:
            score_sell += 30
        if price > 5000:
            score_sell += 15

        return score_buy, score_sell, price
    except Exception as e:
        print(f"[ERROR] Analysis {pair}: {e}")
        return 0, 0, 0

# Analisis teknikal multi-interval
def analyze_all(pair):
    for interval in INTERVALS:
        df = fetch_ohlcv(pair, interval)
        if df is not None:
            score_buy, score_sell, price = calculate_signal_score(pair, df)
            min_score = get_min_score(interval)

            if score_buy >= min_score:
                msg = (
                    f"===========================\n"
                    f"📊 Sinyal BUY TERDETEKSI\n"
                    f"🕒 Interval: {interval}\n"
                    f"💱 Pair: {pair.upper()}\n"
                    f"📈 Harga: {price:.2f} IDR\n"
                    f"✅ Skor BUY: {score_buy}% (min {min_score}%)\n"
                    f"🔗 https://indodax.com/market/{pair}\n"
                    f"==========================="
                )
                bot.send_message(chat_id=CHAT_ID, text=msg)
            elif score_sell >= min_score:
                msg = (
                    f"===========================\n"
                    f"📉 Sinyal SELL TERDETEKSI\n"
                    f"🕒 Interval: {interval}\n"
                    f"💱 Pair: {pair.upper()}\n"
                    f"📉 Harga: {price:.2f} IDR\n"
                    f"⚠️ Skor SELL: {score_sell}% (min {min_score}%)\n"
                    f"🔗 https://indodax.com/market/{pair}\n"
                    f"==========================="
                )
                bot.send_message(chat_id=CHAT_ID, text=msg)

# Cek harga & volume lonjakan
def get_price_volume(pair):
    try:
        url = f"https://indodax.com/api/{pair}/ticker"
        r = requests.get(url)
        data = r.json()
        return float(data["ticker"]["last"]), float(data["ticker"]["vol_idr"])
    except:
        return None, None

# Pemantauan menyeluruh
def monitor(pair):
    last_price, last_vol = get_price_volume(pair)
    if last_price is None:
        return

    while True:
        analyze_all(pair)
        price, vol = get_price_volume(pair)
        if price is None:
            continue
        price_change = ((price - last_price) / last_price) * 100
        vol_change = ((vol - last_vol) / last_vol) * 100 if last_vol else 0

        if price_change >= 3 or vol_change >= 100:
            msg = f"🚨 ALERT VOLUME/HARGA\n"
            msg += f"💱 Pair: {pair.upper()}\n"
            if price_change >= 3:
                msg += f"📈 Harga naik {price_change:.2f}%\n💰 {last_price:.2f} ➡️ {price:.2f} IDR\n"
            if vol_change >= 100:
                msg += f"📊 Volume naik {vol_change:.2f}%\n🔁 {last_vol:.2f} ➡️ {vol:.2f} IDR\n"
            msg += f"🔗 https://indodax.com/market/{pair}"
            bot.send_message(chat_id=CHAT_ID, text=msg)
            last_price, last_vol = price, vol
        time.sleep(INTERVAL)

# Start semua pair
try:
    bot.send_message(chat_id=CHAT_ID, text="✅ Bot sinyal tren & volume/harga aktif.")
except:
    pass

for pair in PAIRS:
    threading.Thread(target=monitor, args=(pair,), daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
