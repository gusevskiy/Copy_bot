import asyncio
import logging
import traceback
import os
from typing import List
from pyrogram import Client
from pyrogram.filters import chat
from pyrogram.enums import MessageMediaType
from pyrogram.types import Message
from dotenv import load_dotenv, find_dotenv

from aiogram import Bot, Dispatcher
from aiogram.types import (
    BufferedInputFile,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InputMediaAudio,
)

# Настройка логирования на верхнем уровне
logging.basicConfig(
    format="[%(levelname) 5s] [%(asctime)s] [%(name)s.%(funcName)s:%(lineno)d]: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


load_dotenv(find_dotenv("/home/gusevskiy/develop/copy_bots/sessions/.env"))

# Константы
donor_chats = list(map(int, os.getenv("DONOR").split(",")))
recipient_chats = list(map(int, os.getenv("RECIPIENT").split(",")))
file_session = str(os.getenv("SESSION"))
BOT_TOKEN = os.getenv("TOKEN")
logging.info(f"donor_chat; {donor_chats}")
logging.info(f"recipient_chat; {recipient_chats}")
logging.info(f"file_session; {file_session}")

app = Client(f"/home/gusevskiy/develop/copy_bots/sessions/{file_session}")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

processed_media_groups = set()


async def edit_text_caption(text: str) -> str:
    """Обрезает текст > 1024 символов."""
    return text[:1020] if len(text) > 1020 else text


async def download_and_prepare_media(
    client: Client, media_group: List[Message]
) -> List:
    """Скачивает медиа и формирует список InputMedia."""
    tasks = [client.download_media(msg, in_memory=True) for msg in media_group]
    captions = [
        await edit_text_caption(msg.caption) if msg.caption else ""
        for msg in media_group
    ]
    types = [
        "photo" if msg.photo else "video" if msg.video else "audio" if msg.audio else "document"
        for msg in media_group
    ]
    files = await asyncio.gather(*tasks)

    media_list = []
    for file, caption, type_ in zip(files, captions, types):
        file.seek(0)
        input_file = BufferedInputFile(file.read(), filename=f"{type_}.file")
        if type_ == "photo":
            media_list.append(InputMediaPhoto(
                media=input_file, caption=caption))
        elif type_ == "video":
            media_list.append(InputMediaVideo(
                media=input_file, caption=caption))
        elif type_ == "document":
            media_list.append(InputMediaDocument(
                media=input_file, caption=caption))
        elif type_ == "audio":
            media_list.append(InputMediaAudio(
                media=input_file, caption=caption))
    return media_list


async def handle_single_media(client: Client, message: Message, recipient_chat) -> None:
    """
    Пересылает одиночные медиа-сообщения.
    """
    file = await client.download_media(message, in_memory=True)
    file.seek(0)
    caption = await edit_text_caption(message.caption) if message.caption else ""

    input_file = BufferedInputFile(file.read(), filename=None)
    if message.photo:
        await bot.send_photo(recipient_chat, input_file, caption=caption)
    elif message.video:
        await bot.send_video(recipient_chat, input_file, caption=caption)
    elif message.voice:
        await bot.send_audio(recipient_chat, input_file, caption=caption)
    elif message.video_note:
        await bot.send_video_note(recipient_chat, input_file)
    elif message.document:
        await bot.send_document(recipient_chat, input_file, caption=caption)
    logging.info("Media sent")


@app.on_message(chat(donor_chats))
async def handle_message(client: Client, message: Message) -> None:
    """
    Основной обработчик сообщений.
    """
    try:
        #индекс в списке доноров
        donor_index = donor_chats.index(message.chat.id)
        # название чата из которого пришло сообщение
        donor_chat_id = message.chat.id
        donor_title = message.chat.title
        # сопоставляем по индексу в списке чат для отправки
        recipient_chat = recipient_chats[donor_index]
        
        logging.info(
            f"Сообщение из чата {donor_chat_id}: {donor_title or ''} -> {recipient_chat}"
        )

        # работаем с альбомом
        if message.media_group_id:
            print("media_group")
            if message.media_group_id in processed_media_groups:
                return

            processed_media_groups.add(message.media_group_id)
            media_group = await client.get_media_group(message.chat.id, message.id)
            media_to_send = await download_and_prepare_media(client, media_group)
            # Отправляем Альбом
            await bot.send_media_group(chat_id=recipient_chat, media=media_to_send)
            logging.info("Mediagroup send")

        # работает с одним носителем
        elif message.media in [
            MessageMediaType.PHOTO,
            MessageMediaType.VIDEO,
            MessageMediaType.DOCUMENT,
            MessageMediaType.VOICE,
            MessageMediaType.VIDEO_NOTE,
        ]:
            await handle_single_media(client, message, recipient_chat)

        # работаем с одиночным текстом или ссылкой на что то.
        elif message.text or message.media == MessageMediaType.WEB_PAGE:
            print("text")
            text = await edit_text_caption(message.text) if message.text else ""
            link = message.web_page.url if message.web_page else ""
            await bot.send_message(recipient_chat, f"{text}{link}")
            logging.info("Text send")
    except Exception as e:
        # Получение полного traceback
        logging.error(f"Error:\n{traceback.format_exc()}")


if __name__ == "__main__":
    app.run()
