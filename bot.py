import os
import logging
import time
import requests
import hashlib
import hmac
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext

# Загружаем переменные
load_dotenv()

BOT_VERSION = "1.0.9"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем переменные
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER = os.getenv('AUTHORIZED_USER')
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY_DEMO')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET_DEMO')

if not all([TOKEN, AUTHORIZED_USER, BYBIT_API_KEY, BYBIT_API_SECRET]):
    logger.error("❌ Отсутствуют переменные окружения!")
    raise ValueError("Проверьте .env файл")

def is_authorized(update: Update) -> bool:
    """Проверка авторизации"""
    user_id = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
    return user_id == AUTHORIZED_USER or str(update.effective_user.id) == AUTHORIZED_USER.replace('@', '')

def get_bybit_balance():
    """Получение баланса с Bybit testnet - ИСПРАВЛЕННАЯ ПОДПИСЬ"""
    try:
        logger.info("🔄 Запрос баланса...")
        
        timestamp = int(time.time() * 1000)
        
        # Для GET запроса с параметрами
        params = {
            "accountType": "UNIFIED",
            "coin": "USDT"
        }
        
        # Сортируем параметры и создаем строку запроса
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        
        # Строка для подписи
        param_str = f"{timestamp}{BYBIT_API_KEY}{query_string}"
        
        logger.info(f"Строка для подписи: {param_str}")
        
        # Создаем подпись
        signature = hmac.new(
            BYBIT_API_SECRET.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Заголовки
        headers = {
            'X-BAPI-API-KEY': BYBIT_API_KEY,
            'X-BAPI-TIMESTAMP': str(timestamp),
            'X-BAPI-SIGN': signature,
            'X-BAPI-RECV-WINDOW': '5000',
            'Content-Type': 'application/json'
        }
        
        # Полный URL с параметрами
        url = f"https://api-testnet.bybit.com/v5/account/wallet-balance?{query_string}"
        
        logger.info(f"URL: {url}")
        
        response = requests.get(url, headers=headers, timeout=10)
        
        logger.info(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('retCode') == 0:
                logger.info("✅ Баланс получен")
                return data
            else:
                logger.error(f"API error: {data.get('retMsg')}")
                logger.error(f"Full response: {data}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code}, {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return None

def format_balance(balance_data):
    """Форматирование баланса"""
    try:
        if not balance_data or balance_data.get('retCode') != 0:
            return "❌ Не удалось получить баланс. Проверьте API ключи."
        
        # Парсим ответ
        result = balance_data.get('result', {})
        accounts = result.get('list', [])
        
        if not accounts:
            return "💼 Баланс пуст"
        
        # Берем первый аккаунт (обычно UNIFIED)
        account = accounts[0]
        coins = account.get('coin', [])
        
        if not coins:
            return "💼 Нет монет"
        
        text = "💼 <b>Баланс на Bybit Testnet:</b>\n\n"
        has_balance = False
        
        for coin in coins:
            coin_name = coin.get('coin', '')
            wallet_balance = float(coin.get('walletBalance', 0))
            equity = float(coin.get('equity', 0))
            
            if wallet_balance > 0 or equity > 0:
                has_balance = True
                text += f"• <b>{coin_name}:</b>\n"
                text += f"  Кошелек: {wallet_balance:.8f}\n"
                if equity != wallet_balance:
                    text += f"  Эквити: {equity:.8f}\n"
        
        if not has_balance:
            text = "💼 Нет монет с ненулевым балансом"
        
        return text
        
    except Exception as e:
        logger.error(f"Format error: {e}", exc_info=True)
        return "❌ Ошибка форматирования баланса"

def start(update: Update, context: CallbackContext):
    """Команда /start"""
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
    """Команда /balance"""
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
    """Команда /version"""
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
    """Запуск бота"""
    logger.info(f"🚀 Запуск бота v{BOT_VERSION}")
    logger.info(f"👤 Авторизован: {AUTHORIZED_USER}")
    
    # Принудительно удаляем webhook
    try:
        response = requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
        logger.info(f"Webhook удален: {response.json()}")
    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {e}")
    
    # Создаем updater
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # Регистрируем команды
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("version", version))
    
    # Запускаем polling
    updater.start_polling(clean=True, drop_pending_updates=True)
    logger.info("✅ Бот запущен и готов к работе!")
    
    # Останавливаем бота при сигнале
    updater.idle()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)