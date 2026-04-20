import os
import logging
import json
import hashlib
import hmac
import time
import requests
import threading
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext
from http.server import HTTPServer, BaseHTTPRequestHandler

# Загружаем переменные окружения
load_dotenv()

# Версия бота
BOT_VERSION = "1.0.3"

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
PORT = int(os.getenv('PORT', 8080))

# Проверка переменных
if not all([TOKEN, AUTHORIZED_USER, BYBIT_API_KEY, BYBIT_API_SECRET]):
    logger.error("❌ Отсутствуют переменные окружения!")
    raise ValueError("Проверьте .env файл")

# Bybit API endpoints (правильные для testnet)
BYBIT_REST_URL = "https://api-testnet.bybit.com"

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Простой HTTP сервер для health checks"""
    
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"Bot is running! Version: {BOT_VERSION}".encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_http_server():
    """Запуск HTTP сервера для health checks"""
    try:
        server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
        logger.info(f"🌐 HTTP сервер запущен на порту {PORT}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Ошибка HTTP сервера: {e}")

def is_authorized(update: Update) -> bool:
    """Проверка авторизации"""
    user_id = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
    authorized = user_id == AUTHORIZED_USER or str(update.effective_user.id) == AUTHORIZED_USER.replace('@', '')
    
    if not authorized:
        logger.warning(f"⛔ Неавторизованный доступ от {user_id}")
    
    return authorized

def get_bybit_balance():
    """Получение баланса через Bybit API v5"""
    try:
        logger.info("🔄 Запрос баланса Bybit testnet...")
        
        timestamp = int(time.time() * 1000)
        
        # Для Bybit API v5 нужен другой формат подписи
        param_str = f"{timestamp}{BYBIT_API_KEY}{timestamp}5000"
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
            'Content-Type': 'application/json'
        }
        
        # Правильный endpoint для получения баланса
        response = requests.get(
            f"{BYBIT_REST_URL}/v5/account/wallet-balance",
            params={"accountType": "UNIFIED"},
            headers=headers,
            timeout=10
        )
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"API Response: {json.dumps(data, indent=2)}")
            
            if data['retCode'] == 0:
                logger.info("✅ Баланс успешно получен")
                return data
            else:
                logger.error(f"❌ Ошибка API: {data['retMsg']}")
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
            return "❌ Не удалось получить баланс. Проверьте API ключи."
        
        result = balance_data.get('result', {})
        
        # Пробуем разные форматы ответа
        if 'list' in result:
            wallet_balance = result.get('list', [{}])[0].get('coin', [])
        elif 'balances' in result:
            wallet_balance = result.get('balances', [])
        else:
            wallet_balance = []
        
        if not wallet_balance:
            return "💼 Баланс пуст или не найден"
        
        balance_lines = ["💼 <b>Ваш баланс на Bybit Testnet:</b>\n"]
        total_usdt = 0
        
        for coin in wallet_balance:
            coin_name = coin.get('coin', '')
            # Пробуем разные поля для баланса
            wallet = coin.get('walletBalance', coin.get('free', coin.get('balance', '0')))
            
            try:
                amount = float(wallet)
                if amount > 0:
                    balance_lines.append(f"• <b>{coin_name}:</b> {amount:.8f}")
                    if coin_name == 'USDT':
                        total_usdt += amount
            except:
                continue
        
        if total_usdt > 0:
            balance_lines.append(f"\n💰 <b>Общий баланс (USDT):</b> {total_usdt:.2f}")
        
        if len(balance_lines) == 1:
            return "💼 Нет монет с ненулевым балансом"
        
        return "\n".join(balance_lines)
        
    except Exception as e:
        logger.error(f"❌ Ошибка форматирования: {e}", exc_info=True)
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

def error_handler(update, context):
    """Обработчик ошибок"""
    logger.error(f"❌ Ошибка: {context.error}")

def main():
    """Запуск бота"""
    logger.info(f"🚀 Запуск бота версии {BOT_VERSION}")
    logger.info(f"👤 Авторизован: {AUTHORIZED_USER}")
    
    # Удаляем webhook перед запуском
    try:
        import requests as req
        webhook_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
        response = req.get(webhook_url)
        logger.info(f"Webhook deleted: {response.json()}")
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
    
    # Запускаем HTTP сервер в отдельном потоке
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    try:
        # Создаем Updater с увеличенным таймаутом
        updater = Updater(token=TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        
        # Регистрируем обработчики
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("balance", balance))
        dispatcher.add_handler(CommandHandler("version", version))
        dispatcher.add_handler(CommandHandler("help", start))
        dispatcher.add_error_handler(error_handler)
        
        # Запускаем бота с clean=True
        updater.start_polling(timeout=30, clean=True)
        logger.info("✅ Бот запущен и готов к работе!")
        
        # Останавливаем бота при сигнале
        updater.idle()
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен вручную")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}", exc_info=True)