import asyncio
import os
import sys

from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()


async def main(chat_ids: list[int]) -> None:
    """Получение последнего сообщения из одного или нескольких чатов"""
    file_session = str(os.getenv("SESSION"))
    app = Client(file_session)

    async with app:
        me = await app.get_me()
        print(f"Аккаунт: @{me.username or ''} (id={me.id})")

        for chat_id in chat_ids:
            try:
                chat = await app.get_chat(chat_id)
                title = chat.title or chat.first_name or ""

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
                    preview = text[:50]
                    print(
                        f"chat_id={chat_id} ({title}): "
                        f"id={last_message.id} от {last_message.date.isoformat()} "
                        f"text='{preview}'"
                    )
                else:
                    print(f"chat_id={chat_id} ({title}): история пуста")
            except Exception as e:
                print(f"chat_id={chat_id}: ОШИБКА -> {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 check_last_message.py <chat_id> [chat_id2 ...]")
        sys.exit(1)
    asyncio.run(main([int(arg) for arg in sys.argv[1:]]))
