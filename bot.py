import os
import logging
import time
import requests
import hashlib
import hmac
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext

load_dotenv()

BOT_VERSION = "1.0.15"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER = os.getenv('AUTHORIZED_USER')
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY_DEMO')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET_DEMO')

def is_authorized(update: Update) -> bool:
    user_id = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
    return user_id == AUTHORIZED_USER or str(update.effective_user.id) == AUTHORIZED_USER.replace('@', '')

def get_bybit_balance():
    """Получение баланса - пробуем разные типы аккаунтов"""
    try:
        logger.info("🔄 Запрос баланса...")
        timestamp = int(time.time() * 1000)
        
        # Пробуем разные типы аккаунтов
        account_types = ["UNIFIED", "SPOT", "FUND", "DERIVATIVES"]
        
        for acc_type in account_types:
            params = {"accountType": acc_type}
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
            recv_window = "5000"
            param_str = f"{timestamp}{BYBIT_API_KEY}{recv_window}{query_string}"
            
            signature = hmac.new(
                BYBIT_API_SECRET.encode('utf-8'),
                param_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            headers = {
                'X-BAPI-API-KEY': BYBIT_API_KEY,
                'X-BAPI-TIMESTAMP': str(timestamp),
                'X-BAPI-SIGN': signature,
                'X-BAPI-RECV-WINDOW': recv_window,
            }
            
            url = f"https://api-testnet.bybit.com/v5/account/wallet-balance?{query_string}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0:
                    coins = data.get('result', {}).get('list', [{}])[0].get('coin', [])
                    if coins:
                        logger.info(f"✅ Баланс найден в accountType: {acc_type}")
                        logger.info(f"Найдено монет: {len(coins)}")
                        return data
                    else:
                        logger.info(f"Тип {acc_type}: монет не найдено")
                else:
                    logger.error(f"API error for {acc_type}: {data.get('retMsg')}")
        
        logger.error("Не удалось получить баланс ни с одним типом аккаунта")
        return None
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return None

def format_balance(balance_data):
    """Форматирование баланса"""
    try:
        if not balance_data or balance_data.get('retCode') != 0:
            return "❌ Не удалось получить баланс"
        
        accounts = balance_data.get('result', {}).get('list', [])
        if not accounts:
            return "💼 Баланс пуст"
        
        text = "💼 <b>Баланс на Bybit Testnet:</b>\n\n"
        has_balance = False
        
        for account in accounts:
            coins = account.get('coin', [])
            for coin in coins:
                coin_name = coin.get('coin', '')
                wallet_balance = float(coin.get('walletBalance', 0))
                
                if wallet_balance > 0:
                    has_balance = True
                    if wallet_balance >= 1:
                        text += f"• <b>{coin_name}:</b> {wallet_balance:,.2f}\n"
                    else:
                        text += f"• <b>{coin_name}:</b> {wallet_balance:.8f}\n"
        
        if not has_balance:
            text = "💼 Нет монет с ненулевым балансом\n\nПроверьте что:\n1. API ключ создан на testnet.bybit.com\n2. У ключа есть права Read-Wallet и Read-Spot\n3. На демо-счете есть средства"
        
        return text
        
    except Exception as e:
        logger.error(f"Format error: {e}")
        return "❌ Ошибка форматирования баланса"

def start(update: Update, context: CallbackContext):
    if not is_authorized(update):
        update.message.reply_text("⛔ У вас нет доступа!")
        return
    
    text = f"""
🤖 <b>Бот Bybit Testnet</b>
📦 <b>Версия:</b> {BOT_VERSION}
✅ <b>Статус:</b> Активен
👤 <b>Авторизован:</b> {AUTHORIZED_USER}

<b>Доступные команды:</b>
/balance - показать баланс
/version - версия бота
    """
    update.message.reply_text(text, parse_mode=ParseMode.HTML)

def balance(update: Update, context: CallbackContext):
    if not is_authorized(update):
        update.message.reply_text("⛔ Нет доступа!")
        return
    
    update.message.reply_text("🔄 Получение баланса...")
    
    data = get_bybit_balance()
    text = format_balance(data)
    
    text += f"\n\n📦 <b>Версия:</b> {BOT_VERSION}"
    text += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    update.message.reply_text(text, parse_mode=ParseMode.HTML)

def version(update: Update, context: CallbackContext):
    if not is_authorized(update):
        update.message.reply_text("⛔ Нет доступа!")
        return
    
    text = f"""
📦 <b>Версия бота:</b> {BOT_VERSION}
✅ <b>Статус:</b> Работает
👤 <b>Автор:</b> {AUTHORIZED_USER}
🕐 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    update.message.reply_text(text, parse_mode=ParseMode.HTML)

def main():
    logger.info(f"🚀 Запуск бота v{BOT_VERSION}")
    logger.info(f"👤 Авторизован: {AUTHORIZED_USER}")
    
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
        time.sleep(1)
    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {e}")
    
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("balance", balance))
    dp.add_handler(CommandHandler("version", version))
    
    updater.start_polling(drop_pending_updates=True)
    logger.info("✅ Бот запущен и готов к работе!")
    
    updater.idle()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"💥 Ошибка: {e}")