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
    """_summary_

    Args:
        msg (Message): Сообщение из канала донора

    Returns:
        str[0]: первые 980 символов из caption
        str[1]: остаток текста, если он превышает 980 символов
    лимит только 1024 символа, 4024 в telegram premium
    """
    msg = vars(msg)
    len_caption = len(msg.get("caption"))
    logger.info(f"len caption: {len_caption}")
    
    if len_caption < 980:
        msg_caption = (
            msg.get("caption") + "\n\n" + "Этот текст был изменен при пересылке!!!"
        )
        msg_text = None
    else:
        split_text = msg.get("caption").split("\n\n")
        msg_caption = split_text[0] + "\n\n" + "Этот текст был изменен при пересылке!!!"
        msg_text = (
            "\n".join(split_text[1:])
            + "\n\n"
            + " Этот текст был изменен при пересылке!!!"
        )

    logger.info(f"Текст изменен!!")
    return msg_caption, msg_text


def delete_file(file_path: str) -> None:
    """_summary_
    Args:
        file_path (str): delited file path
    """
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
    # Получаем название канала
    try:
        print(message.caption[:20])
        channel_title = message.chat.title if message.chat else "recipient channel"

        async for message in client.get_chat_history(
            chat_id=os.getenv("DONOR_CHANNEL_ID"),
            limit=1,  # Установите желаемое количество сообщений
            offset_id=-1,
        ):
            if message.photo:
                logger.info(f"Новое сообщение с фото в канале: {message.caption[:20]}")
                await client.send_message(chat_id=recipient_chat, text=channel_title)
                # описание текста сообщения находится в ключе "caption" длинна текста в сообщении не должна превышать 1024 символов
                msg_caption, msg_text = await massage_transform(message)
                # Загружаем фото
                file_path = await message.download(file_name=path_image)
                logger.info(f"Фото загружено: {file_path}")

                await client.send_photo(
                    chat_id=recipient_chat,
                    photo=path_image,
                    caption=msg_caption,
                )
                if msg_text is not None:
                    await client.send_message(
                        chat_id=recipient_chat,
                        text=msg_text,
                    )
                logger.info(f"Сообщение переслано в канал: {recipient_chat}")
            else:
                logger.info(f"в сообщении нет фотографии, пересылка не производится")

        delete_file(path_image)  # Удаляем загруженное фото
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщений: {str(e)}")


if __name__ == "__main__":
    asyncio.run(client.run())
