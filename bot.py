import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext
import ccxt

# Загружаем переменные окружения
load_dotenv()

# Версия бота (меняй при каждом обновлении)
BOT_VERSION = "1.0.0"

# Настройка подробного логирования
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

# Проверка наличия необходимых переменных
if not all([TOKEN, AUTHORIZED_USER, BYBIT_API_KEY, BYBIT_API_SECRET]):
    logger.error("❌ Отсутствуют необходимые переменные окружения!")
    raise ValueError("Проверьте .env файл")

# Функция для проверки авторизации
def is_authorized(update: Update) -> bool:
    """Проверка авторизации пользователя"""
    user_id = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
    authorized = user_id == AUTHORIZED_USER or str(update.effective_user.id) == AUTHORIZED_USER.replace('@', '')
    
    if not authorized:
        logger.warning(f"⛔ Неавторизованный доступ от {user_id}")
    
    return authorized

# Функция для подключения к Bybit testnet
def get_bybit_balance():
    """Получение баланса с Bybit testnet"""
    try:
        logger.info("🔄 Подключение к Bybit testnet...")
        
        exchange = ccxt.bybit({
            'apiKey': BYBIT_API_KEY,
            'secret': BYBIT_API_SECRET,
            'options': {
                'defaultType': 'spot',
            },
            'urls': {
                'api': {
                    'public': 'https://api-testnet.bybit.com',
                    'private': 'https://api-testnet.bybit.com',
                }
            },
            'enableRateLimit': True,
        })
        
        # Устанавливаем тестовую сеть
        exchange.set_sandbox_mode(True)
        
        logger.info("✅ Подключение установлено, запрашиваем баланс...")
        
        # Получаем баланс
        balance = exchange.fetch_balance()
        
        logger.info("✅ Баланс успешно получен")
        return balance
        
    except ccxt.NetworkError as e:
        logger.error(f"🌐 Сетевая ошибка Bybit: {e}")
        return None
    except ccxt.AuthenticationError as e:
        logger.error(f"🔑 Ошибка авторизации Bybit: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка Bybit: {e}", exc_info=True)
        return None

# Обработчик команды /start
def start(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    try:
        logger.info(f"📱 Команда /start от пользователя @{update.effective_user.username}")
        
        # Проверка авторизации
        if not is_authorized(update):
            update.message.reply_text("⛔ У вас нет доступа к этому боту!")
            return
        
        welcome_text = f"""
🤖 <b>Бот Bybit Testnet</b>
📦 <b>Версия:</b> {BOT_VERSION}
✅ <b>Статус:</b> Активен
🔗 <b>Биржа:</b> Bybit Testnet
👤 <b>Авторизован:</b> {AUTHORIZED_USER}

🔄 Используйте команду /balance для получения баланса
ℹ️ Команда /version - показать версию бота
        """
        
        update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)
        logger.info(f"✅ Отправлено приветствие для @{update.effective_user.username}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в /start: {e}", exc_info=True)
        update.message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")

# Обработчик команды /balance
def balance(update: Update, context: CallbackContext):
    """Обработчик команды /balance - показывает баланс"""
    try:
        logger.info(f"💰 Команда /balance от пользователя @{update.effective_user.username}")
        
        # Проверка авторизации
        if not is_authorized(update):
            update.message.reply_text("⛔ У вас нет доступа к этому боту!")
            return
        
        update.message.reply_text("🔄 Получение баланса с Bybit Testnet...")
        
        # Получаем баланс
        balance_data = get_bybit_balance()
        
        if balance_data is None:
            update.message.reply_text("❌ Не удалось получить баланс. Проверьте логи.")
            return
        
        # Фильтруем монеты с ненулевым балансом
        non_zero_balances = {}
        total_usdt = 0
        
        for currency, data in balance_data['total'].items():
            if data > 0 and currency != 'USDT':
                non_zero_balances[currency] = data
        
        # Добавляем USDT отдельно
        usdt_balance = balance_data['total'].get('USDT', 0)
        if usdt_balance > 0:
            non_zero_balances['USDT'] = usdt_balance
        
        # Формируем ответ
        if not non_zero_balances:
            balance_text = "💼 <b>Ваш баланс:</b>\n\nПусто (нет монет с ненулевым балансом)"
        else:
            balance_lines = ["💼 <b>Ваш баланс на Bybit Testnet:</b>\n"]
            for currency, amount in non_zero_balances.items():
                balance_lines.append(f"• <b>{currency}:</b> {amount:.8f}")
                if currency == 'USDT':
                    total_usdt += amount
            
            if usdt_balance > 0:
                balance_lines.append(f"\n💰 <b>Общий баланс:</b> {total_usdt:.2f} USDT")
            
            balance_text = "\n".join(balance_lines)
        
        # Добавляем информацию о версии бота
        balance_text += f"\n\n📦 <b>Версия бота:</b> {BOT_VERSION}"
        balance_text += f"\n🕐 <b>Время запроса:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        update.message.reply_text(balance_text, parse_mode=ParseMode.HTML)
        logger.info(f"✅ Баланс отправлен для @{update.effective_user.username}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в /balance: {e}", exc_info=True)
        update.message.reply_text("⚠️ Произошла ошибка при получении баланса. Проверьте логи.")

# Обработчик команды /version
def version(update: Update, context: CallbackContext):
    """Показать версию бота"""
    try:
        logger.info(f"ℹ️ Команда /version от @{update.effective_user.username}")
        
        if not is_authorized(update):
            update.message.reply_text("⛔ У вас нет доступа к этому боту!")
            return
        
        version_text = f"""
📦 <b>Информация о боте:</b>

• <b>Версия:</b> {BOT_VERSION}
• <b>Биржа:</b> Bybit Testnet
• <b>Автор:</b> {AUTHORIZED_USER}
• <b>Статус:</b> ✅ Работает
• <b>Последнее обновление:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Для обновления версии измените BOT_VERSION в коде.
        """
        
        update.message.reply_text(version_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в /version: {e}", exc_info=True)
        update.message.reply_text("⚠️ Ошибка получения версии")

# Обработчик неизвестных команд
def unknown(update: Update, context: CallbackContext):
    """Ответ на неизвестные команды"""
    logger.info(f"❓ Неизвестная команда от @{update.effective_user.username}: {update.message.text}")
    update.message.reply_text("❓ Неизвестная команда. Используйте /start, /balance или /version")

def main():
    """Главная функция запуска бота"""
    logger.info(f"🚀 Запуск бота версии {BOT_VERSION}")
    logger.info(f"🤖 Авторизованный пользователь: {AUTHORIZED_USER}")
    logger.info(f"🔗 Bybit Testnet API ключ: {BYBIT_API_KEY[:10]}...")
    
    # Создаем Updater и передаем ему токен бота
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # Регистрируем обработчики команд
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("version", version))
    dispatcher.add_handler(CommandHandler("help", start))
    
    # Обработчик неизвестных команд
    dispatcher.add_handler(CommandHandler("unknown", unknown))
    
    # Запускаем бота
    updater.start_polling()
    logger.info("✅ Бот успешно запущен и готов к работе!")
    
    # Останавливаем бота при нажатии Ctrl+C
    updater.idle()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)