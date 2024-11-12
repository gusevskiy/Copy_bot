'''
Скрипт получает json содержащий в том числе и id канала также и защищенного от копирования сообщений
можно сделать своего 'userinfobot'

Пример использования: запускаеш и отправляеш сообщение
'''

import os
# from utils.settings import settings
from pyrogram import Client, idle
from dotenv import load_dotenv
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
import asyncio


load_dotenv()

api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')


async def get_channel_id(client: Client, message: Message):
    print(message)


async def start():
    client = Client(name='my_session', api_id=api_id, api_hash=api_hash)

    client.add_handler(MessageHandler(callback=get_channel_id))

    try:
        await client.start()
        await idle()
    except Exception as e:
        await client.stop()


if __name__ == '__main__':
    asyncio.run(start())
