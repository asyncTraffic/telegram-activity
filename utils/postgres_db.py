import asyncpg
import pytz
from asyncpg import Pool, Record
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from loguru import logger
import json
from asyncpg import UniqueViolationError


class DictRecord(Record):
    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(value, Record):
            return DictRecord(value)
        return value

    def to_dict(self):
        return self._convert_records_to_dicts(dict(super().items()))

    def _convert_records_to_dicts(self, obj):
        if isinstance(obj, dict):
            return {k: self._convert_records_to_dicts(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_records_to_dicts(item) for item in obj]
        elif isinstance(obj, Record):
            return dict(obj)
        return obj

    def __repr__(self):
        return str(self.to_dict())


class DB:
    def __init__(self, host: str, port: int, user: str, password: str, db_name: str):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._db_name = db_name

    async def close(self):
        await self.db.close()
        logger.warning("Соединение с базой данных завершено!")

    async def setup(self):
        try:
            self.db = await asyncpg.create_pool(
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._db_name,
                record_class=DictRecord,
                init=self._init_database,
            )
            logger.success("Соединение с базой данных успешно установлено!")
        except Exception as e:
            logger.exception(f"Ошибка при подключении к базе данных: {e}")
            raise ValueError("Кажется, при подключении к базе данных возникла ошибка, из-за которой бот не может начать работу :(")

    @staticmethod
    async def _init_database(db: asyncpg.Connection):
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings(
                _id BIGINT PRIMARY KEY,
                api_id BIGINT DEFAULT NULL,
                api_hash TEXT DEFAULT NULL,
                wait_verif_chat_code TEXT DEFAULT NULL,
                update_at_verif_code TIMESTAMP DEFAULT now(),
                wait_append_chat_id BIGINT DEFAULT NULL,
                update_at_chat_id TIMESTAMP DEFAULT now()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks(
                id BIGSERIAL PRIMARY KEY,
                type_ VARCHAR(100) NOT NULL,
                args_input JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT now(),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                CHECK (status IN ('pending', 'completed', 'failed'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS telegram_accounts (
                id SERIAL PRIMARY KEY,
                session_name VARCHAR(255) UNIQUE NOT NULL,
                api_id BIGINT NOT NULL,
                api_hash TEXT NOT NULL,
                account_id BIGINT,
                phone_number VARCHAR(20),
                name TEXT,
                is_active BOOLEAN DEFAULT False,
                proxy JSONB,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id BIGINT PRIMARY KEY,
                title TEXT NOT NULL,
                trigger_invite BOOLEAN DEFAULT False,
                trigger_time BOOLEAN DEFAULT False,
                last_invite_trigger TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS account_chat (
                uniq_id TEXT PRIMARY KEY,
                chat_id BIGINT,
                account_id BIGINT,
                status BOOLEAN DEFAULT False,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS dialogs (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                messages JSONB NOT NULL,
                num_accounts INTEGER NOT NULL DEFAULT 1,
                usage BOOLEAN DEFAULT False
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS proxies (
                    id SERIAL PRIMARY KEY,
                    proxy TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT now()
                )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS proxy_rotation (
                    id INTEGER PRIMARY KEY,
                    last_id INTEGER
                )
        """)
        
        await db.execute("""
            INSERT INTO proxy_rotation (id, last_id)
            VALUES (1, NULL)
            ON CONFLICT (id) DO NOTHING;            

        """)
        await db.execute("SET TIME ZONE 'Europe/Moscow'")



        await db.execute("""
            CREATE TABLE IF NOT EXISTS account_media (
                id INTEGER PRIMARY KEY,
                account_id BIGINT NOT NULL,
                add_id BIGINT NOT NULL,
                media_type TEXT NOT NULL,
                media_path TEXT NOT NULL,
                media_text TEXT,
                is_active BOOLEAN DEFAULT True,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """)

    async def delete_media(self, add_id: int):
        await self.db.execute('DELETE FROM account_media WHERE add_id = $1', add_id)

    async def update_text_media(self, add_id: int, text: str):
        await self.db.execute('UPDATE account_media SET media_text = $1 WHERE add_id = $2', text, add_id)

    async def update_time_account_media(self, add_id: int):
        try:
            await self.db.execute('UPDATE account_media SET updated_at = now() WHERE add_id = $1', add_id)
            return True
        except Exception as e:
            logger.exception(e)
            return False

    async def update_acc_media_active(self, add_id: int, status: bool):
        await self.db.execute('UPDATE account_media SET is_active = $1 WHERE add_id = $2', status, add_id)


    async def get_all_media_by_add_id(self, add_id: int):
        return await self.db.fetch('SELECT * FROM account_media WHERE add_id = $1', add_id)
    
    
    async def get_all_media_account(self, account_id: int):
        return await self.db.fetch('SELECT * FROM account_media WHERE account_id = $1', account_id)


    async def add_account_media(self, account_id: int, add_id: int, media_type: str, media_path: str, media_text: str):
        try:
            await self.db.execute('INSERT INTO account_media (account_id, add_id, media_type, media_path, media_text) VALUES ($1, $2, $3, $4, $5)',
                                account_id, add_id, media_type, media_path, media_text)
            return False
        except Exception as e:
            logger.error(e)
            return False


    async def delete_chat(self, chat_id: int):
        await self.db.execute('DELETE FROM chats WHERE chat_id = $1', chat_id)
        await self.db.execute('DELETE FROM account_chat WHERE chat_id = $1', chat_id)


    async def update_account_proxy_by_session(self, session_name: str, proxy: dict | None) -> bool:
        """
        Обновляет поле proxy для аккаунта с указанным session_name.
        """
        await self.db.execute(
            """
            UPDATE telegram_accounts
               SET proxy = $2, updated_at = now()
            WHERE session_name = $1
            """,
            session_name, proxy
        )
        return True

    async def get_chat_invite_info(self, chat_id: int) -> dict | None:
        """
        Возвращает dict с trigger_invite (bool) и last_invite_trigger (datetime|None).
        """
        row = await self.db.fetchrow(
            "SELECT trigger_invite, last_invite_trigger FROM chats WHERE chat_id = $1",
            chat_id
        )
        return dict(row) if row else None

    async def update_chat_last_invite(self, chat_id: int) -> None:
        """
        Устанавливает last_invite_trigger = now().
        """
        await self.db.execute(
            "UPDATE chats SET last_invite_trigger = now(), updated_at = now() WHERE chat_id = $1",
            chat_id
        )


    async def update_dialog_usage(self, dialog_id: int, status: bool):
        await self.db.execute('UPDATE dialogs SET usage = $1 WHERE id = $2', status, dialog_id)


    async def update_account_proxy(self, account_id: int, proxy: dict | None) -> bool:
        """
        Задает proxy (или сбрасывает на NULL).
        """
        await self.db.execute(
            """
            UPDATE telegram_accounts
               SET proxy = $2
                 , updated_at = now()
             WHERE id = $1
            """,
            account_id, proxy
        )
        return True
    
    async def delete_account(self, account_id: int) -> bool:
        """
        Удаляет аккаунт из БД.
        """
        await self.db.execute(
            "DELETE FROM telegram_accounts WHERE id = $1",
            account_id
        )
        return True

    async def update_account_active(self, account_id: int, is_active: bool) -> bool:
        """
        Переключает флаг is_active.
        """
        await self.db.execute(
            """
            UPDATE telegram_accounts
               SET is_active = $2
                 , updated_at = now()
             WHERE id = $1
            """,
            account_id, is_active
        )
        return True

    async def get_proxy_by_id(self, id_: int):
        return await self.db.fetchrow('SELECT * FROM proxies WHERE id = $1', id_)


    async def get_next_proxy(self) -> Optional[str]:
        """
        Возвращает следующий прокси из таблицы proxies по кругу:
        - Читает last_id из proxy_rotation (первой строки с id=1)
        - Ищет в proxies запись с id > last_id (по возрастанию)
        - Если находит — возвращает её proxy и записывает её id в proxy_rotation.last_id
        - Иначе (дошли до конца списка) — берёт первую запись из proxies
        """
        
        rot = await self.db.fetchrow(
            "SELECT last_id FROM proxy_rotation WHERE id = 1"
        )
        last = rot["last_id"]  

        
        row = await self.db.fetchrow(
            """
            SELECT id, proxy
                FROM proxies
                WHERE ($1::INT IS NULL OR id > $1)
                ORDER BY id
                LIMIT 1
            """,
            last
        )

        
        if not row:
            row = await self.db.fetchrow(
                "SELECT id, proxy FROM proxies ORDER BY id LIMIT 1"
            )
        if not row:
            
            return None

        
        await self.db.execute(
            "UPDATE proxy_rotation SET last_id = $1 WHERE id = 1",
            row["id"]
        )

        return row["proxy"]


    async def get_all_proxies(self) -> list[dict]:
        rows = await self.db.fetch("SELECT id, proxy FROM proxies ORDER BY id")
        
        return [dict(r) for r in rows]

    async def add_proxy(self, proxy: str) -> bool:
        """
        Добавить новый прокси. Возвращает False, если уже есть.
        """
        try:
            await self.db.execute(
                "INSERT INTO proxies (proxy) VALUES ($1)",
                proxy
            )
            return True
        except UniqueViolationError:
            return False

    async def remove_proxy(self, proxy: str) -> bool:
        """
        Удалить прокси. Возвращает True, если было что-то удалить.
        """
        res = await self.db.execute(
            "DELETE FROM proxies WHERE proxy = $1",
            proxy
        )
        
        return res.split()[-1] != '0'





    async def get_time_trigger_chats(self) -> list[dict]:
        """
        Возвращает список chat_id всех чатов, у которых trigger_time = TRUE.
        """
        rows = await self.db.fetch(
            """
            SELECT chat_id
            FROM chats
            WHERE trigger_time = TRUE
            """
        )
        
        return [dict(r) for r in rows]



    async def remove_accounts_from_chat(self, chat_id: int, account_ids: List[int]) -> None:
        """
        Удаляет из чата только указанные аккаунты.
        """
        await self.db.execute(
            """
            DELETE FROM account_chat
            WHERE chat_id = $1
            AND account_id = ANY($2::BIGINT[])
            """,
            chat_id, account_ids
        )

    async def clear_accounts_from_chat(self, chat_id: int) -> None:
        """
        Удаляет из чата все аккаунты.
        """
        await self.db.execute(
            """
            DELETE FROM account_chat
            WHERE chat_id = $1
            """,
            chat_id
        )




    async def get_accounts_not_in_chat(self, chat_id: int) -> List[dict]:
        rows = await self.db.fetch(
            """
            SELECT *
            FROM telegram_accounts ta
            WHERE ta.is_active
              AND ta.account_id NOT IN (
                SELECT account_id
                FROM account_chat
                WHERE chat_id = $1
              )
            ORDER BY ta.id
            """,
            chat_id
        )
        return [dict(r) for r in rows]

    async def get_accounts_in_chat(self, chat_id: int) -> List[dict]:
        rows = await self.db.fetch(
            """
            SELECT ta.*
            FROM telegram_accounts ta
            JOIN account_chat ac ON ta.account_id = ac.account_id
            WHERE ac.chat_id = $1
            ORDER BY ac.created_at
            """,
            chat_id
        )
        return [dict(r) for r in rows]
    

    async def add_accounts_to_chat(self, uniq_id: str, chat_id: int, account_id: int) -> bool:
        try:
            
            await self.db.execute(
                """
                INSERT INTO account_chat (uniq_id, chat_id, account_id)
                VALUES ($1, $2, $3)
                """,
                uniq_id, chat_id, account_id
            )
            return True
        except Exception as e:
            logger.exception(e)
            return False

    async def delete_account_from_chat(self, chat_id: int, account_id: Optional[int] = None) -> bool:
        """
        Если account_id указан — удаляем конкретно его, иначе — все аккаунты из чата.
        """
        if account_id:
            await self.db.execute(
                "DELETE FROM account_chat WHERE chat_id = $1 AND account_id = $2",
                chat_id, account_id
            )
        else:
            await self.db.execute(
                "DELETE FROM account_chat WHERE chat_id = $1",
                chat_id
            )
        return True

    

    async def update_chat_trigger_invite(self, chat_id: int, enable: bool) -> None:
        await self.db.execute(
            "UPDATE chats SET trigger_invite = $2, updated_at = now() WHERE chat_id = $1",
            chat_id, enable
        )

    async def update_chat_trigger_time(self, chat_id: int, enable: bool) -> None:
        await self.db.execute(
            "UPDATE chats SET trigger_time = $2, updated_at = now() WHERE chat_id = $1",
            chat_id, enable
        )


    async def get_all_telegram_accounts(self) -> List[dict]:
        """
        Возвращает список всех записей telegram_accounts.
        """
        rows = await self.db.fetch("""
            SELECT
                id,
                session_name,
                api_id,
                api_hash,
                account_id,
                phone_number,
                name,
                is_active,
                proxy
            FROM telegram_accounts
            ORDER BY id
        """)
        accounts: List[dict] = []
        for row in rows:
            rec = dict(row)
            
            if isinstance(rec['proxy'], str):
                try:
                    rec['proxy'] = json.loads(rec['proxy'])
                except json.JSONDecodeError:
                    rec['proxy'] = None
            
            accounts.append(rec)
        return accounts

    async def get_telegram_account_by_id(self, account_id: int) -> Optional[dict]:
        """
        Возвращает одну запись telegram_accounts по её ID.
        """
        row = await self.db.fetchrow("""
            SELECT
                id,
                session_name,
                api_id,
                api_hash,
                account_id,
                phone_number,
                name,
                is_active,
                proxy
            FROM telegram_accounts
            WHERE id = $1
        """, account_id)
        if not row:
            return None

        rec = dict(row)
        if isinstance(rec['proxy'], str):
            try:
                rec['proxy'] = json.loads(rec['proxy'])
            except json.JSONDecodeError:
                rec['proxy'] = None
        return rec
    
    async def get_telegram_account_by_account_id(self, account_id: int) -> Optional[dict]:
        """
        Возвращает одну запись telegram_accounts по её ID.
        """
        row = await self.db.fetchrow("""
            SELECT
                id,
                session_name,
                api_id,
                api_hash,
                account_id,
                phone_number,
                name,
                is_active,
                proxy
            FROM telegram_accounts
            WHERE account_id = $1
        """, account_id)
        if not row:
            return None

        rec = dict(row)
        if isinstance(rec['proxy'], str):
            try:
                rec['proxy'] = json.loads(rec['proxy'])
            except json.JSONDecodeError:
                rec['proxy'] = None
        return rec

    async def add_telegram_account(
        self,
        session_name: str,
        api_id: int,
        api_hash: str,
        account_id: Optional[int],
        phone_number: Optional[str],
        name: Optional[str],
        is_active: bool = False,
        proxy: Optional[dict] = None
    ) -> int:
        """
        Добавляет новую запись в telegram_accounts и возвращает её ID.
        proxy передаётся как dict или None.
        """
        proxy_json = json.dumps(proxy) if proxy is not None else None
        result = await self.db.fetchrow("""
            INSERT INTO telegram_accounts (
                session_name,
                api_id,
                api_hash,
                account_id,
                phone_number,
                name,
                is_active,
                proxy
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            RETURNING id
        """,
            session_name,
            api_id,
            api_hash,
            account_id,
            phone_number,
            name,
            is_active,
            proxy_json
        )
        return result['id']

    async def add_dialog(
        self,
        name: str,
        messages: List[dict],
        num_accounts: int
    ) -> int:
        
        messages_json = json.dumps(messages, ensure_ascii=False)
        result = await self.db.fetchrow(
            """
            INSERT INTO dialogs (name, messages, num_accounts)
            VALUES ($1, $2::jsonb, $3)
            RETURNING id
            """,
            name, messages_json, num_accounts
        )
        return result["id"]


    async def get_all_dialogs(self) -> List[dict]:
        
        return await self.db.fetch(
            """
            SELECT
            id,
            name,
            messages,
            num_accounts
            FROM dialogs
            WHERE usage = FALSE
            ORDER BY id;
            """
        )


    async def get_dialog_by_id(self, dialog_id: int) -> Optional[dict]:
        row = await self.db.fetchrow(
            """
            SELECT id, name, messages, num_accounts
            FROM dialogs
            WHERE id = $1
            """,
            dialog_id
        )
        if not row:
            return None

        
        rec = dict(row)

        
        if isinstance(rec['messages'], str):
            try:
                rec['messages'] = json.loads(rec['messages'])
            except json.JSONDecodeError:
                rec['messages'] = []

        
        return rec
    
    

    async def delete_account_from_chat(self, chat_id: int, account_id: int):
        await self.db.execute('DELETE FROM chat_id = $1 AND account_id = $2', chat_id, account_id)

    async def get_accounts_by_chat_id(self, chat_id: int):
        return await self.db.fetch('SELECT * FROM account_chat WHERE chat_id = $1', chat_id)


    async def get_all_account_chat_by_chat_id(self, chat_id: int):
        return await self.db.fetch('SELECT * FROM account_chat WHERE chat_id = $1', chat_id)


    async def get_chat_by_id(self, chat_id: int):
        return await self.db.fetchrow('SELECT * FROM chats WHERE chat_id = $1', chat_id)


    async def add_chat(self, chat_id: int, title: str):
        try:
            
            await self.db.fetchval(
                """
                INSERT INTO chats (chat_id, title)
                VALUES ($1, $2)
                """,
                chat_id, title
            )
            logger.info(f"Чат {title} добавлен")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении чата {title}: {e}")
            return None

    async def get_all_chats(self):
        return await self.db.fetch('SELECT * FROM chats')

    async def add_account(self, session_name: str, phone_number: str = None, proxy: Optional[Dict] = None) -> Optional[int]:
        
        try:
            
            account_id = await self.db.fetchval(
                """
                INSERT INTO telegram_accounts (session_name, phone_number, is_active, proxy)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                session_name, phone_number, True, proxy
            )
            logger.info(f"Аккаунт {session_name} добавлен с ID: {account_id}")
            return account_id
        except Exception as e:
            logger.error(f"Ошибка при добавлении аккаунта {session_name}: {e}")
            return None

    async def get_account(self, session_name: str) -> Optional[DictRecord]:
        
        try:
            account = await self.db.fetchrow(
                "SELECT * FROM telegram_accounts WHERE session_name = $1",
                session_name
            )
            return account
        except Exception as e:
            logger.error(f"Ошибка при получении аккаунта {session_name}: {e}")
            return None
        
    async def get_account_by_id(self, account_id: int) -> Optional[DictRecord]:
        
        try:
            account = await self.db.fetchrow(
                "SELECT * FROM telegram_accounts WHERE account_id = $1",
                account_id
            )
            return account
        except Exception as e:
            logger.error(f"Ошибка при получении аккаунта {account_id}: {e}")
            return None
        
    async def get_account_by_uniq_id(self, id: int) -> Optional[DictRecord]:
        
        try:
            account = await self.db.fetchrow(
                "SELECT * FROM telegram_accounts WHERE id = $1",
                id
            )
            return account
        except Exception as e:
            logger.error(f"Ошибка при получении аккаунта {id}: {e}")
            return None

    async def get_all_accounts(self) -> List[DictRecord]:
        
        try:
            accounts = await self.db.fetch("SELECT * FROM telegram_accounts")
            return accounts
        except Exception as e:
            logger.error(f"Ошибка при получении всех аккаунтов: {e}")
            return []

    async def get_active_accounts(self) -> List[DictRecord]:
        
        try:
            accounts = await self.db.fetch(
                "SELECT * FROM telegram_accounts WHERE is_active = TRUE"
            )
            return accounts
        except Exception as e:
            logger.error(f"Ошибка при получении активных аккаунтов: {e}")
            return []

    async def update_account(self, session_name: str, phone_number: Optional[str] = None, is_active: Optional[bool] = None, proxy: Optional[Dict] = None) -> bool:
        
        try:
            updates = []
            params = [session_name]
            param_index = 2

            if phone_number is not None:
                updates.append(f"phone_number = ${param_index}")
                params.append(phone_number)
                param_index += 1
            if is_active is not None:
                updates.append(f"is_active = ${param_index}")
                params.append(is_active)
                param_index += 1
            if proxy is not None:
                updates.append(f"proxy = ${param_index}")
                params.append(proxy)
                param_index += 1

            updates.append(f"updated_at = now()")
            if updates:
                query = f"UPDATE telegram_accounts SET {', '.join(updates)} WHERE session_name = $1"
                await self.db.execute(query, *params)
                logger.info(f"Аккаунт {session_name} обновлен")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при обновлении аккаунта {session_name}: {e}")
            return False

    async def delete_account(self, session_name: str) -> bool:
        
        try:
            result = await self.db.execute(
                "DELETE FROM telegram_accounts WHERE session_name = $1",
                session_name
            )
            if result == "DELETE 1":
                logger.info(f"Аккаунт {session_name} удален")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при удалении аккаунта {session_name}: {e}")
            return False

    async def get_account(self, session_name: str) -> Optional[DictRecord]:
        
        try:
            account = await self.db.fetchrow(
                "SELECT * FROM telegram_accounts WHERE session_name = $1",
                session_name
            )
            return account
        except Exception as e:
            logger.error(f"Ошибка при получении аккаунта {session_name}: {e}")
            return None


    async def get_pending_tasks(self):
        query = "SELECT id, type_, args_input, created_at FROM tasks WHERE status = 'pending'"
        return await self.db.fetch(query)


    async def update_status_task(self, task_id: int, status: str):
        query = "UPDATE tasks SET status = $1 WHERE id = $2"
        await self.db.execute(query, status, task_id)


    async def create_task(self, type_: str, args_input: json):
        query = """
            INSERT INTO tasks (type_, args_input, status)
            VALUES ($1, $2, 'pending')
            RETURNING id
        """
        await self.db.fetchval(query, type_, args_input)


    async def get_settings(self) -> dict:
        response = await self.db.fetchrow("SELECT * FROM settings WHERE _id = 1")
        return response.to_dict()


    async def add_settings(self):
        try:
            await self.db.execute("INSERT INTO settings (_id) VALUES ($1)", 1)
            return True
        except Exception as e:
            logger.warning(e)
            return False


    async def get_admins_role(self) -> List[dict]:
        response = await self.db.fetch("SELECT * FROM users WHERE role = 'admin'")
        return response

    
    async def get_user_info(self, user_id: int) -> dict:
        response = await self.db.fetchrow("SELECT * FROM users WHERE _id = $1", user_id)
        return response.to_dict() if response else {}


    async def get_user_info_dict(self, user_id: int) -> dict:
        response = await self.db.fetchrow("SELECT * FROM users WHERE _id = $1", user_id)
        return response


    async def get_all_admin_db(self):
        return await self.db.fetch("SELECT * FROM users WHERE role = 'admin' OR role = 'owner'")


    async def add_user(self, user_id: int, username: str, full_name: str) -> dict:
        if not await self.user_existence(user_id):
            response = await self.db.fetchrow(
                "INSERT INTO users(_id, username, full_name) VALUES($1, $2, $3) RETURNING *",
                user_id, username, full_name
            )
            return response.to_dict()
        await self.update_user_activity(user_id)
        return await self.get_user_info(user_id)


    async def update_user_activity(self, user_id: int):
        if await self.user_existence(user_id):
            await self.db.execute("UPDATE users SET updated_at = $1 WHERE _id = $2", datetime.now(), user_id)


    async def user_existence(self, user_id: int) -> bool:
        return await self.db.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE _id=$1)", user_id)


    async def get_all_users(self) -> List[dict]:
        return await self.db.fetch("SELECT * FROM users")   