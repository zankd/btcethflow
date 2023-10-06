import websocket
import json
import pprint
import csv
import datetime
from binance.client import Client
from binance.enums import *
from colorama import Fore, init
import time
import config

client = Client(config.TAPI_KEY, config.TAPI_SECRET)
client.API_URL = 'https://testnet.binance.vision/api'

start_time = datetime.datetime.now()
elapsed_time_minutes = 0  

SOCKET = "wss://testnet.binance.vision/ws/btcusdt@kline_1m"
TRADE_SYMBOL = 'ETHUSDT'
TRADE_QUANTITY = 0.01
holding_eth = False

# Init colorama
init()

def order(side, quantity, symbol, order_type=ORDER_TYPE_MARKET):
    try:
        print("Sending order")
        order = client.create_test_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        print(order)

        time = order['transactTime']
        order_id = order['orderId']
        status = order['status']
        order_price = order['price']
        profit_usdt = order['cummulativeQuoteQty']
        commission = order['commission']
        profit_after_commission = profit_usdt - commission

        # Write the trade details
        with open('flowtrades.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow((time, side, quantity, symbol, order_type, order_id, status, order_price, profit_usdt, profit_after_commission))
    except Exception as e:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open('flowerrors.txt', 'a') as f:
            f.write("{} - An exception occurred - {}\n".format(current_time, e))
        return False

    return order['price']

def on_open(ws):
    global elapsed_time_minutes
    print('Opened connection')
    elapsed_time_minutes = (datetime.datetime.now() - start_time).total_seconds() / 60

def on_close(ws, close_status_code, close_msg):
    print('Closed connection')

def print_candle_info(close, btc_increase):
    print("Candle closed at {:.2f}".format(close))
    
    # Define a tolerance level for comparison
    tolerance = 0.0001 
    
    if abs(btc_increase) < tolerance:
        btc_increase = 0.0  
    print("BTC increase: {}%".format(Fore.RED + "{:.4f}".format(btc_increase) + Fore.RESET))


def on_message(ws, message):
    global elapsed_time_minutes, holding_eth 
    print('Received message')
    json_message = json.loads(message)
    pprint.pprint(json_message)

    candle = json_message['k']
    is_candle_closed = candle['x']
    close = float(candle['c'])

    btc_ticker = client.get_ticker(symbol='BTCUSDT')
    btc_price = float(btc_ticker['lastPrice'])
    btc_increase = (btc_price - close) / close * 100

    if is_candle_closed:
        current_time = datetime.datetime.now()
        elapsed_time_minutes = (current_time - start_time).total_seconds() / 60

        if elapsed_time_minutes >= 3:
            print_candle_info(close, btc_increase)

            # Place a buy order if BTC increase is greater than 0.1%
            if btc_increase > 0.1 and not holding_eth:
                # Place a buy order for 0.1 ETH
                buy_price = order(SIDE_BUY, TRADE_QUANTITY, TRADE_SYMBOL)
                if buy_price:
                    # Set the flag to indicate that you are holding ETH
                    holding_eth = True
                    print("Buy Order Placed: Price={}, Quantity={}".format(buy_price, TRADE_QUANTITY))
            elif holding_eth and btc_increase < -0.1:
                # Place a sell order for 0.1 ETH
                order(SIDE_SELL, TRADE_QUANTITY, TRADE_SYMBOL)
                # Reset the flag to indicate that you are no longer holding ETH
                holding_eth = False
                print("Sell Order Placed: Price={}, Quantity={}".format(btc_price, TRADE_QUANTITY))

    # Check if you are holding ETH and if the price has increased by 2%
    if holding_eth:
        eth_ticker = client.get_symbol_ticker('ETHUSDT')
        eth_price = float(eth_ticker['last'])
        eth_increase = (eth_price - buy_price) / buy_price * 100

        # Check if the increase is greater than 2%
        if eth_increase > 2:
            # Place a sell order for 0.1 ETH
            order(SIDE_SELL, TRADE_QUANTITY, TRADE_SYMBOL)
            # Reset the flag to indicate that you are no longer holding ETH
            holding_eth = False

            print("Sell Order Placed: Price={}, Quantity={}".format(eth_price, TRADE_QUANTITY))


def on_error(ws, error):
    print(f"Error: {error}")

try:
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message, on_error=on_error)
    ws.run_forever()
except KeyboardInterrupt:
    ws.close()
except Exception as e:
    print(f"Unexpected error: {e}")
