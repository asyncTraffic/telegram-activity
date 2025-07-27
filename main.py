import asyncio
import logging, sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from data.config import DOMAIN, TOKEN, db
from handlers.admin import accounts, admin_base, chats, dialogs, proxy
from loader import adminRouter, bot, storage, dp, adminChatRouter, account_manager
from loguru import logger
from colorlog import ColoredFormatter
from microservices.trigger_time import scheduler_time_trigger_loop
from microservices.generate_dialog import dialog_generator_service

handler = logging.StreamHandler()
formatter = ColoredFormatter(
    '%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
)
handler.setFormatter(formatter)


def setup_logger():
    logger.remove()
    logger.add(
        sink=sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        sink="logs/app.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        compression="zip"
    )


def main_webhook():
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    dp.include_router(adminRouter)
    dp.include_router(adminChatRouter)
    
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(
        app, path=f"/webhook/main/{TOKEN}/"
    )
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="localhost", port=8080)


async def on_startup_longpool():
    try:
        await db.setup()
    except Exception as e:
        logger.exception(f"Ошибка при подключении к базе данных: {e}")
        sys.exit(1)

    createSettings = await db.add_settings()
    logger.success("Настройки успешно созданы!" if createSettings else "Настройки уже созданы!")

    try:
        await account_manager.start_all_accounts()
    except Exception as e:
        logger.error(e)

    try:        
        asyncio.create_task(scheduler_time_trigger_loop())

    except Exception as e:
        logger.error(e)

    try:
        asyncio.create_task(dialog_generator_service())
    except Exception as e:
        logger.error(e)

    logger.success("Бот успешно запущен!")
    

async def on_shutdown_longpool():
    await db.close()
    logger.success("Бот выключается...")


async def main_longpool():
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    dp.include_router(adminRouter)
    dp.include_router(adminChatRouter)
    dp.startup.register(on_startup_longpool)
    dp.shutdown.register(on_shutdown_longpool)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    if DOMAIN == "":
        asyncio.run(main_longpool())
    else:
        main_webhook()