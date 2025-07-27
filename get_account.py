from telethon import TelegramClient
from data.config import API_ID, API_HASH


with TelegramClient('anon', API_ID, API_HASH) as client:
    client.loop.run_until_complete(client.send_message('me', 'Hello, myself!'))
