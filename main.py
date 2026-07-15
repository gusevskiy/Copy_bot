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
from datetime import datetime, timezone
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


# Путь захардкожен под dev-машину и на сервере не существует, поэтому
# find_dotenv тут ничего не найдёт. В докере это не страшно, т.к.
# переменные приходят напрямую из docker-compose "environment:", но если
# запускать main.py руками (не в контейнере) на сервере, .env не подхватится.
load_dotenv(find_dotenv("/home/gusevskiy/develop/copy_bots/sessions/.env"))

# Константы, читаются из переменных окружения (см. docker-compose.yml -> environment:)
donor_chats = list(map(int, os.getenv("DONOR").split(",")))       # id чатов-доноров, откуда читаем сообщения
recipient_chats = list(map(int, os.getenv("RECIPIENT").split(",")))  # id чатов-получателей, по индексу совпадает с donor_chats
file_session = str(os.getenv("SESSION"))  # имя .session файла (userbot-аккаунт), без расширения
BOT_TOKEN = os.getenv("TOKEN")            # токен обычного Telegram-бота (aiogram), через него идёт постинг
logging.info(f"donor_chats: {donor_chats}")
logging.info(f"recipient_chats: {recipient_chats}")
logging.info(f"file_session; {file_session}")

# Клиент-userbot (Pyrogram) - читает сообщения из donor_chats.
# Использует уже существующий .session файл (авторизация не нужна, если он валиден).
app = Client(
    f"{file_session}",
    workers=4,  # Параллельная обработка
    sleep_threshold=30,  # Терпим лаги до 30 сек
)
# Обычный бот (aiogram) - именно он публикует контент в recipient_chats.
# Если TOKEN невалиден/просрочен, Bot(token=...) упадёт уже на этой строке,
# т.е. процесс не запустится вообще (это будет видно в самом начале логов).
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# id медиа-групп (альбомов), которые уже обработали - чтобы не пересылать
# один и тот же альбом повторно (Pyrogram шлёт по одному update на каждое
# сообщение альбома). Набор растёт бесконечно и никогда не чистится (см. improvements).
processed_media_groups = set()


async def edit_text_caption(text: str) -> str:
    """Обрезает текст > 1024 символов."""
    # Telegram Bot API не даёт caption длиннее 1024 символов (у обычных ботов),
    # а Pyrogram-юзербот мог скачать текст/подпись с премиум-аккаунта, где лимит больше (4096).
    return text[:1020] if len(text) > 1020 else text


async def download_and_prepare_media(
    client: Client, media_group: List[Message]
) -> List:
    """Скачивает медиа и формирует список InputMedia."""
    # Качаем все файлы альбома в память (in_memory=True) параллельно через asyncio.gather ниже.
    tasks = [client.download_media(msg, in_memory=True) for msg in media_group]
    captions = [
        await edit_text_caption(msg.caption) if msg.caption else ""
        for msg in media_group
    ]
    # Определяем тип каждого сообщения в альбоме, чтобы завернуть его в нужный InputMedia*.
    types = [
        "photo"
        if msg.photo
        else "video"
        if msg.video
        else "audio"
        if msg.audio
        else "document"
        for msg in media_group
    ]
    files = await asyncio.gather(*tasks)

    media_list = []
    try:
        for file, caption, type_ in zip(files, captions, types):
            file.seek(0)
            input_file = BufferedInputFile(file.read(), filename=f"{type_}.file")
            if type_ == "photo":
                media_list.append(InputMediaPhoto(media=input_file, caption=caption))
            elif type_ == "video":
                media_list.append(InputMediaVideo(media=input_file, caption=caption))
            elif type_ == "document":
                media_list.append(InputMediaDocument(media=input_file, caption=caption))
            elif type == "audio":
                # БАГ: сравнение идёт со встроенным builtin `type`, а не с переменной `type_`.
                # Это условие никогда не истинно, поэтому аудио-файлы внутри альбома
                # молча выпадают из media_list (скачиваются, но не отправляются).
                # Должно быть: elif type_ == "audio":
                media_list.append(InputMediaAudio(media=input_file, caption=caption))
    finally:
        # Закрываем BytesIO-объекты, чтобы не копить память, даже если отправка упала.
        for file in files:
            if file:
                file.close()

    return media_list


async def handle_single_media(
    client: Client, message: Message, recipient_chat, donor_title
) -> None:
    """
    Пересылает одиночные медиа-сообщения.
    """
    # Скачиваем файл userbot-клиентом (Pyrogram) и тут же заливаем его через bot-клиента (aiogram),
    # т.е. файл проходит транзитом через память процесса, а не пересылается напрямую в Telegram.
    file = await client.download_media(message, in_memory=True)
    file.seek(0)
    caption = await edit_text_caption(message.caption) if message.caption else ""

    input_file = BufferedInputFile(file.read(), filename=None)
    if message.photo:
        await bot.send_photo(recipient_chat, input_file, caption=caption)
    elif message.video:
        await bot.send_video(recipient_chat, input_file, caption=caption)
    elif message.voice:
        # Голосовые сообщения (voice) шлём как send_audio, а не send_voice -
        # осознанный выбор или недосмотр, но именно так их получит подписчик.
        await bot.send_audio(recipient_chat, input_file, caption=caption)
    elif message.video_note:
        await bot.send_video_note(recipient_chat, input_file)
    elif message.document:
        await bot.send_document(recipient_chat, input_file, caption=caption)
    logging.info("Media sent")


# chat(donor_chats) - фильтр Pyrogram: хэндлер сработает только на сообщения
# из чатов, перечисленных в donor_chats. Юзербот должен состоять в этих чатах
# (либо иметь к ним доступ) - если его оттуда удалили/кикнули, сообщения просто
# перестанут сюда попадать без каких-либо ошибок в логе.
@app.on_message(chat(donor_chats))
async def handle_message(client: Client, message: Message) -> None:
    """
    Основной обработчик сообщений.
    """
    try:
        # индекс в списке доноров
        donor_index = donor_chats.index(message.chat.id)
        # название чата из которого пришло сообщение
        donor_chat_id = message.chat.id
        donor_title = message.chat.title
        # сопостовляем по индексу в списке чат для отправки:
        # donor_chats[i] -> recipient_chats[i]. Если списки в .env рассинхронизированы
        # по длине/порядку (например добавили донора, забыли добавить получателя),
        # тут будет IndexError, и упадёт именно в except ниже - без явного указания причины.
        recipient_chat = recipient_chats[donor_index]

        logging.info(
            f"Сообщение из чата {donor_chat_id}: {donor_title or ''} -> {recipient_chat}"
        )

        # работаем с альбомом
        if message.media_group_id:
            # Pyrogram присылает отдельный update на КАЖДОЕ сообщение альбома,
            # поэтому дедуплицируем по media_group_id и обрабатываем альбом только
            # один раз (на первом попавшемся сообщении из него).
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
            # передаем, отправляет там
            await handle_single_media(client, message, recipient_chat, donor_title)

        # работаем с одиночным текстом или ссылкой на что то.
        elif message.text or message.media == MessageMediaType.WEB_PAGE:
            text = await edit_text_caption(message.text) if message.text else ""
            link = message.web_page.url if message.web_page else ""
            await bot.send_message(recipient_chat, f"{text}{link}")
            logging.info("Text send")

        # Просто диагностика задержки доставки - на случай, если сообщения
        # обрабатываются с большим опозданием (например из-за FloodWait или очереди).
        now = datetime.now(timezone.utc)
        time_difference = (now - message.date).total_seconds()
        logging.info(
            f"[TIME CHECK] message.date = {message.date.isoformat()} | "
            f"server_time = {now.isoformat()} | "
            f"diff = {time_difference:.2f} seconds"
        )
    except Exception:
        # Ловим ЛЮБУЮ ошибку на уровне одного сообщения (в т.ч. FloodWait от Telegram,
        # IndexError из-за рассинхронизации donor/recipient, сетевые сбои и т.д.) -
        # сообщение при этом теряется без повторной попытки, но сам бот не падает
        # и продолжает обрабатывать следующие сообщения. Смотреть именно этот лог,
        # если "бот не пересылает конкретное сообщение".
        logging.error(f"Error:\n{traceback.format_exc()}")


if __name__ == "__main__":
    # app.run() держит соединение и сам переподключается при обрывах связи.
    # Но если сессия отозвана/невалидна (см. тест сессии выше) или сеть недоступна
    # намертво - процесс упадёт уже тут, до входа в handle_message, и это будет
    # видно в самом начале логов контейнера (docker logs two_bots).
    app.run()
