import os
import logging
import time
import requests
import sys
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from telegram import Update, ParseMode, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackContext
from queue import Queue

# Загружаем переменные окружения
load_dotenv()

# Версия бота
BOT_VERSION = "1.0.7"

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

# Проверка переменных
if not all([TOKEN, AUTHORIZED_USER, BYBIT_API_KEY, BYBIT_API_SECRET]):
    logger.error("❌ Отсутствуют переменные окружения!")
    sys.exit(1)

# Создаем бота
bot = Bot(token=TOKEN)
update_queue = Queue()
dispatcher = Dispatcher(bot, update_queue, use_context=True)

def is_authorized(update: Update) -> bool:
    """Проверка авторизации"""
    user_id = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
    authorized = user_id == AUTHORIZED_USER or str(update.effective_user.id) == AUTHORIZED_USER.replace('@', '')
    return authorized

def get_bybit_balance():
    """Получение баланса через API Bybit"""
    try:
        import hashlib
        import hmac
        
        logger.info("🔄 Запрос баланса...")
        
        timestamp = int(time.time() * 1000)
        recv_window = '5000'
        
        # Правильная подпись для Bybit API v5
        param_str = f"{timestamp}{BYBIT_API_KEY}{recv_window}"
        signature = hmac.new(
            bytes(BYBIT_API_SECRET, 'utf-8'),
            bytes(param_str, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-BAPI-API-KEY': BYBIT_API_KEY,
            'X-BAPI-TIMESTAMP': str(timestamp),
            'X-BAPI-SIGN': signature,
            'X-BAPI-RECV-WINDOW': recv_window,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            "https://api-testnet.bybit.com/v5/account/wallet-balance",
            headers=headers,
            params={"accountType": "UNIFIED"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('retCode') == 0:
                logger.info("✅ Баланс получен")
                return data
            else:
                logger.error(f"API error: {data.get('retMsg')}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

def format_balance(balance_data):
    """Форматирование баланса"""
    try:
        if not balance_data or balance_data.get('retCode') != 0:
            return "❌ Ошибка получения баланса"
        
        balances = balance_data.get('result', {}).get('list', [{}])[0].get('coin', [])
        if not balances:
            return "💼 Баланс пуст"
        
        lines = ["💼 <b>Баланс на Bybit Testnet:</b>\n"]
        for coin in balances:
            amount = float(coin.get('walletBalance', 0))
            if amount > 0:
                lines.append(f"• <b>{coin.get('coin')}:</b> {amount:.8f}")
        
        if len(lines) == 1:
            return "💼 Нет монет с ненулевым балансом"
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Format error: {e}")
        return "❌ Ошибка форматирования"

def start(update: Update, context: CallbackContext):
    """/start"""
    if not is_authorized(update):
        update.message.reply_text("⛔ Нет доступа!")
        return
    
    text = f"""
🤖 <b>Бот Bybit Testnet</b>
📦 <b>Версия:</b> {BOT_VERSION}
✅ <b>Статус:</b> Активен
👤 <b>Авторизован:</b> {AUTHORIZED_USER}

/balance - показать баланс
/version - версия бота
    """
    update.message.reply_text(text, parse_mode=ParseMode.HTML)

def balance(update: Update, context: CallbackContext):
    """/balance"""
    if not is_authorized(update):
        update.message.reply_text("⛔ Нет доступа!")
        return
    
    update.message.reply_text("🔄 Получение баланса...")
    data = get_bybit_balance()
    text = format_balance(data)
    text += f"\n\n📦 Версия: {BOT_VERSION}\n🕐 {datetime.now().strftime('%H:%M:%S')}"
    update.message.reply_text(text, parse_mode=ParseMode.HTML)

def version(update: Update, context: CallbackContext):
    """/version"""
    if not is_authorized(update):
        update.message.reply_text("⛔ Нет доступа!")
        return
    
    text = f"📦 Версия: {BOT_VERSION}\n✅ Бот работает"
    update.message.reply_text(text)

# Регистрируем команды
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("balance", balance))
dispatcher.add_handler(CommandHandler("version", version))

# Flask приложение
app = Flask(__name__)

@app.route(f'/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint"""
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return jsonify({'ok': True}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'ok': False}), 500

@app.route('/', methods=['GET'])
def index():
    return f"Bot v{BOT_VERSION} is running", 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': BOT_VERSION}), 200

if __name__ == '__main__':
    logger.info(f"🚀 Запуск бота v{BOT_VERSION}")
    logger.info(f"👤 Авторизован: {AUTHORIZED_USER}")
    
    # Принудительно удаляем все webhook и останавливаем polling
    try:
        # Останавливаем любые существующие webhook
        url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
        response = requests.get(url)
        logger.info(f"Webhook удален: {response.json()}")
        
        # Дополнительно отправляем stopPolling (не официально, но помогает)
        time.sleep(2)
        
    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {e}")
    
    # Получаем порт от хостинга
    port = int(os.getenv('PORT', 3000))
    
    # Настраиваем webhook с правильным URL
    # Для bothost.ru используем переменную окружения RENDER_EXTERNAL_URL или PUBLIC_URL
    public_url = os.getenv('PUBLIC_URL', os.getenv('RENDER_EXTERNAL_URL', ''))
    
    if not public_url:
        # Пробуем определить автоматически
        host = os.getenv('HOST', '')
        if host:
            public_url = f"https://{host}"
        else:
            # Если не можем определить, используем polling как fallback
            logger.warning("⚠️ Не удалось определить публичный URL, запуск в polling режиме")
            from telegram.ext import Updater
            updater = Updater(token=TOKEN, use_context=True)
            dispatcher_polling = updater.dispatcher
            dispatcher_polling.add_handler(CommandHandler("start", start))
            dispatcher_polling.add_handler(CommandHandler("balance", balance))
            dispatcher_polling.add_handler(CommandHandler("version", version))
            updater.start_polling()
            logger.info("✅ Polling режим запущен")
            updater.idle()
            sys.exit(0)
    
    webhook_url = f"{public_url}/webhook"
    
    # Устанавливаем webhook
    try:
        set_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
        response = requests.post(set_url, json={'url': webhook_url})
        result = response.json()
        
        if result.get('ok'):
            logger.info(f"✅ Webhook установлен: {webhook_url}")
        else:
            logger.error(f"❌ Ошибка webhook: {result}")
            logger.info("Переход в polling режим...")
            from telegram.ext import Updater
            updater = Updater(token=TOKEN, use_context=True)
            dispatcher_polling = updater.dispatcher
            dispatcher_polling.add_handler(CommandHandler("start", start))
            dispatcher_polling.add_handler(CommandHandler("balance", balance))
            dispatcher_polling.add_handler(CommandHandler("version", version))
            updater.start_polling()
            updater.idle()
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}")
    
    # Запускаем Flask сервер
    logger.info(f"🌐 Запуск сервера на порту {port}")
    app.run(host='0.0.0.0', port=port)