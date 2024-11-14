import os
import asyncio
import traceback
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.log_config import setup_logger

logger = setup_logger()
load_dotenv()
client = Client(name="my_client")
# Храним ID последней группы, чтобы избежать повторной обработки
last_media_group_id = None


# Получаем путь к директории, где находится текущий файл
current_dir = os.path.dirname(os.path.abspath(__file__))
path_image = os.getenv("PATH_IMAGE")
# Используем os.path.join для правильного объединения путей
full_path_image = os.path.join(current_dir, path_image)
logger.info(f"Полный путь к image: {full_path_image}")

donor_chat = int(os.getenv("DONOR_CHANNEL_ID"))
logger.info(f"donor_chat: {donor_chat}")

recipient_chat = int(os.getenv("RECIPIENT_CHANNEL_ID"))
logger.info(f"recipient_chat: {recipient_chat}")


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


async def delete_file(file_path: str) -> None:
    """Удаляет все файлы в директории, где находится указанный файл.

    Args:
        file_path (str): Путь к файлу для удаления.
    """
    # Проверяем, есть ли путь к папке
    if os.path.isfile(file_path):
        path_dir = os.path.dirname(file_path)
        logger.info(f"Путь к директории: {path_dir}")

        for filename in os.listdir(path_dir):
            full_path = os.path.join(path_dir, filename)
            try:
                # Удаляем файл, если это действительно файл
                if os.path.isfile(full_path):
                    await asyncio.to_thread(os.remove, full_path)
                    logger.info(f"Файл удален: {full_path}")
                    await asyncio.sleep(1)  # которкая пауза чтобы избежать блокировки
            except Exception as e:
                logger.error(f"Ошибка при удалении файла: {full_path} - {e}")
    else:
        logger.error(f"Файл не найден: {file_path}")


async def process_file(client, message, channel_title):
    """Обрабатывает фотографии из группы и пересылает их в recipient_chat

    Args:
        client (_type_): Клиент зарегистрированный на Telegram user
        message (Message): Сообщение из канала donor_chat
        channel_title (str): Название канала donor_chat
    """
    logger.info(f"Обрабатываем фотографии из группы: {channel_title}")
    msg_caption, msg_text = await massage_transform(message)
    # Загружаем фото
    file_path = await message.download(file_name=full_path_image)
    logger.info(f"Фото загружено: {file_path}")
    await client.send_message(chat_id=recipient_chat, text=channel_title)
    await client.send_photo(
        chat_id=recipient_chat,
        photo=full_path_image,
        caption=msg_caption,
    )
    if msg_text is not None:
        await client.send_message(
            chat_id=recipient_chat,
            text=msg_text,
        )
    logger.info(f"Сообщение переслано в канал: {recipient_chat}")

    await delete_file(full_path_image)  # Удаляем загруженное фото


@client.on_message(filters.chat(chats=donor_chat))
async def clone_content(client, message: Message) -> None:
    """
    Args:
        client (_type_): Клиент зарегистрированный на Telegram user
        message (Message): сообщение в канале donor_chat
    return: None
    """
    try:
        logger.info("Start")
        global last_media_group_id
        # Получаем название канала
        channel_title = message.chat.title if message.chat else "recipient channel"
        if message.media_group_id and message.caption:
            if message.media_group_id == last_media_group_id:
                logger.info(
                    "Пропускаем сообщение, так как он является частью медиа-группы"
                )
                return
            # обновляем ID последнего альбома
            last_media_group_id = message.media_group_id
            logger.info(f"Новое сообщение с альбомом фото в канале:")

            await process_file(client, message, channel_title)

        # Обработка сообщений с одной фотографией
        elif message.photo and not message.media_group_id:
            logger.info(
                f"Новое сообщение с одной фотографией в канале: {channel_title}"
            )
            await process_file(client, message, channel_title)

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Ошибка при обработке сообщений: {str(e)}\n{error_trace}")
    finally:
        logger.info("End")


if __name__ == "__main__":
    asyncio.run(client.run())
