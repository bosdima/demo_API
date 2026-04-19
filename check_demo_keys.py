#!/usr/bin/env python3
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv

load_dotenv()

# Пробуем разные варианты ключей
demo_key = os.getenv('BYBIT_API_KEY_DEMO') or os.getenv('BYBIT_API_KEY')
demo_secret = os.getenv('BYBIT_API_SECRET_DEMO') or os.getenv('BYBIT_API_SECRET')

print(f"🔑 DEMO KEY: {demo_key[:10]}...{demo_key[-5:] if demo_key else 'None'}")
print(f"🔐 DEMO SECRET: {'*' * 10 if demo_secret else 'None'}")
print()

if not demo_key or not demo_secret:
    print("❌ Ключи не найдены в .env")
    exit(1)

# Проверяем подключение к testnet
print("🔄 Проверка подключения к testnet.bybit.com...")
try:
    session = HTTP(testnet=True, api_key=demo_key, api_secret=demo_secret)
    
    # 1. Проверка баланса
    print("1. Запрос баланса...")
    balance = session.get_wallet_balance(accountType="UNIFIED")
    if balance['retCode'] == 0:
        print("✅ Баланс получен!")
        total = balance['result']['list'][0].get('totalEquity', 0)
        print(f"   Общий баланс: {total} USDT")
        coins = balance['result']['list'][0].get('coin', [])
        for c in coins:
            if float(c.get('walletBalance', 0)) > 0:
                print(f"   {c['coin']}: {c['walletBalance']}")
    else:
        print(f"❌ Ошибка баланса: {balance}")
        exit(1)
    
    # 2. Проверка получения цены
    print("\n2. Запрос цены TONUSDT...")
    ticker = session.get_tickers(category="spot", symbol="TONUSDT")
    if ticker['retCode'] == 0:
        price = ticker['result']['list'][0]['lastPrice']
        print(f"✅ Цена TONUSDT: {price}")
    else:
        print(f"❌ Ошибка цены: {ticker}")
    
    print("\n🎉 Все проверки пройдены! Ключи работают.")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()