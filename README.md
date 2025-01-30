# Copy_bot
Бот для удобства отслеживания контента.
Пересылает сообщения из нескольких груп на котрые подписан владелец в одну. 

Пересылает все: текст, картинки, голосовые и видео (все группируется в рамках одного сообщения)

Для работы бота на сервере нужно:

[Docker](https://docs.docker.com/engine/install/ubuntu/)

[Python](https://python.org) 3.11

[Client pyrogram](https://docs.pyrogram.org/intro/quickstart)

[Bot telegram](https://telegram.me/BotFather)

```bash
git clone https://github.com/gusevskiy/Copy_bot

python -m venv venv

. venv/bin/activate

pip install -r requirements.txt

docker compose up
```

В docker-compose файле нужно прописать 
в DONOR список групп из которых нужно получать контент
в RECIPIENT группу, в которую нужно пересылать контент.  
Получение и доставка индексируются но индексу списка
если нужно пересылать в одну группу то в RECIPIENT должна бать одна группа кратно списку DONOR.  
Те сообщения из групп 111111 и 222222 будут пересылаться в 333333.  
Можно делить на  
DONOR "111111, 222222, 333333, 444444" в  
RECIPIENT "55555, 55555, 666666, 666666"  
соответственно сообщения из 111111 и 222222 пойдут в 555555, а 333333 и 444444 в 66666
```bash
      DONOR: "111111, 222222"
      SESSION: "name_seccion"
      # Токен для aiogram3
      TOKEN: "TOKENTOKENTOKENTOKENTOKENTOKENTOKENTOKENTOKEN"
      # Чат в который шлет msg бот aiogram3
      RECIPIENT: "333333, 333333"
```

[нужна подсказка](https://t.me/gusevsk1y)
