from aiogram.filters import Command, CommandObject
from keyboards.reply.adminkey import kbMainAdmin
from loader import *
from utils.misc_func.bot_models import FSM
from loguru import logger

@adminRouter.message(Command("admin"))
async def admin_main_page(msg: Message, state: FSM):
    await state.clear()
    text = (
        "Добро пожаловать в <b>панель администратора!</b>\n\n"
        "<i>Воспользуйтесь кнопками ниже для управления ботом 👇</i>"
    )
    await msg.answer(text, reply_markup=kbMainAdmin())