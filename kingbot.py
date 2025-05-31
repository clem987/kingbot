import ccxt
import pandas as pd
import numpy as np
import time
import datetime
from ta.momentum import RSIIndicator
from ta.trend import MACD
import requests

# === Configuration ===

import os

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CAPITAL_USDC = 70
STOP_LOSS_PCT = 0.03
SYMBOLS = ['BTC/USDC', 'ETH/USDC', 'BNB/USDC']
INTERVAL = 30  # secondes
INFO_INTERVAL = 5 * 60  # toutes les 5 minutes

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

positions = {}
last_info_time = 0

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=data)
    except Exception as e:
        print("Erreur Telegram :", e)

def get_ohlcv(symbol, limit=100):
    data = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=limit)
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def analyse(df):
    df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
    macd = MACD(df['close'])
    df['macd'] = macd.macd()
    df['signal'] = macd.macd_signal()
    return df

def should_buy(df):
    last = df.iloc[-1]
    return last['rsi'] < 30 and last['macd'] > last['signal']

def should_sell(df, entry_price, current_price):
    loss_pct = (entry_price - current_price) / entry_price
    return df.iloc[-1]['rsi'] > 70 or loss_pct >= STOP_LOSS_PCT

def send_status():
    now = datetime.datetime.now().strftime('%H:%M:%S')
    balance = exchange.fetch_balance()
    usdc_balance = balance['USDC']['free']
    msg = f"🕒 {now} — 📊 *STATUS* KINGBOT\n💰 Solde USDC : {usdc_balance:.2f}$\n"
    for symbol in SYMBOLS:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        msg += f"\n🔹 {symbol} : {price:.2f}$"
        if symbol in positions:
            entry = positions[symbol]['entry_price']
            amount = positions[symbol]['amount']
            pnl = (price - entry) * amount
            msg += f" | 🟢 Position ouverte | PnL latent : {pnl:.2f}$"
        else:
            msg += " | ⚪ Aucune position"
    msg += "\n\n👑 Garde le cap, The King surveille les marchés !"
    send_telegram(msg)

def run():
    global positions, last_info_time
    send_telegram("🚀 KINGBOT est lancé. En route vers les gains.")
    while True:
        for symbol in SYMBOLS:
            try:
                df = get_ohlcv(symbol)
                df = analyse(df)
                price = df.iloc[-1]['close']

                if symbol not in positions:
                    if should_buy(df):
                        usdc_balance = exchange.fetch_balance()['USDC']['free']
                        amount = round((CAPITAL_USDC / len(SYMBOLS)) / price, 5)
                        order = exchange.create_market_buy_order(symbol, amount)
                        positions[symbol] = {
                            'entry_price': price,
                            'amount': amount,
                            'timestamp': datetime.datetime.now()
                        }
                        msg = f"📈 Achat {symbol} à {price:.2f}$\n🎯 Montant : {amount} | 💰 Solde restant : {usdc_balance:.2f}$"
                        send_telegram(msg)

                else:
                    position = positions[symbol]
                    if should_sell(df, position['entry_price'], price):
                        order = exchange.create_market_sell_order(symbol, position['amount'])
                        profit = (price - position['entry_price']) * position['amount']
                        send_telegram(f"📉 Vente {symbol} à {price:.2f}$\n💸 Profit : {profit:.2f} $")
                        del positions[symbol]

            except Exception as e:
                print(f"[ERREUR] {symbol} : {e}")
                send_telegram(f"⚠️ Erreur avec {symbol} : {e}")

        if time.time() - last_info_time >= INFO_INTERVAL:
            send_status()
            last_info_time = time.time()

        time.sleep(INTERVAL)

if __name__ == "__main__":
    run()













