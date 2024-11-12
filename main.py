import os
import asyncio
from typing import AsyncGenerator
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message



load_dotenv()

api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

client = Client(name="my_session")

donor_channel_id = -1001847140757  # test_english
# donor_channel_id = -1966291562  # Kiber Topor


async def massage_transform(msg):
    # msg = vars(msg)
    # msg["caption"] = msg["caption"] + "\n\n" + "Этот текст был изменен при пересылке!!!"
    return msg + "\n\n" + "Этот текст был изменен при пересылке!!!"


def delete_file(file_path: str) -> None:
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Файл удален: {file_path}")
    else:
        print(f"Файл не найден: {file_path}")



@client.on_message(filters.chat(chats=donor_channel_id))
async def clone_content(client, message: Message) -> None:
    recipient_channel_id = -1001923852824  # call_recording

   
    # my_channel_id = 452054525
    async for message in client.get_chat_history(
        chat_id=donor_channel_id,
        limit=1,  # Установите желаемое количество сообщений
        offset_id=-1
    ):
        print(message.caption)
        # описание текста сообщения находится в ключе "caption" длинна текста в сообщении не должна превышать 1024 символов
        transformed_message = await massage_transform(message.caption)

        if message.photo:
            # Загружаем фото
            file_path = await message.download(file_name="image/image.png")
            print(f"Фото сохранено по пути: {file_path}")

            await client.send_photo(chat_id=recipient_channel_id, photo="image/image.png", caption=transformed_message[:1024])

    delete_file("image/image.png")  # Удаляем загруженное фото



if __name__ == "__main__":
    asyncio.run(client.run())


"C:\Program Files\Git\bin\bash.exe"