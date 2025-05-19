import json
import time
import vectorbt as vbt
import talib
from binance.um_futures import UMFutures
from binance.error import ClientError
from telegram import Bot

API_KEY = "oGzSEClmbwGvnnXP25s8nWc5TPaUVPr3AfvJ30pLZvlscpUwX4Pkm8cwbzB4YUaN"
API_SECRET = "uXQf6tjSFcO11p0uBTE90LYVOpOI9AYEZRnLhI0VZdWb23yQekI1eu73JH8JBo84"
TELEGRAM_TOKEN = "7869953064:AAHmBKtVL18HDUw9TR1eHqehK4PxQsm1uAU"
CHAT_ID = "1559265898"

client = UMFutures(key=API_KEY, secret=API_SECRET)
bot = Bot(token=TELEGRAM_TOKEN)
send_telegram("Bot Baþladý")
entry_prices = {}

with open("symbol_config.json", "r") as f:
    symbol_config = json.load(f)

def send_telegram(message):
    try:
        bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print(f"Telegram Hatasý: {e}")

def get_trade_quantity(symbol, entry_price, percent=50):
    balance = float(client.balance()[0]['balance'])
    usdt_to_use = balance * (percent / 100)
    qty = usdt_to_use / entry_price
    return round(qty, 3)

def get_technical_signal(symbol):
    ohlcv = vbt.BinanceData.download(symbol=symbol, timeframe='5m', limit=100).get('close')
    close = ohlcv.vbt.to_numpy()
    rsi = talib.RSI(close, timeperiod=14)
    macd, signal, hist = talib.MACD(close)
    upper, middle, lower = talib.BBANDS(close)

    config = symbol_config.get(symbol, {})
    rsi_buy = config.get("rsi_buy", 35)
    rsi_sell = config.get("rsi_sell", 65)

    if rsi[-1] < rsi_buy and macd[-1] > signal[-1] and close[-1] < lower[-1]:
        return "LONG"
    elif rsi[-1] > rsi_sell and macd[-1] < signal[-1] and close[-1] > upper[-1]:
        return "SHORT"
    else:
        return None

def open_position(symbol, side):
    try:
        entry_price = float(client.ticker_price(symbol=symbol)['price'])
        qty = get_trade_quantity(symbol, entry_price)
        client.new_order(
            symbol=symbol,
            side="BUY" if side == "LONG" else "SELL",
            type="MARKET",
            quantity=qty
        )
        entry_prices[symbol] = entry_price
        send_telegram(f"{symbol} için {side} pozisyon açýldý: {qty} @ {entry_price}")
    except Exception as e:
        send_telegram(f"{symbol} pozisyon açýlýrken hata: {e}")

def close_position(symbol, side):
    try:
        entry_price = entry_prices.get(symbol, float(client.ticker_price(symbol=symbol)['price']))
        qty = get_trade_quantity(symbol, entry_price)
        client.new_order(
            symbol=symbol,
            side="SELL" if side == "LONG" else "BUY",
            type="MARKET",
            quantity=qty
        )
        send_telegram(f"{symbol} için {side} pozisyon kapatýldý: {qty}")
        entry_prices.pop(symbol, None)
    except Exception as e:
        send_telegram(f"{symbol} pozisyon kapanýrken hata: {e}")

def check_profit_loss(symbol):
    if symbol not in entry_prices:
        return
    entry = entry_prices[symbol]
    current = float(client.ticker_price(symbol=symbol)['price'])
    change = (current - entry) / entry * 100
    if change >= 5:
        send_telegram(f"{symbol}: +%{round(change, 2)} kar, pozisyon kapatýlýyor.")
        close_position(symbol, "LONG")
    elif change <= -2:
        send_telegram(f"{symbol}: %{round(change, 2)} zarar, pozisyon kapatýlýyor.")
        close_position(symbol, "LONG")

def run_bot():
    while True:
        for symbol in symbol_config.keys():
            try:
                signal = get_technical_signal(symbol)
                position_amt = float([p for p in client.get_position_risk() if p['symbol'] == symbol.replace("/", "")][0]['positionAmt'])
                
                if signal == "LONG" and position_amt == 0:
                    open_position(symbol, "LONG")
                elif signal == "SHORT" and position_amt == 0:
                    open_position(symbol, "SHORT")

                check_profit_loss(symbol)
            except Exception as e:
                print(f"Hata {symbol}: {e}")
        time.sleep(60)

if __name__ == "__main__":
    run_bot()
