from aiogram.types import *
from aiogram.types.web_app_info import WebAppInfo


def kbMainUserMenu() -> ReplyKeyboardMarkup:
    key = [
        [
            KeyboardButton(text="💠 Показать меню 💠")
        ],
    ]
    keyReplayUser = ReplyKeyboardMarkup(
        keyboard=key,
        resize_keyboard=True,
        input_field_placeholder="Действуйте!"
    )
    return keyReplayUser