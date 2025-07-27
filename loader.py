from data.config import TOKEN, db
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from typing import Any, Dict, Union
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Bot, Dispatcher, F, Router
from services.api_session import *
from utils.misc_func.filters import *

import asyncio, pytz

from middlewares.middleware_users import *
from middlewares.album import *
from utils.postgres_db import DB
from microservices.account_manager import AccountManager
from data.config import API_HASH, API_ID

adminRouter = Router()
adminRouter.callback_query.filter(IsPrivate())
adminRouter.message.filter(IsPrivate())
adminRouter.message.filter(IsAdmin())
adminRouter.callback_query.filter(IsAdmin())
adminRouter.message.middleware(MediaGroupMiddleware())
adminRouter.message.middleware(ExistsUserMiddleware())

adminChatRouter = Router()
adminChatRouter.callback_query.filter(IsChat())
adminChatRouter.message.filter(IsChat())
adminChatRouter.message.filter(IsAdmin())
adminChatRouter.callback_query.filter(IsAdmin())

session = AiohttpSession()
bot_settings = {"session": session, "parse_mode": "HTML"}

bot = Bot(token=TOKEN, **bot_settings)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
account_manager = AccountManager(bot, db, API_ID, API_HASH)