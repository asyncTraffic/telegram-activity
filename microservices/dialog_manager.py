import asyncio
import re
import random
from typing import List, Dict
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction
from loguru import logger
from account_manager import AccountManager

class TelegramDialogPlayer:
    def __init__(self, account_manager: AccountManager, chat_id: str):
        self.account_manager = account_manager
        self.chat_id = chat_id

    def parse_dialog(self, dialog_text: str, num_roles: int) -> List[Dict[str, str]]:
        pattern = r'\[([^\]]+)\]\s*([^\[]+)'
        matches = re.findall(pattern, dialog_text, re.MULTILINE)
        roles = set(match[0] for match in matches)

        if len(roles) != num_roles:
            raise ValueError(f"Ожидалось {num_roles} ролей, найдено {len(roles)}")
        if len(self.account_manager.clients) < num_roles:
            raise ValueError(f"Недостаточно аккаунтов ({len(self.account_manager.clients)}) для {num_roles} ролей")

        return [{'role': match[0], 'message': match[1].strip()} for match in matches]

    async def play_dialog(self, dialog_text: str, num_roles: int):
        await self.account_manager.start_all_accounts()
        if not self.account_manager.clients:
            raise ValueError("Нет активных аккаунтов для разыгрывания диалога")

        dialog = self.parse_dialog(dialog_text, num_roles)
        roles = list(set(msg['role'] for msg in dialog))
        session_names = list(self.account_manager.clients.keys())
        role_to_session = {role: session_names[i] for i, role in enumerate(roles)}

        first_client = list(self.account_manager.clients.values())[0]
        chat = await first_client.get_entity(self.chat_id)

        for msg in dialog:
            session_name = role_to_session[msg['role']]
            client = self.account_manager.clients[session_name]
            message = msg['message']

            chars_per_second = 4
            message_length = len(message)
            base_duration = message_length / chars_per_second
            random_factor = random.uniform(0.8, 1.2)
            typing_duration = base_duration * random_factor
            typing_duration = max(1.0, min(typing_duration, 5.0))

            try:
                await client(SetTypingRequest(peer=chat, action=SendMessageTypingAction()))
                await asyncio.sleep(typing_duration)
            except Exception as e:
                logger.error(f"Ошибка при активации typing для {session_name}: {e}")

            success = await self.account_manager.send_message(session_name, self.chat_id, message)
            if not success:
                logger.warning(f"Не удалось отправить сообщение от {session_name}")

            await asyncio.sleep(random.uniform(2, 5))