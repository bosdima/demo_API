import os
import logging
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ParseMode, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext

# Загружаем переменные окружения
load_dotenv()

BOT_VERSION = "1.0.6"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER = os.getenv('AUTHORIZED_USER')
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY_DEMO')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET_DEMO')

if not all([TOKEN, AUTHORIZED_USER, BYBIT_API_KEY, BYBIT_API_SECRET]):
    logger.error("❌ Отсутствуют переменные окружения!")
    raise ValueError("Проверьте .env файл")

def is_authorized(update: Update) -> bool:
    user_id = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
    return user_id == AUTHORIZED_USER or str(update.effective_user.id) == AUTHORIZED_USER.replace('@', '')

def get_bybit_balance():
    try:
        import hashlib, hmac
        
        timestamp = int(time.time() * 1000)
        param_str = f"{timestamp}{BYBIT_API_KEY}5000"
        signature = hmac.new(
            bytes(BYBIT_API_SECRET, 'utf-8'),
            bytes(param_str, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-BAPI-API-KEY': BYBIT_API_KEY,
            'X-BAPI-TIMESTAMP': str(timestamp),
            'X-BAPI-SIGN': signature,
            'X-BAPI-RECV-WINDOW': '5000',
        }
        
        response = requests.get(
            "https://api-testnet.bybit.com/v5/account/wallet-balance",
            headers=headers,
            params={"accountType": "UNIFIED"},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return None

def start(update: Update, context: CallbackContext):
    if not is_authorized(update):
        update.message.reply_text("⛔ Нет доступа!")
        return
    
    update.message.reply_text(f"""
🤖 Бот Bybit Testnet
📦 Версия: {BOT_VERSION}
✅ Статус: Активен
👤 Авторизован: {AUTHORIZED_USER}

/balance - баланс
/version - версия
    """)

def balance(update: Update, context: CallbackContext):
    if not is_authorized(update):
        update.message.reply_text("⛔ Нет доступа!")
        return
    
    update.message.reply_text("🔄 Получение баланса...")
    data = get_bybit_balance()
    
    if not data or data.get('retCode') != 0:
        update.message.reply_text("❌ Ошибка получения баланса")
        return
    
    balances = data.get('result', {}).get('list', [{}])[0].get('coin', [])
    if not balances:
        update.message.reply_text("💼 Баланс пуст")
        return
    
    text = "💼 Баланс:\n"
    for coin in balances:
        amount = float(coin.get('walletBalance', 0))
        if amount > 0:
            text += f"• {coin.get('coin')}: {amount:.8f}\n"
    
    update.message.reply_text(text)

def version(update: Update, context: CallbackContext):
    if not is_authorized(update):
        update.message.reply_text("⛔ Нет доступа!")
        return
    
    update.message.reply_text(f"📦 Версия: {BOT_VERSION}")

def main():
    logger.info(f"🚀 Запуск бота v{BOT_VERSION}")
    
    # Удаляем webhook
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
    
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("balance", balance))
    dp.add_handler(CommandHandler("version", version))
    
    updater.start_polling()
    logger.info("✅ Бот запущен!")
    updater.idle()

if __name__ == '__main__':
    main()