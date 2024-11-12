"""
https://www.youtube.com/watch?v=lcS94kcy7lc
скрипт пересылает сообщения из чата donor_channel_id в my_channel_id
кол-во устанавливается в limit.

"""
import os
import asyncio
from typing import AsyncGenerator
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
import json
from pprint import pprint



load_dotenv()

api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

client = Client(name="my_session", api_id=api_id, api_hash=api_hash)

donor_channel_id = -1001847140757  # test_english
# donor_channel_id = -1966291562  # Kiber Topor


async def massage_transform(msg: dict) -> dict:
    msg = vars(msg)
    msg["caption"] = msg["caption"] + "\n\n" + "Этот текст был изменен при пересылке!!!"
    return msg




@client.on_message(filters.chat(chats=donor_channel_id))
async def clone_content(client, message: Message):
    print(f"Получено сообщение: {message.author_signature}")
    
    recipient_channel_id = -1001923852824  # call_recording
    my_channel_id = 452054525
    async for message in client.get_chat_history(
        chat_id=donor_channel_id,
        limit=1,  # Установите желаемое количество сообщений
        offset_id=-1
    ):
        print(f"------------------------------------------------")
        print(f"------------------------------------------------")
        print(f"Получено от автора: {message.author_signature}")
        
        # text=(f"{message.author_signature}\n" 
        #       f"{message.text}")
        print(message)

# пересылает сообщение целиком
    #     await client.forward_messages(
    #     chat_id=recipient_channel_id,          # ID канала/чата, куда переслать сообщение
    #     from_chat_id=donor_channel_id,   # ID канала/чата, откуда переслать сообщение
    #     message_ids=message.id   # ID пересылаемого сообщения
    # )

# пересылает только текст сообщения
        # await client.send_message(
        #     chat_id= recipient_channel_id, text=text)

# Получаем текст сообщения

    # transformed_message = await massage_transform(message)

    # # Отправляем новое сообщение с измененным текстом
    # await client.send_message(recipient_channel_id, transformed_message)


    # with open('msg2.json', 'w', encoding="utf8") as f:
	#     json.dump(vars(message), f, ensure_ascii=False, indent=4, default=str)

    # transformed_message = vars(message)
    # pprint(transformed_message)


if __name__ == "__main__":
    asyncio.run(client.run())


"C:\Program Files\Git\bin\bash.exe"