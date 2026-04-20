import os
import logging
import json
import hashlib
import hmac
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext

# Загружаем переменные окружения
load_dotenv()

# Версия бота
BOT_VERSION = "1.0.1"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Получаем переменные
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER = os.getenv('AUTHORIZED_USER')
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY_DEMO')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET_DEMO')

# Проверка переменных
if not all([TOKEN, AUTHORIZED_USER, BYBIT_API_KEY, BYBIT_API_SECRET]):
    logger.error("❌ Отсутствуют переменные окружения!")
    raise ValueError("Проверьте .env файл")

# Bybit API endpoints (testnet)
BYBIT_REST_URL = "https://api-testnet.bybit.com"

def is_authorized(update: Update) -> bool:
    """Проверка авторизации"""
    user_id = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
    authorized = user_id == AUTHORIZED_USER or str(update.effective_user.id) == AUTHORIZED_USER.replace('@', '')
    
    if not authorized:
        logger.warning(f"⛔ Неавторизованный доступ от {user_id}")
    
    return authorized

def generate_bybit_signature(params, secret):
    """Генерация подписи для Bybit API"""
    param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
    signature = hmac.new(
        bytes(secret, 'utf-8'),
        bytes(param_str, 'utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

def get_bybit_balance():
    """Получение баланса через Bybit API"""
    try:
        logger.info("🔄 Запрос баланса Bybit testnet...")
        
        # Параметры запроса
        timestamp = int(time.time() * 1000)
        params = {
            'api_key': BYBIT_API_KEY,
            'timestamp': timestamp,
        }
        
        # Генерация подписи
        params['sign'] = generate_bybit_signature(params, BYBIT_API_SECRET)
        
        # Запрос к API
        headers = {
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{BYBIT_REST_URL}/v5/account/wallet-balance",
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['retCode'] == 0:
                logger.info("✅ Баланс успешно получен")
                return data
            else:
                logger.error(f"❌ Ошибка API: {data['retMsg']}")
                return None
        else:
            logger.error(f"❌ HTTP ошибка: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения баланса: {e}", exc_info=True)
        return None

def format_balance_message(balance_data):
    """Форматирование баланса для сообщения"""
    try:
        if not balance_data or balance_data.get('retCode') != 0:
            return "❌ Не удалось получить баланс"
        
        # Парсим баланс
        result = balance_data.get('result', {})
        wallet_balance = result.get('list', [{}])[0].get('coin', [])
        
        if not wallet_balance:
            return "💼 Баланс пуст"
        
        balance_lines = ["💼 <b>Ваш баланс на Bybit Testnet:</b>\n"]
        total_usdt = 0
        
        for coin in wallet_balance:
            coin_name = coin.get('coin', '')
            wallet = coin.get('walletBalance', '0')
            
            if float(wallet) > 0:
                balance_lines.append(f"• <b>{coin_name}:</b> {float(wallet):.8f}")
                if coin_name == 'USDT':
                    total_usdt += float(wallet)
        
        if total_usdt > 0:
            balance_lines.append(f"\n💰 <b>Общий баланс (USDT):</b> {total_usdt:.2f}")
        
        return "\n".join(balance_lines)
        
    except Exception as e:
        logger.error(f"❌ Ошибка форматирования: {e}")
        return "❌ Ошибка обработки баланса"

def start(update: Update, context: CallbackContext):
    """Команда /start"""
    try:
        logger.info(f"📱 /start от @{update.effective_user.username}")
        
        if not is_authorized(update):
            update.message.reply_text("⛔ У вас нет доступа!")
            return
        
        welcome_text = f"""
🤖 <b>Бот Bybit Testnet</b>
📦 <b>Версия:</b> {BOT_VERSION}
✅ <b>Статус:</b> Активен
🔗 <b>Биржа:</b> Bybit Testnet
👤 <b>Авторизован:</b> {AUTHORIZED_USER}

🔄 /balance - показать баланс
ℹ️ /version - версия бота
        """
        
        update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)
        logger.info(f"✅ Приветствие отправлено")
        
    except Exception as e:
        logger.error(f"❌ Ошибка /start: {e}")

def balance(update: Update, context: CallbackContext):
    """Команда /balance"""
    try:
        logger.info(f"💰 /balance от @{update.effective_user.username}")
        
        if not is_authorized(update):
            update.message.reply_text("⛔ Нет доступа!")
            return
        
        update.message.reply_text("🔄 Получение баланса...")
        
        balance_data = get_bybit_balance()
        balance_text = format_balance_message(balance_data)
        
        # Добавляем версию и время
        balance_text += f"\n\n📦 <b>Версия бота:</b> {BOT_VERSION}"
        balance_text += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        update.message.reply_text(balance_text, parse_mode=ParseMode.HTML)
        logger.info(f"✅ Баланс отправлен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка /balance: {e}")
        update.message.reply_text("⚠️ Ошибка получения баланса")

def version(update: Update, context: CallbackContext):
    """Команда /version"""
    try:
        logger.info(f"ℹ️ /version от @{update.effective_user.username}")
        
        if not is_authorized(update):
            update.message.reply_text("⛔ Нет доступа!")
            return
        
        version_text = f"""
📦 <b>Информация о боте:</b>

• <b>Версия:</b> {BOT_VERSION}
• <b>Биржа:</b> Bybit Testnet
• <b>Автор:</b> {AUTHORIZED_USER}
• <b>Статус:</b> ✅ Работает
• <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        update.message.reply_text(version_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"❌ Ошибка /version: {e}")

def unknown(update: Update, context: CallbackContext):
    """Неизвестные команды"""
    logger.info(f"❓ Неизвестная команда: {update.message.text}")
    update.message.reply_text("❓ Используйте /start, /balance или /version")

def main():
    """Запуск бота"""
    logger.info(f"🚀 Запуск бота версии {BOT_VERSION}")
    logger.info(f"👤 Авторизован: {AUTHORIZED_USER}")
    
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("version", version))
    dispatcher.add_handler(CommandHandler("help", start))
    
    updater.start_polling()
    logger.info("✅ Бот запущен и готов к работе!")
    
    updater.idle()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)