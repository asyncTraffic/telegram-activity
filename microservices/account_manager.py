import asyncio
import json
import re
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, List
import random
import socks
from aiogram import Bot
from loguru import logger
from telethon import TelegramClient
from telethon.errors import ChannelInvalidError, ChannelPrivateError
from telethon.sessions import SQLiteSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.types import SendMessageTypingAction
from data.config import DB, ADMIN

class AccountManager:
    def __init__(self, bot: Bot, account_db: DB, api_id: int, api_hash: str, session_dir: str = "sessions"):
        self.bot = bot
        self.account_db = account_db
        self.api_id = api_id
        self.api_hash = api_hash
        self.clients: Dict[str, TelegramClient] = {}
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)

    def _build_proxy(self, proxy_data: Dict) -> Optional[tuple]:
        if not proxy_data:
            return None
        try:
            proxy_types = {
                "socks5": socks.SOCKS5,
                "socks4": socks.SOCKS4,
                "http": socks.HTTP,
                "https": socks.HTTP,
            }
            ptype = proxy_data["type"]
            if ptype not in proxy_types:
                raise ValueError(f"Unsupported proxy type: {ptype}")
            tup = (proxy_types[ptype], proxy_data["host"], proxy_data["port"], True)
            if proxy_data.get("username") and proxy_data.get("password"):
                tup += (proxy_data["username"], proxy_data["password"])
            logger.debug(tup)
            return tup
        except Exception as e:
            logger.error(f"Proxy build error: {e}")
            return None

    async def disable_account(self, session_name: str, reason: str) -> None:
        client = self.clients.pop(session_name, None)
        if client:
            try:
                await client.disconnect()
                logger.info(f"{session_name}: клиент отключён в disable_account")
            except Exception as e:
                logger.warning(f"{session_name}: ошибка отключения в disable_account: {e}")

        try:
            await self.account_db.update_account(session_name=session_name, is_active=False)
        except Exception as e:
            logger.error(f"{session_name}: не удалось пометить is_active=False в БД: {e}")

        text = f"⚠️ Аккаунт `{session_name}` отключён автоматически:\n{reason}"
        for admin_id in ADMIN:
            try:
                await self.bot.send_message(admin_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

    async def join_chat_by_link(self, session_name: str, invite_link: str) -> bool:
        logger.debug(invite_link)
        client = self.clients.get(session_name)
        if not client:
            logger.error(f"{session_name}: Telethon-клиент не найден")
            return False

        link = invite_link.strip().rstrip('/')
        tail = link.rsplit('/', 1)[-1]
        logger.debug(tail)
        logger.debug(link)

        is_private = '+' in tail or 'joinchat' in link
        logger.debug(is_private)
        try:
            if is_private:
                hash_part = tail.replace('+', '')
                await client(ImportChatInviteRequest(hash_part))
                logger.info(f"{session_name} вошёл по приватной ссылке")
            else:
                await client(JoinChannelRequest(tail))
                logger.info(f"{session_name} вошёл по публичному username: {tail}")
            return True
        except Exception as e:
            logger.error(f"{session_name}: не удалось присоединиться по ссылке {invite_link} — {e}")
            return False

    async def add_account(self, session_file: str, proxy: Optional[Dict] = None) -> Optional[str]:
        src_path = Path(session_file)
        if not src_path.exists() or src_path.suffix != ".session":
            logger.error(f"Неверный путь или расширение: {session_file}")
            return None

        session_name = str(uuid.uuid4())
        dest_path = self.session_dir / f"{session_name}.session"

        try:
            dest_path.write_bytes(src_path.read_bytes())
        except Exception as e:
            logger.error(f"Ошибка копирования сессии: {e}")
            return None

        proxy_tup = self._build_proxy(proxy) if proxy else None
        client = TelegramClient(str(dest_path), self.api_id, self.api_hash, proxy=proxy_tup)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError("Сессия не авторизована")
            me = await client.get_me()
            account_id = me.id
            phone_number = me.phone or None
            name = " ".join(filter(None, (me.first_name, me.last_name))) or None

            proxy_json = json.dumps(proxy, ensure_ascii=False) if proxy else None
            new_id = await self.account_db.add_telegram_account(
                session_name=session_name,
                api_id=self.api_id,
                api_hash=self.api_hash,
                account_id=account_id,
                phone_number=phone_number,
                name=name,
                is_active=True,
                proxy=proxy_json
            )
            self.clients[session_name] = client
            logger.info(f"Аккаунт {session_name} (ID в БД {new_id}) добавлен и активирован")
            return session_name

        except Exception as e:
            logger.error(f"Не удалось добавить аккаунт: {e}")
            await client.disconnect()
            dest_path.unlink(missing_ok=True)
            return None

    async def update_account_proxy(self, session_name: str, proxy: dict | None) -> bool:
        updated = await self.account_db.update_account_proxy_by_session(session_name, proxy)
        if not updated:
            logger.error(f"{session_name}: не удалось обновить proxy в БД")
            return False

        old_client = self.clients.get(session_name)
        if old_client:
            try:
                await old_client.disconnect()
                logger.info(f"{session_name}: старый клиент отключён")
            except Exception as e:
                logger.warning(f"{session_name}: ошибка при отключении старого клиента: {e}")

        session_path = self.session_dir / f"{session_name}.session"
        proxy_tuple = self._build_proxy(proxy) if proxy else None
        new_client = TelegramClient(str(session_path), self.api_id, self.api_hash, proxy=proxy_tuple)
        try:
            await new_client.connect()
            if not await new_client.is_user_authorized():
                raise RuntimeError("сессия не авторизована после переподключения")
            self.clients[session_name] = new_client
            logger.info(f"{session_name}: клиент перезапущен с proxy={proxy}")
            return True
        except Exception as e:
            logger.error(f"{session_name}: не удалось подключить новый клиент: {e}")
            self.clients.pop(session_name, None)
            return False

    async def start_all_accounts(self):
        rows = await self.account_db.get_all_telegram_accounts()
        active = [r for r in rows if r.get("is_active")]
        for rec in active:
            name = rec["session_name"]
            path = self.session_dir / f"{name}.session"
            if not path.exists():
                await self.disable_account(name, "session-файл не найден")
                continue

            proxy_tup = self._build_proxy(rec.get("proxy") or {})
            client = TelegramClient(str(path), self.api_id, self.api_hash, proxy=proxy_tup)
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    raise RuntimeError("not authorized")
                self.clients[name] = client
                logger.info(f"Аккаунт {name} запущен")
            except Exception as e:
                logger.error(f"Ошибка при старте {name}: {e}")
                try:
                    await client.disconnect()
                except Exception:
                    pass
                await self.disable_account(name, str(e))

    async def stop_all(self):
        for name, client in list(self.clients.items()):
            try:
                await client.disconnect()
            except Exception:
                pass
        self.clients.clear()

    async def send_message(self, session_name: str, chat_id: str, text: str) -> bool:
        client = self.clients.get(session_name)
        if not client:
            logger.error(f"{session_name}: клиент не найден")
            return False
        try:
            await client.send_message(chat_id, text)
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            return False

    async def parse_dialog(self, dialog_text: str, num_roles: int) -> List[Dict[str, str]]:
        pattern = r"\[([^\]]+)\]\s*([^\[]+)"
        matches = re.findall(pattern, dialog_text, re.MULTILINE)
        if not matches:
            raise ValueError("Диалог не распознан")
        roles = {r for r, _ in matches}
        if len(roles) != num_roles:
            raise ValueError(f"Ожидалось {num_roles} ролей, найдено {len(roles)}")
        if len(self.clients) < num_roles:
            raise ValueError("Мало запущенных аккаунтов")
        return [{"role": r, "message": m.strip()} for r, m in matches]

    async def play_dialog(self, chat_id: str, dialog_text: str, num_roles: int):
        if not self.clients:
            await self.start_all_accounts()
        dialog = await self.parse_dialog(dialog_text, num_roles)

        roles = list({d["role"] for d in dialog})
        sessions = list(self.clients.keys())
        mapping = {roles[i]: sessions[i] for i in range(len(roles))}

        first = next(iter(self.clients.values()))
        chat = await first.get_input_entity(chat_id)

        for d in dialog:
            sess = mapping[d["role"]]
            client = self.clients[sess]
            conn = client.is_connected()

            dur = min(max(len(d["message"]) / 4 * random.uniform(0.8, 1.2), 1), 5)
            try:
                await client(SetTypingRequest(peer=chat, action=SendMessageTypingAction()))
            except ChannelInvalidError:
                logger.warning(f"не удалось включить typing для {chat_id}")
            except Exception as e:
                logger.exception(e)

            await asyncio.sleep(dur)
            await self.send_message(sess, chat_id, d["message"])
            await asyncio.sleep(random.uniform(5, 15))

    async def stop_account(self, session_name: str) -> bool:
        client = self.clients.get(session_name)
        if not client:
            logger.warning(f"stop_account: клиент {session_name} не найден")
            return False

        try:
            await client.disconnect()
            logger.info(f"stop_account: клиент {session_name} отключён")
        except Exception as e:
            logger.error(f"stop_account: ошибка при отключении {session_name}: {e}")
        finally:
            self.clients.pop(session_name, None)
            try:
                await self.account_db.update_account(session_name=session_name, is_active=False)
            except Exception as e:
                logger.error(f"stop_account: не удалось обновить is_active в БД для {session_name}: {e}")
        return True

    async def update_account_name(self, session_name: str, new_name: str) -> bool:
        client: TelegramClient = self.clients.get(session_name)
        if not client:
            logger.error(f"{session_name}: клиент не найден для смены имени")
            return False
        try:
            parts = new_name.strip().split(None, 1)
            first = parts[0]
            last = parts[1] if len(parts) > 1 else ""
            await client(UpdateProfileRequest(first_name=first, last_name=last))
            logger.info(f"{session_name}: имя обновлено на '{new_name}'")
            return True
        except Exception as e:
            logger.error(f"{session_name}: не удалось сменить имя: {e}")
            return False

    async def update_account_about(self, session_name: str, about: str) -> bool:
        client: TelegramClient = self.clients.get(session_name)
        if not client:
            logger.error(f"{session_name}: клиент не найден для смены описания")
            return False
        try:
            await client(UpdateProfileRequest(about=about))
            logger.info(f"{session_name}: описание обновлено")
            return True
        except Exception as e:
            logger.error(f"{session_name}: не удалось сменить описание: {e}")
            return False

    async def update_account_photo(self, session_name: str, photo_bytes: bytes) -> bool:
        client: TelegramClient = self.clients.get(session_name)
        if not client:
            logger.error(f"{session_name}: клиент не найден для смены фото")
            return False
        try:
            bio = BytesIO(photo_bytes)
            bio.name = "profile.jpg"
            file = await client.upload_file(bio)
            await client(UploadProfilePhotoRequest(file=file))
            logger.info(f"{session_name}: фото профиля обновлено")
            return True
        except Exception as e:
            logger.error(f"{session_name}: не удалось сменить фото: {e}")
            return False