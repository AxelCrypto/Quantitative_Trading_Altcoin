#import ta
import pandas as pd
from perp_bitget import PerpBitget
import ccxt
import numpy as np
import requests
import json
import time
import os
from datetime import datetime
import yfinance as yf

df = yf.Ticker('ADA-USD').history(period="5y", interval='1d')
df.reset_index(drop = False, inplace = True)
df.columns = df.columns.str.lower()
#print(df.tail())
df.drop(columns=['dividends','stock splits'], inplace=True)
#df.columns = df.columns.str.capitalize()
df.rename(columns = {'date':'timestamp'},inplace=True)
df.set_index('timestamp', inplace=True)

df.drop(columns=df.columns.difference(['open','high','low','close','volume']), inplace=True)

period = 22
sqrt_period = np.sqrt(period)

def John(x, y):
    alpha = 2 / (y + 1)
    sum = np.zeros(len(x))
    sum[0] = alpha * x[0]
    for i in range(1, len(x)):
        sum[i] = alpha * x[i] + (1 - alpha) * sum[i-1]
    return sum

close_ema1 = John(df['close'], int(period / 2))
close_ema2 = John(df['close'], period)
ehma = John(2 * close_ema1 - close_ema2, sqrt_period)

df['ehma'] = ehma
df['ehma_1'] = df['ehma'].shift(1)
df.columns = df.columns.str.lower()


now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- Start Execution Time :", current_time, "---")



# Connection to API (To update in the AWS' server)
f = open(
    "../api_connection.json")
api_connection = json.load(f)
f.close()

account_to_select = "bitget_connection"
production = True

pair = "ADA/USDT:USDT"
timeframe = "1d"
leverage = 2

print(f"--- {pair} {timeframe} Leverage x {leverage} ---")

type = ["long", "short"]




# Trading actions
def open_long(row):
    if row['ehma'] > row['ehma_1']:
        return True
    else:
        return False


def close_long(row):
    if row['ehma'] < row['ehma_1']:
        return True
    else:
        return False

def open_short(row):
    if row['ehma'] < row['ehma_1']:
        return True
    else:
        return False


def close_short(row):
    if row['ehma'] > row['ehma_1']:
        return True
    else:
        return False


#Connection
bitget = PerpBitget(
    apiKey=api_connection[account_to_select]["apiKey"],
    secret=api_connection[account_to_select]["secret"],
    password=api_connection[account_to_select]["password"],
)


# Get balance
usd_balance = float(bitget.get_usdt_equity())
print("USD balance :", round(usd_balance, 2), "$")


positions_data = bitget.get_open_position()
position = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["info"]["marketPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["info"]["marketPrice"]), "open_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] == pair]

row = df.iloc[-1]


# Trading Account positions
if len(position) > 0:
    position = position[0]
    print(f"Current position : {position}")
    if position["side"] == "long" and close_long(row):
        close_long_market_price = float(df.iloc[-1]["close"])
        close_long_quantity = float(
            bitget.convert_amount_to_precision(pair, position["size"])
        )
        exchange_close_long_quantity = close_long_quantity * close_long_market_price
        print(
            f"Place Close Long Market Order: {close_long_quantity} {pair[:-5]} at the price of {close_long_market_price}$ ~{round(exchange_close_long_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "sell", close_long_quantity, reduce=True)

        short_market_price = float(df.iloc[-1]["close"])
        short_quantity_in_usd = usd_balance * 1
        short_quantity = float(bitget.convert_amount_to_precision(pair, float(
            bitget.convert_amount_to_precision(pair, short_quantity_in_usd / short_market_price)
        )))
        exchange_short_quantity = short_quantity * short_market_price
        print(
            f"Place Open Short Market Order: {short_quantity} {pair[:-5]} at the price of {short_market_price}$ ~{round(exchange_short_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "sell", short_quantity, reduce=False)



    elif position["side"] == "short" and close_short(row):
        close_short_market_price = float(df.iloc[-1]["close"])
        close_short_quantity = float(
            bitget.convert_amount_to_precision(pair, position["size"])
        )
        exchange_close_short_quantity = close_short_quantity * close_short_market_price
        print(
            f"Place Close Short Market Order: {close_short_quantity} {pair[:-5]} at the price of {close_short_market_price}$ ~{round(exchange_close_short_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "buy", close_short_quantity, reduce=True)

        long_market_price = float(df.iloc[-1]["close"])
        long_quantity_in_usd = usd_balance * leverage
        long_quantity = float(bitget.convert_amount_to_precision(pair, float(
            bitget.convert_amount_to_precision(pair, long_quantity_in_usd / long_market_price)
        )))
        exchange_long_quantity = long_quantity * long_market_price
        print(
            f"Place Open Long Market Order: {long_quantity} {pair[:-5]} at the price of {long_market_price}$ ~{round(exchange_long_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "buy", long_quantity, reduce=False)


else:
    print("No active position")
    if open_long(row) and "long" in type:
        long_market_price = float(df.iloc[-1]["close"])
        long_quantity_in_usd = usd_balance * leverage
        long_quantity = float(bitget.convert_amount_to_precision(pair, float(
            bitget.convert_amount_to_precision(pair, long_quantity_in_usd / long_market_price)
        )))
        exchange_long_quantity = long_quantity * long_market_price
        print(
            f"Place Open Long Market Order: {long_quantity} {pair[:-5]} at the price of {long_market_price}$ ~{round(exchange_long_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "buy", long_quantity, reduce=False)

    elif open_short(row) and "short" in type:
        short_market_price = float(df.iloc[-1]["close"])
        short_quantity_in_usd = usd_balance * 1
        short_quantity = float(bitget.convert_amount_to_precision(pair, float(
            bitget.convert_amount_to_precision(pair, short_quantity_in_usd / short_market_price)
        )))
        exchange_short_quantity = short_quantity * short_market_price
        print(
            f"Place Open Short Market Order: {short_quantity} {pair[:-5]} at the price of {short_market_price}$ ~{round(exchange_short_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "sell", short_quantity, reduce=False)

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- End Execution Time :", current_time, "---")
