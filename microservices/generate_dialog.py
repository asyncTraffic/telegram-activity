import asyncio
import random
from loguru import logger
from loader import db
from utils.misc_func.generator_dialogs import ai_generate_dialog

async def dialog_generator_service(interval: int = 60) -> None:
    logger.info(f"Генератор диалогов запущен. (interval={interval}s)")
    while True:
        try:
            num_roles = random.randint(2, 5)
            logger.info(f"Генерируем диалоги для {num_roles} ролей")
            ai_res = await ai_generate_dialog(num_roles)

            dlg_id = await db.add_dialog(
                name=ai_res["name"],
                messages=ai_res["messages"],
                num_accounts=ai_res["num_accounts"]
            )
            logger.success(f"Диалог сохранён под ID={dlg_id}, roles={ai_res['num_accounts']}")

        except Exception as e:
            logger.error(f"Ошибка при генерации диалога: {e}")

        await asyncio.sleep(interval)