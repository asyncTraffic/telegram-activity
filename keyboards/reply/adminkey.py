from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def kbMainAdmin() -> ReplyKeyboardMarkup:
    key = [
        [
            KeyboardButton(text="👤 Аккаунты"),
            KeyboardButton(text="🗂 Чаты"),
        ],
        [
            KeyboardButton(text="📜 Диалоги"),
            KeyboardButton(text="🌐 Прокси"),
        ]
    ]
    keyReplayAdmin = ReplyKeyboardMarkup(
        keyboard=key,
        resize_keyboard=True,
        input_field_placeholder="Действуйте!"
    )
    return keyReplayAdmin