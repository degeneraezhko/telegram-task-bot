# Telegram Task Manager Bot

Бот-планировщик задач для Telegram с приоритетами, дедлайнами и статистикой.

## Что делает

- Добавление задач с приоритетом (высокий/средний/низкий) и дедлайном
- Просмотр списка активных и завершённых задач
- Завершение и удаление задач
- Статистика: сколько всего, активно, завершено, срочных
- Данные хранятся в SQLite

## Как сделано

- **Python 3.10+**, python-telegram-bot 20.x
- ConversationHandler для пошагового ввода
- SQLite для хранения задач
- Keyboard-интерфейс (не команды)

## Стек

`Python` `python-telegram-bot` `SQLite` `ConversationHandler`

## Запуск

```bash
pip install python-telegram-bot
export TELEGRAM_BOT_TOKEN="your_token"
python main.py
```

## Скриншоты

См. `/screenshots/`
