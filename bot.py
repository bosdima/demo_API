import os
import logging
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from telegram import Update, ParseMode
from telegram.ext import Dispatcher, CommandHandler, CallbackContext

# Загружаем переменные окружения
load_dotenv()

# Версия бота
BOT_VERSION = "1.0.4"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем переменные
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER = os.getenv('AUTHORIZED_USER')
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY_DEMO')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET_DEMO')

# Flask приложение
app = Flask(__name__)

# Dispatcher для Telegram
dispatcher = Dispatcher(None, use_context=True)

# Проверка переменных
if not all([TOKEN, AUTHORIZED_USER, BYBIT_API_KEY, BYBIT_API_SECRET]):
    logger.error("❌ Отсутствуют переменные окружения!")
    raise ValueError("Проверьте .env файл")

def is_authorized(update: Update) -> bool:
    """Проверка авторизации"""
    user_id = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
    authorized = user_id == AUTHORIZED_USER or str(update.effective_user.id) == AUTHORIZED_USER.replace('@', '')
    return authorized

def get_bybit_balance():
    """Получение баланса через прямые запросы к API Bybit (исправленная подпись)"""
    try:
        import hashlib
        import hmac
        
        logger.info("🔄 Запрос баланса Bybit testnet...")
        
        # Для Bybit API v5 нужна специальная подпись
        timestamp = int(time.time() * 1000)
        recv_window = '5000'
        
        # Параметры для подписи
        param_str = f"{timestamp}{BYBIT_API_KEY}{recv_window}"
        
        # Создаем подпись
        signature = hmac.new(
            bytes(BYBIT_API_SECRET, 'utf-8'),
            bytes(param_str, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Заголовки для запроса
        headers = {
            'X-BAPI-API-KEY': BYBIT_API_KEY,
            'X-BAPI-TIMESTAMP': str(timestamp),
            'X-BAPI-SIGN': signature,
            'X-BAPI-RECV-WINDOW': recv_window,
            'Content-Type': 'application/json'
        }
        
        # Запрос к API (используем GET с параметрами)
        url = "https://api-testnet.bybit.com/v5/account/wallet-balance"
        params = {"accountType": "UNIFIED"}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('retCode') == 0:
                logger.info("✅ Баланс успешно получен")
                return data
            else:
                logger.error(f"❌ Ошибка API: {data.get('retMsg')}")
                return None
        else:
            logger.error(f"❌ HTTP ошибка: {response.status_code}, {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения баланса: {e}", exc_info=True)
        return None

def format_balance_message(balance_data):
    """Форматирование баланса"""
    try:
        if not balance_data or balance_data.get('retCode') != 0:
            return "❌ Не удалось получить баланс.\n\nПроверьте:\n1. API ключи созданы на testnet.bybit.com\n2. Ключи имеют права на чтение\n3. На счете есть средства"
        
        result = balance_data.get('result', {})
        balances = result.get('list', [{}])[0].get('coin', [])
        
        if not balances:
            return "💼 Баланс пуст (нет монет)"
        
        balance_lines = ["💼 <b>Баланс на Bybit Testnet:</b>\n"]
        total_usdt = 0
        
        for coin in balances:
            coin_name = coin.get('coin', '')
            wallet_balance = float(coin.get('walletBalance', 0))
            
            if wallet_balance > 0:
                balance_lines.append(f"• <b>{coin_name}:</b> {wallet_balance:.8f}")
                if coin_name == 'USDT':
                    total_usdt += wallet_balance
        
        if total_usdt > 0:
            balance_lines.append(f"\n💰 <b>Общий баланс:</b> {total_usdt:.2f} USDT")
        
        if len(balance_lines) == 1:
            return "💼 Нет монет с ненулевым балансом"
        
        return "\n".join(balance_lines)
        
    except Exception as e:
        logger.error(f"❌ Ошибка форматирования: {e}")
        return "❌ Ошибка обработки баланса"

# Обработчики команд
def start(update: Update, context: CallbackContext):
    """Команда /start"""
    try:
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
        logger.info(f"✅ Приветствие отправлено @{update.effective_user.username}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка /start: {e}")

def balance(update: Update, context: CallbackContext):
    """Команда /balance"""
    try:
        if not is_authorized(update):
            update.message.reply_text("⛔ Нет доступа!")
            return
        
        update.message.reply_text("🔄 Получение баланса...")
        
        balance_data = get_bybit_balance()
        balance_text = format_balance_message(balance_data)
        
        balance_text += f"\n\n📦 <b>Версия бота:</b> {BOT_VERSION}"
        balance_text += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        update.message.reply_text(balance_text, parse_mode=ParseMode.HTML)
        logger.info(f"✅ Баланс отправлен @{update.effective_user.username}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка /balance: {e}")
        update.message.reply_text("⚠️ Ошибка получения баланса")

def version(update: Update, context: CallbackContext):
    """Команда /version"""
    try:
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
    update.message.reply_text("❓ Используйте /start, /balance или /version")

# Регистрируем обработчики
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("balance", balance))
dispatcher.add_handler(CommandHandler("version", version))
dispatcher.add_handler(CommandHandler("help", start))

@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    """Webhook для получения обновлений от Telegram"""
    try:
        json_str = request.get_data().decode('UTF-8')
        update = Update.de_json(json_str, dispatcher.bot)
        dispatcher.process_update(update)
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"Ошибка webhook: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check для хостинга"""
    return jsonify({
        'status': 'running',
        'version': BOT_VERSION,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Главная страница"""
    return f"🤖 Bot is running! Version: {BOT_VERSION}", 200

def set_webhook():
    """Установка webhook для бота"""
    try:
        # Получаем URL из переменной окружения (bothost.ru дает PORT, но URL нужно узнать)
        # Для bothost.ru используем их домен
        host = os.getenv('HOST', 'localhost')
        port = os.getenv('PORT', '3000')
        
        # В bothost.ru URL будет примерно таким: https://bot-xxx.bothost.ru
        # Попробуем определить автоматически
        webhook_url = f"https://{host}/webhook/{TOKEN}" if host != 'localhost' else f"http://localhost:{port}/webhook/{TOKEN}"
        
        # Удаляем старый webhook
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
        
        # Устанавливаем новый webhook
        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/setWebhook",
            json={'url': webhook_url}
        )
        
        if response.json().get('ok'):
            logger.info(f"✅ Webhook установлен на {webhook_url}")
        else:
            logger.error(f"❌ Ошибка установки webhook: {response.json()}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка установки webhook: {e}")

if __name__ == '__main__':
    logger.info(f"🚀 Запуск бота версии {BOT_VERSION}")
    logger.info(f"👤 Авторизован: {AUTHORIZED_USER}")
    
    # Устанавливаем webhook
    set_webhook()
    
    # Запускаем Flask сервер
    port = int(os.getenv('PORT', 3000))
    logger.info(f"🌐 Запуск сервера на порту {port}")
    app.run(host='0.0.0.0', port=port)