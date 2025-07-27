import random
import asyncio
from datetime import datetime
import re
import g4f
from g4f.errors import RateLimitError
from loguru import logger
from dotenv import load_dotenv
from data.config import PROMPT_TEMPLATE, DETAILS, TIMEOUT
from loader import db 
load_dotenv()


async def ai_generate_dialog(num_roles: int) -> dict:
    """
    генерирует диалог через g4f беря прокси из базы по кругу
    вернет:
    {
        "name": str,
        "messages": List[{"role":str,"text":str}],
        "num_accounts": int,
        "raw": str
    }
    """
    
    detail = random.choice(DETAILS).strip()
    prompt = PROMPT_TEMPLATE.format(num=num_roles, detail=detail)
    logger.info("Промт для AI:\n" + prompt)

    proxy = await db.get_next_proxy()
    if proxy:
        logger.info(f"Прокси для AI: {proxy}")
    else:
        logger.warning("Лист с прокси пуст, делаем запрос без прокси")

    n = 1

    while True:
        try:
            raw: str = await asyncio.to_thread(lambda: g4f.ChatCompletion.create(
                model=random.choice([
                    g4f.models.gpt_4, g4f.models.gpt_4_1, g4f.models.gpt_4_1_mini, g4f.models.gpt_4_1_nano,
                    g4f.models.qwen_2_5_72b
                       ]),
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                proxy=proxy,  
                timeout=TIMEOUT
            ))
            break
        except RateLimitError as e:
            logger.error(e)

        except Exception as e:
            logger.error(f'Ошибка при генерации диалога: {e}, попытка номер {n}')
            n+=1
            if n >=3:
                raise RuntimeError(f"Не удлаось сгенерировать диалог, причина: {e}")
            

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    messages = []
    pat = re.compile(r"^\[(?P<role>[^\]]+)\]\s*(?P<text>.+)$")
    for line in lines:
        m = pat.match(line)
        if m:
            messages.append({
                "role": m.group("role"),
                "text": m.group("text")
            })

    if not messages:
        messages = [{"role": "AI", "text": raw}]

    filtered = []
    for m in messages:
        mm = re.match(r"User\s+(\d+)$", m["role"])
        if mm and 1 <= int(mm.group(1)) <= num_roles:
            filtered.append(m)

    name = f"ai_{datetime.now():%Y%m%dT%H%M%SZ}_{random.randint(1000,9999)}"
    return {
        "name": name,
        "messages": filtered,
        "num_accounts": num_roles,
        "raw": raw
    }
