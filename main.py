import os
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from utils.log_config import setup_logger

logger = setup_logger()
load_dotenv()
client = Client(name="my_session")


donor_chat = int(os.getenv("DONOR_CHANNEL_ID"))
recipient_chat = int(os.getenv("RECIPIENT_CHANNEL_ID"))
path_image = os.getenv("PATH_IMAGE")


async def massage_transform(msg: Message) -> str:
    msg = vars(msg)
    msg_caption = msg.get("caption") + "\n\n" + "Этот текст был изменен при пересылке!!!"
    logger.info(f"Текст изменен: {msg_caption}")
    return msg_caption


def delete_file(file_path: str) -> None:
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Файл удален: {file_path}")
    else:
        logger.info(f"Файл не найден: {file_path}")



@client.on_message(filters.chat(chats=donor_chat))
async def clone_content(client, message: Message) -> None:
    """ 
    Args:
        client (_type_): Клиент зарегистрированный на Telegram user
        message (Message): сообщение в канале donor_chat
    return: None
    """
    logger.info(f"Новое сообщение в канале: {message.caption[:20]}")
    async for message in client.get_chat_history(
        chat_id=os.getenv("DONOR_CHANNEL_ID"),
        limit=1,  # Установите желаемое количество сообщений
        offset_id=-1,
    ):
        print("type", type(message.caption))

        if message.photo:
            # описание текста сообщения находится в ключе "caption" длинна текста в сообщении не должна превышать 1024 символов
            transformed_message = await massage_transform(message)
            # Загружаем фото
            file_path = await message.download(file_name=path_image)
            logger.info(f"Фото загружено: {file_path}")

            await client.send_photo(
                chat_id=recipient_chat,
                photo=path_image,
                caption=transformed_message,
            )
            logger.info(f"Сообщение переслано в канал: {recipient_chat}")
        logger.info(f"в сообщении нет фотографии")

    delete_file(path_image)  # Удаляем загруженное фото


if __name__ == "__main__":
    asyncio.run(client.run())
