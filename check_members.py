import asyncio
import os
import sys

from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()


async def main(chat_id: int) -> None:
    file_session = str(os.getenv("SESSION"))
    app = Client(file_session)

    async with app:
        me = await app.get_me()
        print(f"Аккаунт: @{me.username or ''} (id={me.id})")

        chat = await app.get_chat(chat_id)
        print(f"Чат: {chat.title or chat.first_name} (id={chat.id}, type={chat.type})")

        print("Участники:")
        try:
            async for member in app.get_chat_members(chat_id):
                user = member.user
                print(f"  id={user.id} @{user.username or ''} {user.first_name or ''} {user.last_name or ''}")
        except Exception as e:
            print(f"Не удалось получить список участников: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python3 check_members.py <chat_id>")
        sys.exit(1)
    asyncio.run(main(int(sys.argv[1])))
