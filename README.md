# Copy_bot
копирует сообщения из групп

# копировать на сервер
rsync -av --exclude='.git' --exclude='venv' --exclude='logs' /mnt/d/DEV_python/Copy_bot/ root@45.132.18.171:/root/bot/    


docker run -d -v $(pwd)/logs:/app/logs <image_name>  
