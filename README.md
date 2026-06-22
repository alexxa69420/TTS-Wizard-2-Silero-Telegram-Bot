### TTS-Wizard-2-Silero-Telegram-Bot

[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/navendu-pottekkat/awesome-readme?include_prereleases)](https://img.shields.io/github/v/release/navendu-pottekkat/awesome-readme?include_prereleases)
[![GitHub last commit](https://img.shields.io/github/last-commit/navendu-pottekkat/awesome-readme)](https://img.shields.io/github/last-commit/navendu-pottekkat/awesome-readme)
[![GitHub issues](https://img.shields.io/github/issues-raw/navendu-pottekkat/awesome-readme)](https://img.shields.io/github/issues-raw/navendu-pottekkat/awesome-readme)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/navendu-pottekkat/awesome-readme)](https://img.shields.io/github/issues-pr/navendu-pottekkat/awesome-readme)

## О проекте

Я заебалась сливать ~3к сом в месяц элевенам за то, чтобы говорить прикольным голосом, поэтому разработала этот код.

**Что он делает:**
1. Ловит запросы от **TTS Voice Wizard**.
2. Кидает их на генерацию к боту [@silero_voice_bot](https://t.me/silero_voice_bot) в телеграмме (у них дешевая подписка и куча символов, в отличие от элевенов).
3. Получает аудио и отдает его обратно в TTS Wizard.
4. **[NEW]** Дублирует текст, который вы сказали, прямо в **Twitch Chat** от вашего имени (или имени бота). (ДЛЯ РАБОТЫ ЭТОЙ ФУНКЦИИ ИСПОЛЬЗУЙТЕ "start_TITTS.bat").

---

# Установка

### 1. Подготовка
Если у вас нет Python, то установите его по ссылке:
https://www.python.org/downloads/
**Важно:** Требуется версия **3.12 и выше**.

Если у вас нет **FFMPEG** в PATH, то установите его (гайдов в интернете достаточно, это нужно для конвертации аудио).

### 2. Скачивание
Скачайте последний релиз по ссылке:
https://github.com/alexxa69420/TTS-Wizard-2-Silero-Telegram-Bot/releases

В папке, куда вы распаковали архив, откройте `install.bat` для установки venv, чтобы компоненты не конфликтовали с чем бы у вас там ни было + всего нужного для работы.

### 3. Первый запуск и настройка (`start.bat`)

Запустите `start.bat`. При первом запуске приложение попросит ввести данные для Telegram и Twitch.

#### А. Настройка Telegram (для генерации звука)
Код запросит `API_ID` и `API_HASH`.
1. Перейдите на https://my.telegram.org/apps
2. Создайте приложение (можно вводить любые данные).
3. Скопируйте полученные ID и Hash в консоль.
4. Далее код попросит войти в аккаунт (ввести номер телефона и код подтверждения от Telegram).

#### Б. Настройка Twitch (для отправки сообщений в чат)
Код запросит данные для подключения к чату:
1. **Twitch Username**: Логин аккаунта, от имени которого будут отправляться сообщения (ваш основной или бот аккаунт).
2. **Twitch OAuth Token**: Это "пароль" для скрипта.
   * Получить его можно тут: **https://twitchtokengenerator.com/**
   * Нажмите "Bot Chat Token", и скопируйте "ACCESS TOKEN".
3. **Ссылка на канал**: Ссылка на канал, в чат которого нужно писать (например `https://www.twitch.tv/alexxa69419`).

> **Важно:** Все данные сохраняются локально в файл `.env`. Код не собирает и не отправляет ваши личные данные никуда, кроме серверов Telegram и Twitch для авторизации. Код с открытым источником, любой пользователь в праве посмотреть, что делает код в деталях.

---

# Настройка TTS Voice Wizard

1. Откройте TTS Voice Wizard.
2. Установите `Text To Speech Mode` как **`Locally Hosted`**.
3. В настройках поменяйте значение `OSC Send Port` (или API Port) на **`8124`**.
4. **Не забудьте применить изменения!**

Теперь, когда вы печатаете в TTS Wizard, звук будет генерироваться через Silero Bot, а текст — улетать в чат Твича.

---

# @mention

тгк: https://t.me/alexxa69ch

Отдельный шатаут https://t.me/Weiss_Stille за библиотеку num2words и помощь в коде ^^

# Лицензия и просьба с предупреждением

Уточнение лицензии проекта:

[MIT license](./LICENSE)

Вкратце кому tl;dr: лицензия подразумевает собой "делай чо хочешь, НО оставьте упоминание автора или этого репо, у себя в описании".

<B>Этот проект предоставляется как есть. Разработчик не несет НИКАКОЙ ответственности за любые проблемы, вызванные юзерботом. Устанавливая код, вы принимаете все риски на себя. Это включает, но не ограничивается: банами аккаунтов, удаленными (алгоритмами Telegram) сообщениями. Пожалуйста, прочитайте условия предоставления услуг API телеграма https://core.telegram.org/api/terms для получения дополнительной информации.</B>

Вообще, кстати, по сути не должно, НО Я НИЧЕГО НЕ ОБЕЩАЮ. Угроза бана зависит от количества отправляемых запросов, но если вы простой человек, то не думаю, что будет что-то плохое :DD

НО Я НИЧЕГО НЕ ОБЕЩАЮ!!
