import os
import logging
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from pybit.unified_trading import HTTP
import asyncio
from datetime import datetime

# Загрузка переменных окружения
load_dotenv()

# Настройка подробного логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Получение переменных из окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER = os.getenv('AUTHORIZED_USER')
BYBIT_API_KEY_DEMO = os.getenv('BYBIT_API_KEY_DEMO')
BYBIT_API_SECRET_DEMO = os.getenv('BYBIT_API_SECRET_DEMO')

# Проверка наличия необходимых переменных
if not all([TELEGRAM_BOT_TOKEN, AUTHORIZED_USER, BYBIT_API_KEY_DEMO, BYBIT_API_SECRET_DEMO]):
    logger.error("❌ Ошибка: Не все переменные окружения установлены!")
    logger.error(f"TELEGRAM_BOT_TOKEN: {'✅' if TELEGRAM_BOT_TOKEN else '❌'}")
    logger.error(f"AUTHORIZED_USER: {'✅' if AUTHORIZED_USER else '❌'}")
    logger.error(f"BYBIT_API_KEY_DEMO: {'✅' if BYBIT_API_KEY_DEMO else '❌'}")
    logger.error(f"BYBIT_API_SECRET_DEMO: {'✅' if BYBIT_API_SECRET_DEMO else '❌'}")
    exit(1)

logger.info("✅ Все переменные окружения загружены успешно")

# Инициализация клиента Bybit (тестовая сеть)
try:
    session = HTTP(
        testnet=True,
        api_key=BYBIT_API_KEY_DEMO,
        api_secret=BYBIT_API_SECRET_DEMO,
    )
    logger.info("✅ Клиент Bybit успешно инициализирован (testnet)")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации клиента Bybit: {e}")
    exit(1)

# Функция проверки авторизации пользователя
async def is_authorized(update: Update) -> bool:
    user_username = update.effective_user.username
    if not user_username:
        logger.warning(f"Пользователь {update.effective_user.id} не имеет username")
        return False
    
    authorized = f"@{user_username}" == AUTHORIZED_USER
    if not authorized:
        logger.warning(f"Неавторизованная попытка доступа от пользователя @{user_username}")
    else:
        logger.info(f"Авторизован пользователь @{user_username}")
    return authorized

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получена команда /start от пользователя {update.effective_user.id}")
    
    if not await is_authorized(update):
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    await update.message.reply_text(
        "🤖 Бот для проверки баланса на Bybit Testnet\n\n"
        "Доступные команды:\n"
        "/balance - показать баланс всех монет\n"
        "/balance USDT - показать баланс конкретной монеты\n"
        "/help - показать это сообщение"
    )
    logger.info("Ответ на /start отправлен")

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получена команда /help от пользователя {update.effective_user.id}")
    
    if not await is_authorized(update):
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    await update.message.reply_text(
        "📖 Доступные команды:\n\n"
        "/balance - показать баланс всех монет с ненулевым балансом\n"
        "/balance USDT - показать баланс указанной монеты\n"
        "/balance ALL - показать баланс всех монет (включая нулевые)\n"
        "/help - показать это сообщение"
    )
    logger.info("Ответ на /help отправлен")

# Функция получения баланса с Bybit
async def get_bybit_balance(coin: str = None):
    logger.info(f"Запрос баланса с Bybit для монеты: {coin if coin else 'все монеты'}")
    
    try:
        # Получение информации об аккаунте
        logger.debug("Отправка запроса wallet/get_balance...")
        response = session.get_wallet_balance(accountType="UNIFIED")
        logger.debug(f"Ответ от Bybit: {response}")
        
        if response.get('retCode') != 0:
            error_msg = response.get('retMsg', 'Неизвестная ошибка')
            logger.error(f"Ошибка API Bybit: {error_msg}")
            return None, f"Ошибка API: {error_msg}"
        
        # Парсинг баланса
        balance_data = response.get('result', {}).get('list', [{}])[0]
        coins = balance_data.get('coin', [])
        
        logger.info(f"Получены данные о {len(coins)} монетах")
        
        if coin:
            # Поиск конкретной монеты
            coin_upper = coin.upper()
            for coin_data in coins:
                if coin_data.get('coin') == coin_upper:
                    wallet_balance = coin_data.get('walletBalance', '0')
                    available_balance = coin_data.get('availableToWithdraw', '0')
                    logger.info(f"Найден баланс для {coin_upper}: wallet={wallet_balance}, available={available_balance}")
                    return {
                        'coin': coin_upper,
                        'wallet_balance': wallet_balance,
                        'available_balance': available_balance
                    }, None
            logger.warning(f"Монета {coin_upper} не найдена в балансе")
            return None, f"Монета {coin_upper} не найдена"
        else:
            # Формирование списка всех монет с ненулевым балансом
            non_zero_coins = []
            for coin_data in coins:
                wallet_balance = float(coin_data.get('walletBalance', 0))
                if wallet_balance > 0:
                    non_zero_coins.append({
                        'coin': coin_data.get('coin'),
                        'wallet_balance': coin_data.get('walletBalance'),
                        'available_balance': coin_data.get('availableToWithdraw')
                    })
            
            logger.info(f"Найдено {len(non_zero_coins)} монет с ненулевым балансом")
            return non_zero_coins, None
            
    except Exception as e:
        logger.error(f"Исключение при получении баланса: {e}", exc_info=True)
        return None, f"Ошибка подключения: {str(e)}"

# Команда /balance
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получена команда /balance от пользователя {update.effective_user.id}")
    
    if not await is_authorized(update):
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    # Отправка сообщения о начале обработки
    status_msg = await update.message.reply_text("🔄 Запрос баланса с Bybit Testnet...")
    
    # Получение аргументов команды
    args = context.args
    coin = args[0] if args else None
    
    try:
        balance_data, error = await get_bybit_balance(coin)
        
        if error:
            await status_msg.edit_text(f"❌ Ошибка: {error}")
            return
        
        if coin:
            # Отображение баланса конкретной монеты
            message = f"💰 Баланс на Bybit Testnet:\n\n"
            message += f"Монета: {balance_data['coin']}\n"
            message += f"Баланс кошелька: {balance_data['wallet_balance']}\n"
            message += f"Доступно для вывода: {balance_data['available_balance']}\n"
            message += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await status_msg.edit_text(message)
            logger.info(f"Баланс для {coin} отправлен пользователю")
            
        else:
            # Отображение всех монет
            if not balance_data:
                await status_msg.edit_text("💰 Баланс на Bybit Testnet:\n\nНет монет с ненулевым балансом")
                logger.info("Нулевой баланс отправлен пользователю")
                return
            
            message = "💰 Баланс на Bybit Testnet:\n\n"
            for coin_data in balance_data:
                message += f"• {coin_data['coin']}:\n"
                message += f"  Баланс: {coin_data['wallet_balance']}\n"
                message += f"  Доступно: {coin_data['available_balance']}\n\n"
            
            message += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await status_msg.edit_text(message)
            logger.info(f"Баланс {len(balance_data)} монет отправлен пользователю")
            
    except Exception as e:
        logger.error(f"Ошибка в команде balance: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Произошла ошибка: {str(e)}")

# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Произошла ошибка: {context.error}", exc_info=True)
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла техническая ошибка. Администратор уведомлен."
            )
    except:
        pass

def main():
    """Запуск бота"""
    logger.info("🚀 Запуск Telegram бота...")
    logger.info(f"Авторизованный пользователь: {AUTHORIZED_USER}")
    logger.info(f"Bybit API Key (первые 10 символов): {BYBIT_API_KEY_DEMO[:10]}...")
    
    try:
        # Создание приложения
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Добавление обработчиков команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("balance", balance))
        
        # Добавление обработчика ошибок
        application.add_error_handler(error_handler)
        
        logger.info("✅ Бот успешно настроен и готов к работе")
        
        # Запуск бота
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)

if __name__ == '__main__':
    main()