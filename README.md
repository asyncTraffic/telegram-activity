
# Telegram Activity Bot

Телеграм-бот для создания активности в чатах Telegram путем имитации общения с помощью нескольких аккаунтов. Включает панель администратора для управления аккаунтами, добавления групп, триггеров для диалогов и встроенную бесплатную нейросеть для генерации разговоров.

## Возможности
- **Панель администратора**: Загрузка `.session` файлов (Telethon), настройка прокси, изменение имени, фото и описания аккаунта.
- **Управление группами**: Добавление групп и привязка к ним Telegram-аккаунтов.
- **Триггеры**:
  - **Триггер на вступление**: Боты начинают общение после присоединения нового участника.
  - **Триггер по времени**: Боты инициируют случайные диалоги в заданное время, имитируя скорость набора текста живым человеком.
- **Генерация диалогов**: Встроенная нейросеть создает диалоги для N участников на основе заданного промта, распределяемые по аккаунтам.
- **Случайные диалоги**: Бот выбирает случайный диалог (например, на 4 участника) и воспроизводит его в группе по ролям.

## Технологии
- **Язык**: Python 3.10
- **База данных**: PostgreSQL (через `asyncpg`)
- **Фреймворк для бота**: `aiogram` 3.5.0
- **Клиент Telegram**: `Telethon` (для работы с `.session` файлами)

## Установка
1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/yourusername/telegram-activity-bot.git
   cd telegram-activity-bot
   ```
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Настройте базу данных PostgreSQL и укажите параметры подключения в `.env`:
   ```
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_NAME=your_db_name
   DB_HOST=your_db_host
   DB_PORT=your_db_port
   TOKEN=your_bot_token
   ```
4. Настройте `data/config.py`:
   - Укажите `API_ID` и `API_HASH` для Telethon.
   - Добавьте Telegram ID администраторов в `ADMINS`.
   - Настройте темы для диалогов в `DETAILS` и отредактируйте промт, если нужно.
5. Убедитесь, что в папке проекта есть:
   - `main.py` с кодом бота
   - `requirements.txt` с зависимостями
   - `.env` с переменными окружения
6. Загрузите проект на сервер Ubuntu.
7. Дайте права на исполнение скрипту `setup.sh`:
   ```bash
   chmod +x setup.sh
   ```
8. Запустите скрипт:
   ```bash
   ./setup.sh
   ```
9. Дождитесь сообщения `All steps completed successfully!` и проверьте статус сервиса:
   ```bash
   systemctl status autodialog
   ```

## Использование
1. Запустите бот и откройте панель администратора в Telegram.
2. Загрузите `.session` файлы Telegram-аккаунтов, настройте прокси, имена, фото и описания.
3. Добавьте группы и привяжите к ним аккаунты.
4. Настройте триггеры для автоматического запуска диалогов.
5. Бот начнет генерировать и воспроизводить диалоги в группах на основе промта.

## Управление сервисом
Бот автоматически запускается и управляется через `systemd`. Для проверки статуса, перезапуска или остановки используйте:
```bash
systemctl status autodialog
systemctl restart autodialog
systemctl stop autodialog
```

## Скриншоты
<img width="618" height="780" alt="image" src="https://github.com/user-attachments/assets/6d635786-3ff5-42ee-971e-9df26b2855ad" />

<img width="618" height="780" alt="image" src="https://github.com/user-attachments/assets/8fdfb9ce-c133-4f52-927c-77e8f2188286" />

<img width="618" height="780" alt="image" src="https://github.com/user-attachments/assets/4b196c0f-146a-4316-9b73-256831c2412f" />

<img width="618" height="780" alt="image" src="https://github.com/user-attachments/assets/0378e6cc-7bfd-4c6d-8384-8609544a31e6" />

<img width="618" height="780" alt="image" src="https://github.com/user-attachments/assets/dab2583a-38c6-4820-af7d-9a9c67d4e526" />

<img width="618" height="780" alt="image" src="https://github.com/user-attachments/assets/3600e090-e93c-4fb1-b80c-44a07a9dc306" />

<img width="618" height="780" alt="image" src="https://github.com/user-attachments/assets/2bc1d973-bdf8-470b-97bb-424222138663" />


## Контакты
Для связи с разработчиком:
- Telegram: https://t.me/asynctraffic_tg
- Telegram комьюнити (чат): https://t.me/+mpeVd6Dkc8E5ZWVi
- Telegram канал: https://t.me/async_traffic_channel

## Лицензия
MIT License
