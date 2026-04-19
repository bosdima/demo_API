#!/usr/bin/env python3
"""
Проверка API ключей для Bybit Testnet (v3 API)
Запуск: python check_demo_keys.py
"""

import os
import sys
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

print("="*60)
print("🔧 ПРОВЕРКА API КЛЮЧЕЙ ДЛЯ BYBIT TESTNET (v3 API)")
print("="*60)

# Получаем ключи из .env
demo_key = os.getenv('BYBIT_API_KEY_DEMO') or os.getenv('BYBIT_API_KEY')
demo_secret = os.getenv('BYBIT_API_SECRET_DEMO') or os.getenv('BYBIT_API_SECRET')

print(f"\n📋 Найденные ключи:")
print(f"   API Key: {demo_key[:15] if demo_key else '❌ НЕ НАЙДЕН'}...")
print(f"   API Secret: {'✅ НАЙДЕН' if demo_secret else '❌ НЕ НАЙДЕН'}")

if not demo_key or not demo_secret:
    print("\n❌ ОШИБКА: Ключи не найдены в файле .env")
    print("\nДобавьте в файл .env:")
    print("  BYBIT_API_KEY_DEMO=ваш_ключ_с_testnet_bybit")
    print("  BYBIT_API_SECRET_DEMO=ваш_секрет_с_testnet_bybit")
    exit(1)

# Пробуем импортировать pybit
try:
    from pybit import HTTP
    print("✅ pybit версия 4.1.0 загружена")
except ImportError:
    print("❌ pybit не установлен. Установите: pip install pybit==4.1.0")
    exit(1)

# Пробуем разные endpoint'ы
endpoints = [
    ("https://api-testnet.bybit.com", "Testnet (рекомендуется)"),
    ("https://api.bybit.com", "Mainnet (реальная биржа)"),
]

success = False

for endpoint, description in endpoints:
    print(f"\n{'='*60}")
    print(f"🔄 Проверка: {description}")
    print(f"   Endpoint: {endpoint}")
    print(f"{'='*60}")
    
    try:
        # Создаём сессию
        session = HTTP(
            endpoint=endpoint,
            api_key=demo_key,
            api_secret=demo_secret
        )
        
        # 1. Проверка баланса USDT
        print("\n1. Запрос баланса USDT...")
        try:
            balance = session.get_wallet_balance(coin="USDT")
            if balance['ret_code'] == 0:
                print("   ✅ Баланс USDT получен!")
                usdt_balance = balance['result']['USDT']['available_balance']
                print(f"   💰 Доступно USDT: {usdt_balance}")
                
                if float(usdt_balance) > 0:
                    print(f"   ✅ На счету есть средства!")
                else:
                    print(f"   ⚠️ Баланс 0. Запросите тестовые USDT на сайте testnet.bybit.com")
            else:
                print(f"   ❌ Ошибка: {balance.get('ret_msg', 'Unknown error')}")
                continue
        except Exception as e:
            print(f"   ❌ Исключение: {str(e)[:100]}")
            continue
        
        # 2. Проверка информации об аккаунте
        print("\n2. Запрос информации об аккаунте...")
        try:
            info = session.get_account_info()
            if info['ret_code'] == 0:
                print(f"   ✅ Аккаунт найден!")
                print(f"   👤 UID: {info['result'].get('uid', 'N/A')}")
                print(f"   📧 Email: {info['result'].get('email', 'N/A')}")
            else:
                print(f"   ❌ Ошибка: {info.get('ret_msg', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Исключение: {str(e)[:100]}")
        
        # 3. Проверка получения цены (публичный запрос, не требует ключей)
        print("\n3. Запрос цены TONUSDT...")
        try:
            ticker = session.get_ticker(symbol="TONUSDT")
            if ticker['ret_code'] == 0:
                price = ticker['result']['last_price']
                print(f"   ✅ Цена TONUSDT: {price} USDT")
            else:
                print(f"   ❌ Ошибка: {ticker.get('ret_msg', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Исключение: {str(e)[:100]}")
        
        # Если дошли сюда - ключи работают!
        print(f"\n{'='*60}")
        print("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! КЛЮЧИ РАБОТАЮТ!")
        print(f"✅ Используйте endpoint: {endpoint}")
        print(f"📝 Режим: {description}")
        print(f"{'='*60}")
        success = True
        break
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {str(e)[:150]}")
        continue

if not success:
    print("\n" + "="*60)
    print("❌ НЕ УДАЛОСЬ ПОДКЛЮЧИТЬСЯ НИ К ОДНОМУ ENDPOINT'У")
    print("="*60)
    print("\n🔧 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
    print("   1. Неверные API ключи")
    print("   2. Ключи созданы на неправильном сайте")
    print("   3. Аккаунт на testnet не активирован")
    print("   4. Проблемы с интернет-соединением")
    print("\n💡 РЕШЕНИЕ:")
    print("   1. Перейдите на https://testnet.bybit.com")
    print("   2. Зарегистрируйтесь/войдите")
    print("   3. Создайте НОВЫЕ API ключи")
    print("   4. Включите 'Спот - ТОРГОВАТЬ'")
    print("   5. Скопируйте ключи в .env")
    print("   6. Запросите тестовые USDT в разделе 'Активы'")
    print("   7. Запустите этот скрипт снова")