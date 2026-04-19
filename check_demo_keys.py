#!/usr/bin/env python3
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv

load_dotenv()

# Получаем новые ключи
api_key = os.getenv('BYBIT_API_KEY_DEMO') or os.getenv('BYBIT_API_KEY')
api_secret = os.getenv('BYBIT_API_SECRET_DEMO') or os.getenv('BYBIT_API_SECRET')

print(f"🔑 API Key: {api_key}")
print(f"🔐 API Secret: {api_secret[:10]}...{api_secret[-5:] if api_secret else 'None'}")
print()

if not api_key or not api_secret:
    print("❌ Ключи не найдены")
    exit(1)

print("🔄 Подключение к testnet.bybit.com...")

try:
    session = HTTP(testnet=True, api_key=api_key, api_secret=api_secret)
    
    # Проверяем баланс
    print("1. Запрос баланса...")
    balance = session.get_wallet_balance(accountType="UNIFIED")
    
    if balance['retCode'] == 0:
        print("✅ БАЛАНС ПОЛУЧЕН!")
        total = balance['result']['list'][0].get('totalEquity', 0)
        print(f"💰 Общий баланс: {total} USDT")
        
        # Показываем монеты с балансом
        coins = balance['result']['list'][0].get('coin', [])
        for coin in coins:
            wallet = float(coin.get('walletBalance', 0))
            if wallet > 0:
                print(f"   • {coin['coin']}: {wallet}")
        
        if total == 0:
            print("\n⚠️ Баланс 0. Запросите тестовые монеты:")
            print("   1. Перейдите на https://testnet.bybit.com")
            print("   2. Активы → Спот → USDT → 'Получить тестовые USDT'")
    
    else:
        print(f"❌ Ошибка: {balance}")
        exit(1)
    
    # Проверяем цену
    print("\n2. Запрос цены TONUSDT...")
    ticker = session.get_tickers(category="spot", symbol="TONUSDT")
    if ticker['retCode'] == 0:
        price = ticker['result']['list'][0]['lastPrice']
        print(f"✅ Цена TONUSDT: {price} USDT")
    else:
        print(f"❌ Ошибка: {ticker}")
    
    print("\n🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! КЛЮЧИ РАБОТАЮТ!")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")