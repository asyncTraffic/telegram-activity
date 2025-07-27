from utils.postgres_db import DB
from dotenv import load_dotenv
import os
import base64

load_dotenv()

db_host = os.getenv("DB_HOST"), # БЕРЕТСЯ ИЗ .ENV ФАЙЛА 
db_port = os.getenv("DB_PORT") # БЕРЕТСЯ ИЗ .ENV ФАЙЛА 
db_user = os.getenv("DB_USER") # БЕРЕТСЯ ИЗ .ENV ФАЙЛА 
db_passwd = os.getenv("DB_PASSWORD") # БЕРЕТСЯ ИЗ .ENV ФАЙЛА 
db_name = os.getenv("DB_NAME") # БЕРЕТСЯ ИЗ .ENV ФАЙЛА 
TOKEN = os.getenv("TOKEN") # БЕРЕТСЯ ИЗ .ENV ФАЙЛА 

db = DB(db_host[0], db_port, db_user, db_passwd, db_name)


NAME_PROJECT = '🚀 Auto Dialog'

DOMAIN = "" # ЕСЛИ ХОТИТЕ ЗАПУСТИТЬ НА ХУКАХ, НУЖНО ПРИВЯЗЫВАТЬ ДОМЕН, ЕСЛИ НЕ ЗНАЕТЕ ЧТО ЭТО ТО НЕ ТРОГАЙТЕ

ADMIN = [12356789, 987654321] # АЙДИШНИКИ АДМИНОВ ЧЕРЕЗ ЗАПЯТУЮ
API_ID = 12345 # API ID, можно взять на my.telegram.org
API_HASH = '5g665we469680c770871vh658d64588' #API HASH, можно взять на my.telegram.org

DETAILS = 'автомобили'.split(",") # через запятую перечислите темы для генерации диалога





PROMPT_TEMPLATE = os.getenv(
    "PROMPT_TEMPLATE",
    """
Сгенерируй диалог ровно между {num} уникальными участниками в открытом общем Telegram-чате. Тема: {detail}.
• Используй только роли User 1, User 2, …, User {num} — ни одной дополнительной.
• Реплики участников могут идти в любом порядке (например, User 1, User 3, User 1, User 2, User 2, User 3, User 1), а не обязательно циклом 1→2→3.
• Ответь на русском языке в разговорном стиле со сленгом.
• Строго форматируй по одной строке на сообщение, например:

[User 1] Первое сообщение  
[User 3] Второе сообщение  
[User 1] Третье сообщение  
…  
[User {num}] Последнее сообщение  

• Нужно иногда допускать опечатки.
• Никаких дополнительных описаний или пояснений — только сами строки диалога.
• Нужно делать строго указанное количество участников.
"""
)

BOT_TIMEZONE = "Europe/Moscow"

COOLDOWN_MINUTES = 30

TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))