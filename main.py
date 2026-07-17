import asyncio
import logging
import traceback
import os
from typing import List
from pyrogram import Client, idle
from pyrogram.filters import chat
from pyrogram.enums import MessageMediaType
from pyrogram.types import (
    Message,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InputMediaAudio,
)
from dotenv import load_dotenv
from datetime import datetime, timezone

# Настройка логирования на верхнем уровне
logging.basicConfig(
    format="[%(levelname) 5s] [%(asctime)s] [%(name)s.%(funcName)s:%(lineno)d]: %(message)s",
    level=logging.INFO,
)
load_dotenv()

# Константы, читаются из переменных окружения (см. docker-compose.yaml -> env_file)
donor_chats = list(map(int, os.getenv("DONOR").split(",")))       # id чатов-доноров, откуда читаем сообщения
recipient_chats = list(map(int, os.getenv("RECIPIENT").split(",")))  # id чатов-получателей, по индексу совпадает с donor_chats
file_session = str(os.getenv("SESSION"))  # имя .session файла (userbot-аккаунт), без расширения
logging.info(f"donor_chats: {donor_chats}")
logging.info(f"recipient_chats: {recipient_chats}")
logging.info(f"file_session; {file_session}")

# Единственный клиент (Pyrogram-юзербот): и читает donor_chats, и пересылает в
# recipient_chats. Отдельного bot-аккаунта нет - не нужно добавлять его в каждый
# получатель, нет проблем с "chat not found"/privacy mode, свойственных Bot API.
app = Client(
    f"{file_session}",
    workers=4,  # Параллельная обработка
    sleep_threshold=30,  # Терпим лаги до 30 сек
)

# id медиа-групп (альбомов), которые уже обработали - чтобы не пересылать
# один и тот же альбом повторно (Pyrogram шлёт по одному update на каждое
# сообщение альбома). Набор растёт бесконечно и никогда не чистится (см. improvements).
processed_media_groups = set()


async def edit_text_caption(text: str) -> str:
    """Обрезает текст > 1024 символов."""
    # Telegram не даёт caption длиннее 1024 символов, а Pyrogram-юзербот мог
    # скачать текст/подпись с премиум-аккаунта, где лимит больше (4096).
    return text[:1020] if len(text) > 1020 else text


async def download_and_prepare_media(
    client: Client, media_group: List[Message]
) -> tuple:
    """Скачивает медиа и формирует список InputMedia. Возвращает (media_list, files)."""
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
    # file - BytesIO с уже проставленным Pyrogram'ом атрибутом .name, его можно
    # передавать в InputMedia* напрямую, без обёрток. Закрывать файлы здесь
    # нельзя - send_media_group читает их позже, уже после возврата из этой
    # функции (иначе ловим "I/O operation on closed file"). Закрытие - на
    # вызывающей стороне, после фактической отправки.
    for file, caption, type_ in zip(files, captions, types):
        if type_ == "photo":
            media_list.append(InputMediaPhoto(media=file, caption=caption))
        elif type_ == "video":
            media_list.append(InputMediaVideo(media=file, caption=caption))
        elif type_ == "document":
            media_list.append(InputMediaDocument(media=file, caption=caption))
        elif type_ == "audio":
            media_list.append(InputMediaAudio(media=file, caption=caption))

    return media_list, files


async def handle_single_media(
    client: Client, message: Message, recipient_chat
) -> None:
    """
    Пересылает одиночные медиа-сообщения.
    """
    file = await client.download_media(message, in_memory=True)
    caption = await edit_text_caption(message.caption) if message.caption else ""

    if message.photo:
        await client.send_photo(recipient_chat, file, caption=caption)
    elif message.video:
        await client.send_video(recipient_chat, file, caption=caption)
    elif message.voice:
        # Голосовые сообщения (voice) шлём как send_audio, а не send_voice -
        # осознанный выбор или недосмотр, но именно так их получит подписчик.
        await client.send_audio(recipient_chat, file, caption=caption)
    elif message.video_note:
        await client.send_video_note(recipient_chat, file)
    elif message.document:
        await client.send_document(recipient_chat, file, caption=caption)
    elif message.audio:
        await client.send_audio(recipient_chat, file, caption=caption)
    elif message.animation:
        await client.send_animation(recipient_chat, file, caption=caption)
    elif message.sticker:
        # У стикеров нет caption - Telegram его не поддерживает для этого типа.
        await client.send_sticker(recipient_chat, file)
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
            media_to_send, files = await download_and_prepare_media(client, media_group)
            try:
                # Отправляем Альбом
                await client.send_media_group(recipient_chat, media_to_send)
                logging.info("Mediagroup send")
            finally:
                # Закрываем BytesIO-объекты уже после отправки, чтобы не копить
                # память, но и не закрыть их раньше, чем send_media_group успеет
                # их прочитать.
                for file in files:
                    if file:
                        file.close()

        # работает с одним носителем
        elif message.media in [
            MessageMediaType.PHOTO,
            MessageMediaType.VIDEO,
            MessageMediaType.DOCUMENT,
            MessageMediaType.VOICE,
            MessageMediaType.VIDEO_NOTE,
            MessageMediaType.AUDIO,
            MessageMediaType.ANIMATION,
            MessageMediaType.STICKER,
        ]:
            await handle_single_media(client, message, recipient_chat)

        # работаем с одиночным текстом или ссылкой на что то.
        elif message.text or message.media == MessageMediaType.WEB_PAGE:
            text = await edit_text_caption(message.text) if message.text else ""
            link = message.web_page.url if message.web_page else ""
            await client.send_message(recipient_chat, f"{text}{link}")
            logging.info("Text send")

        # Просто диагностика задержки доставки - на случай, если сообщения
        # обрабатываются с большим опозданием (например из-за FloodWait или очереди).
        # Kurigram отдаёт message.date как naive datetime (без tzinfo), в
        # отличие от pyrotgfork/Pyrogram - приводим к aware UTC перед вычитанием.
        message_date = message.date
        if message_date.tzinfo is None:
            message_date = message_date.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        time_difference = (now - message_date).total_seconds()
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


async def check_donor_chats() -> None:
    """
    Запрашивает последнее сообщение из каждого DONOR-чата при старте.
    Если аккаунт удалён/кикнут из чата, get_chat_history упадёт с исключением -
    это сразу видно в логах при запуске, не дожидаясь первого пропущенного поста.
    """
    for chat_id in donor_chats:
        try:
            last_message = None
            async for message in app.get_chat_history(chat_id, limit=1):
                last_message = message
                break

            if last_message:
                text = last_message.text or last_message.caption or ""
                # Если это часть альбома - подпись может лежать не на этом
                # конкретном сообщении, а на соседнем с тем же media_group_id.
                # Забираем весь альбом и ищем текст по всем его сообщениям.
                if not text and last_message.media_group_id:
                    media_group = await app.get_media_group(chat_id, last_message.id)
                    for msg in media_group:
                        if msg.text or msg.caption:
                            text = msg.text or msg.caption
                            break
                preview = text[:10]
                logging.info(
                    f"[STARTUP CHECK] chat_id={chat_id}: OK, "
                    f"последнее сообщение id={last_message.id} от {last_message.date.isoformat()} "
                    f"text='{preview}'"
                )
            else:
                logging.warning(f"[STARTUP CHECK] chat_id={chat_id}: доступен, но история пуста")
        except Exception:
            logging.error(
                f"[STARTUP CHECK] chat_id={chat_id}: не удалось получить историю "
                f"(возможно, аккаунт удалён/кикнут из чата)\n{traceback.format_exc()}"
            )


async def check_recipient_chats() -> None:
    """
    Проверяет при старте, что юзербот имеет доступ к каждому RECIPIENT-чату -
    то есть может в него постить. Без TOKEN/отдельного бота эта проверка
    делается тем же клиентом, что и check_donor_chats.
    """
    for chat_id in recipient_chats:
        try:
            recipient = await app.get_chat(chat_id)
            logging.info(f"[RECIPIENT CHECK] {chat_id}: OK -> {recipient.title or recipient.first_name}")
        except Exception:
            logging.error(
                f"[RECIPIENT CHECK] {chat_id}: недоступен\n{traceback.format_exc()}"
            )


async def main() -> None:
    async with app:
        # Разовая проверка при старте: get_chat_history/get_chat работают, даже
        # если аккаунт НЕ состоит в чате как участник (например, доступ через
        # админку/публичный юзернейм без вступления) - это прямые запросы.
        # А live-апдейты в on_message Telegram шлёт только реальным
        # подписчикам/участникам. Если донор не попал в диалоги аккаунта -
        # значит, скорее всего, он там не состоит, и live-сообщения оттуда
        # приходить не будут (историю читать можно всё равно).
        dialog_ids = set()
        async for dialog in app.get_dialogs():
            dialog_ids.add(dialog.chat.id)

        for chat_id in donor_chats:
            if chat_id not in dialog_ids:
                logging.warning(
                    f"[DIALOGS CHECK] chat_id={chat_id}: НЕТ в списке диалогов аккаунта - "
                    f"скорее всего, аккаунт не состоит в этом чате как участник, "
                    f"и live-сообщения оттуда приходить не будут (историю читать можно)."
                )

        await check_donor_chats()
        await check_recipient_chats()
        await idle()


if __name__ == "__main__":
    # В Kurigram app.run() больше не принимает корутину аргументом (в отличие
    # от Pyrogram/pyrotgfork) - запускаем main() вручную. asyncio.run() тут не
    # подходит: он создаёт НОВЫЙ loop, а app (Client) уже привязан к дефолтному
    # loop'у в момент создания на уровне модуля - отсюда "attached to a
    # different loop". Используем тот же loop через get_event_loop().
    # Если сессия отозвана/невалидна или сеть недоступна намертво - процесс
    # упадёт уже тут, и это будет видно в самом начале логов контейнера
    # (docker logs two_bots).
    asyncio.get_event_loop().run_until_complete(main())
