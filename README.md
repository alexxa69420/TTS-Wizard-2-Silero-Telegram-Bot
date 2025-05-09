# TTS-Wizard-2-Silero-Telegram-Bot

[![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/navendu-pottekkat/awesome-readme?include_prereleases)](https://img.shields.io/github/v/release/navendu-pottekkat/awesome-readme?include_prereleases)
[![GitHub last commit](https://img.shields.io/github/last-commit/navendu-pottekkat/awesome-readme)](https://img.shields.io/github/last-commit/navendu-pottekkat/awesome-readme)
[![GitHub issues](https://img.shields.io/github/issues-raw/navendu-pottekkat/awesome-readme)](https://img.shields.io/github/issues-raw/navendu-pottekkat/awesome-readme)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/navendu-pottekkat/awesome-readme)](https://img.shields.io/github/issues-pr/navendu-pottekkat/awesome-readme)

я заебалась сливать ~3к сом в месяц элевенам за то чтобы говорить прикольным голосом, поэтому разработала этот код что ловит запросы от TTS Voice Wizard и кидает их на генерацию к боту @silero_voice_bot в телеграмме (у них дешевая подписка и куча символов в отличии от элевенов), после чего слушает ответ в виде голосового сообщения, которое обратно отдает на проигрывание в ТТС

# Установка

Если у вас нету Python, то установите его по ссылке: 
https://www.python.org/downloads/

Если у вас нету FFMPEG в PATH, то установите его, гайдов в интернете достаточно.

Скачайте последний релиз по ссылке: 
https://github.com/alexxa69420/TTS-Wizard-2-Silero-Telegram-Bot/releases

В папке куда вы распаковали архив откройте install.bat для установки venv чтобы компоненты не конфликтовали с чем бы у вас там не было + всего нужного для работы, после чего запустите start.bat.

При первом открытии файла приложение запросит вас ввести API_ID и API_HASH которые вы можете получить после создания приложения в https://my.telegram.org/apps

После чего, для создания сессии, код укажет ввести ваш номер привязанный к телеграм аккаунту, пароль двухфакторной защиты если она у вас включена, и код присланный телеграмом.

<b>Код не собирает и не отправляет ваши личные данные, поэтому код с открытым источником, любой пользователь в праве посмотреть что делает код в деталях.</b>

В TTS Voice Wizard установите `Text To Speech Mode` как `Locally Hosted`, и в настройках поменяйте значнение `OSC Send Port` на `8124`, и не забудьте применить изменение.


# @mention

тгк: https://t.me/alexxa69ch

Отдельный шатаут https://t.me/Weiss_Stille за библиотеку num2words и помощь в коде ^^


# Лицензия и просьба с предупреждением

Уточнение лицензии проекта:

[MIT license](./LICENSE)

Вкратце кому tl:rd, лицензия подразумевает собой "делай чо хочешь, НО оставьте упоминание автора, т.е. этого репо, у себя в описании"

<B> Этот проект предоставляется как есть. Разработчик не несет НИКАКОЙ ответственности за любые проблемы, вызванные юзерботом. Устанавливая код, вы принимаете все риски на себя. Это, но не ограничивается банами аккаунтов, удаленными (алгоритмами Telegram) сообщениями. Пожалуйста, прочитайте условия предоставления услуг API телеграма https://core.telegram.org/api/terms для получения дополнительной информации. </b>

вообще кстати по сути не должно, НО Я НИЧЕГО НЕ ОБЕЩАЮ, угроза бана зависит от количества отправляемых запросов, но если вы простой человек, то не думаю что будет что то плохое :DD

НО Я НИЧЕГО НЕ ОБЕЩАЮ!!
