# --- START OF FILE app.py ---

import os
import threading
import asyncio
import urllib.parse
import logging
import base64
import tempfile
from datetime import datetime
from io import BytesIO
import time
import shutil
import re
import os

from dotenv import load_dotenv
from flask import Flask, request, Response, jsonify
from pyrogram import Client, filters, enums
from pyrogram.errors import UserAlreadyParticipant, UserNotParticipant, FloodWait
from pydub import AudioSegment
from pydub.utils import mediainfo
from num2words import num2words
from pymystem3 import Mystem # <<< ИЗМЕНЕНИЕ: Импорт Mystem >>>

# --- КОНФИГУРАЦИЯ ---
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Проверка, заданы ли API_ID и API_HASH
if not API_ID or not API_HASH:
    print("Файл .env не найден или в нём отсутствуют API_ID и API_HASH.")
    print("Получите их на https://my.telegram.org/apps и введите ниже:")

    API_ID = input("Введите API_ID: ").strip()
    API_HASH = input("Введите API_HASH: ").strip()

    # Сохраняем в .env файл
    with open(".env", "w") as f:
        f.write(f"API_ID={API_ID}\n")
        f.write(f"API_HASH={API_HASH}\n")

    print(".env файл успешно создан.")

# Преобразуем API_ID в int (он может быть строкой после input)
API_ID = int(API_ID)

# Остальная часть конфигурации
SESSION_NAME = "my_account"
TARGET_BOT_USERNAME = "silero_voice_bot"
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 8124
RESPONSE_TIMEOUT = 30
DEBUG_WAV_DIR = "debug_wavs"

os.makedirs(DEBUG_WAV_DIR, exist_ok=True)

# --- Настройки логирования ---
# ... (без изменений) ...
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(threadName)s (%(funcName)s) - %(message)s')
logger = logging.getLogger(__name__)

# --- Глобальные переменные ---
# ... (без изменений) ...
pyrogram_client = None
telegram_loop = None
TARGET_BOT_ID = None
pending_requests = {}
pending_requests_lock = threading.Lock()

# <<< ИЗМЕНЕНИЕ: Инициализация Mystem >>>
# Используем try-except на случай, если Mystem не установлен или не найден
try:
    # mystem = Mystem() # Стандартная инициализация
    # Указываем граммемы для ускорения и уменьшения вывода
    mystem = Mystem(grammar_info=True, entire_input=False)
    logger.info("Mystem инициализирован успешно.")
    # Пробный запуск для инициализации/скачивания (если нужно)
    try:
        _ = mystem.analyze("тест")
        logger.info("Пробный анализ Mystem прошел.")
    except Exception as init_err:
         logger.error(f"Ошибка при пробном запуске Mystem (возможно, требуется скачивание бинарных файлов): {init_err}")
         # Можно добавить более сложную логику поиска/указания пути к mystem
         # Например: mystem = Mystem(mystem_binary='C:/path/to/mystem.exe')
         # Но пока предполагаем, что авто-скачивание сработает или он в PATH
except Exception as e:
    logger.error(f"Не удалось инициализировать Mystem: {e}. Коррекция рода числительных будет отключена.")
    mystem = None # Устанавливаем в None, чтобы проверки ниже работали

# --- Инициализация Flask ---
app = Flask(__name__)

# --- Логика Flask ---

# <<< ИЗМЕНЕНИЕ: Функция для коррекции рода с использованием Mystem >>>
def correct_numeral_gender_mystem(text):
    """
    Корректирует род числительных "один" и "два" на основе следующего слова,
    используя Pymystem3.
    """
    if not mystem: # Если Mystem не был инициализирован
        logger.warning("Mystem недоступен, коррекция рода пропускается.")
        return text

    words = text.split(' ')
    corrected_words = []
    i = 0
    while i < len(words):
        word = words[i]
        corrected_word = word

        if word in ["один", "два"]:
            if i + 1 < len(words):
                next_word = words[i+1]
                # Убираем возможные знаки препинания с конца
                cleaned_next_word = re.sub(r'[^\w\s]+$', '', next_word).strip()

                if cleaned_next_word:
                    try:
                        # Анализируем только следующее слово
                        analysis = mystem.analyze(cleaned_next_word)
                        # logger.debug(f"Word: {word}, Next: {cleaned_next_word}, Analysis: {analysis}") # Отладка

                        # Ищем первый результат анализа для этого слова
                        if analysis and 'analysis' in analysis[0] and analysis[0]['analysis']:
                            # Берем первый вариант разбора
                            gr = analysis[0]['analysis'][0]['gr']
                            # logger.debug(f"Grammar info: {gr}") # Отладка

                            # Проверяем, что это существительное и извлекаем род
                            if gr.startswith('S,'): # S - существительное
                                gender = None
                                if 'жен' in gr:
                                    gender = 'femn'
                                elif 'сред' in gr:
                                    gender = 'neut'
                                elif 'муж' in gr:
                                    gender = 'masc'

                                # logger.debug(f"Detected gender: {gender}") # Отладка

                                if gender:
                                    if word == "один":
                                        if gender == 'femn':
                                            corrected_word = "одна"
                                        elif gender == 'neut':
                                            corrected_word = "одно"
                                    elif word == "два":
                                        if gender == 'femn':
                                            corrected_word = "две"
                    except Exception as e:
                        logger.warning(f"Ошибка анализа Mystem для '{cleaned_next_word}': {e}")

        corrected_words.append(corrected_word)
        i += 1

    return ' '.join(corrected_words)


@app.route('/synthesize/', methods=['GET'])
@app.route('/synthesize/<path:text>', methods=['GET'])
def handle_synthesize_request(text=''):
    # ... (начало функции без изменений: получение и декодирование текста) ...
    global pyrogram_client, telegram_loop, TARGET_BOT_ID, pending_requests, pending_requests_lock

    current_thread_name = threading.current_thread().name
    req_logger = logging.getLogger(current_thread_name)
    request_start_time = time.time()
    req_logger.info(f"Получен запрос на /synthesize/ от {request.remote_addr}")

    if not text:
        qs = request.query_string.decode('utf-8', errors='ignore')
        if qs:
            args = urllib.parse.parse_qs(qs)
            text_param = args.get('text', [None])[0]
            if text_param:
                text = text_param
            else:
                text = qs
    if not text:
        req_logger.error("Текст не найден ни в пути, ни в параметрах.")
        return jsonify({"status": "error", "message": "Текст не предоставлен"}), 400
    try:
        decoded_text = urllib.parse.unquote(text).strip()
        if not decoded_text:
            req_logger.error("Пустой текст после декодирования.")
            return jsonify({"status": "error", "message": "Пустой текст после декодирования"}), 400
        req_logger.info(f"Оригинальный декодированный текст: '{decoded_text}'")
    except Exception as e:
        req_logger.error(f"Ошибка декодирования URL: {e}")
        return jsonify({"status": "error", "message": "Ошибка декодирования текста"}), 400


    # --- Этап 1: Замена чисел на слова (num2words) ---
    text_after_num2words = decoded_text
    try:
        # ... (логика num2words без изменений) ...
        def replace_with_words(match):
            number_str = match.group(0)
            try:
                number = int(number_str)
                return num2words(number, lang='ru')
            except ValueError:
                return number_str
            except Exception as conv_err:
                req_logger.warning(f"Ошибка num2words для числа '{number_str}': {conv_err}. Используется оригинал.")
                return number_str

        processed_text_stage1 = re.sub(r"[-]?\d+", replace_with_words, decoded_text)

        if processed_text_stage1 != decoded_text:
            req_logger.info(f"Текст после num2words: '{processed_text_stage1}'")
            text_after_num2words = processed_text_stage1
        else:
            req_logger.info("Числа для замены (num2words) в тексте не найдены.")

    except Exception as e:
        req_logger.error(f"Ошибка на этапе num2words: {e}", exc_info=True)
        # text_after_num2words останется decoded_text


    # --- Этап 2: Коррекция рода числительных 1 и 2 (Mystem) ---
    text_to_send_to_bot = text_after_num2words
    try:
        # <<< ИЗМЕНЕНИЕ: Вызов функции коррекции рода с Mystem >>>
        processed_text_stage2 = correct_numeral_gender_mystem(text_after_num2words)

        if processed_text_stage2 != text_after_num2words:
            req_logger.info(f"Текст после коррекции рода (Mystem): '{processed_text_stage2}'")
            text_to_send_to_bot = processed_text_stage2
        else:
             req_logger.info("Коррекция рода для 'один'/'два' (Mystem) не применялась или не потребовалась.")

    except Exception as e:
        # Ловим ошибки именно этапа коррекции
        req_logger.error(f"Ошибка на этапе коррекции рода (Mystem): {e}", exc_info=True)
        req_logger.warning("Отправка текста после этапа num2words из-за ошибки коррекции рода.")
        # text_to_send_to_bot уже содержит text_after_num2words


    # --- Проверки готовности и отправка (без изменений) ---
    # ... (код проверок и отправки text_to_send_to_bot) ...
    if not pyrogram_client or not pyrogram_client.is_connected:
        req_logger.error("Клиент Pyrogram не готов.")
        return jsonify({"status": "error", "message": "Клиент Telegram не готов"}), 503
    if not TARGET_BOT_ID:
        req_logger.error("ID целевого бота не определен.")
        return jsonify({"status": "error", "message": "Не удалось определить ID бота"}), 500
    if not telegram_loop or not telegram_loop.is_running():
        req_logger.error("Цикл событий Telegram не запущен.")
        return jsonify({"status": "error", "message": "Внутренняя ошибка сервера (event loop)"}), 500

    request_key = text_to_send_to_bot
    loop = telegram_loop
    event = threading.Event()

    with pending_requests_lock:
        if request_key in pending_requests:
            req_logger.warning(f"Запрос с текстом '{request_key}' уже в обработке. Отклонение.")
            return jsonify({"status": "error", "message": "Запрос с таким текстом уже обрабатывается"}), 429
        pending_requests[request_key] = {'event': event, 'result': None, 'error': None}
        req_logger.info(f"Запрос '{request_key}' добавлен в ожидание.")

    req_logger.info(f"Отправка текста '{text_to_send_to_bot}' боту {TARGET_BOT_USERNAME} ({TARGET_BOT_ID})")
    send_future = asyncio.run_coroutine_threadsafe(send_text_to_bot(text_to_send_to_bot), loop)
    try:
        sent_successfully = send_future.result(timeout=10)
        if not sent_successfully:
            raise Exception("Не удалось отправить сообщение боту (async задача вернула не True).")
        req_logger.info("Сообщение успешно отправлено боту.")
    except Exception as e:
        req_logger.error(f"Ошибка при отправке сообщения боту: {e}")
        with pending_requests_lock:
            pending_requests.pop(request_key, None)
        return jsonify({"status": "error", "message": f"Ошибка отправки в Telegram: {e}"}), 500


    # --- Ожидание результата (без изменений) ---
    # ... (код ожидания события и обработки результата/ошибки/таймаута) ...
    audio_base64_string = None
    error_result = None
    try:
        req_logger.info(f"Ожидание ответа для '{request_key}' (таймаут: {RESPONSE_TIMEOUT} сек)")
        event_was_set = event.wait(timeout=RESPONSE_TIMEOUT)

        if event_was_set:
            req_logger.info(f"Событие для '{request_key}' получено.")
            with pending_requests_lock:
                request_data = pending_requests.get(request_key)
                if request_data:
                    audio_base64_string = request_data.get('result')
                    error_result = request_data.get('error')
                else:
                    error_result = Exception("Внутренняя ошибка: данные запроса не найдены после события.")

            if error_result:
                req_logger.error(f"Получена ошибка от обработчика для '{request_key}': {error_result}")
                raise error_result

            elif audio_base64_string:
                req_logger.info(f"Получена строка Base64 для '{request_key}' (длина: {len(audio_base64_string)} символов)")
                total_time = time.time() - request_start_time
                req_logger.info(f"Общее время обработки запроса '{request_key}': {total_time:.2f} сек.")
                return Response(audio_base64_string, mimetype="text/plain")
            else:
                req_logger.error(f"Событие для '{request_key}' установлено, но нет ни результата, ни ошибки!")
                raise Exception("Внутренняя ошибка: нет результата после события.")

        else: # event_was_set is False
            req_logger.error(f"Таймаут ожидания ответа от бота для текста: '{request_key}'")
            # Удаляем запрос при таймауте здесь, а не в finally, т.к. finally удалит его в любом случае
            # Но логируем таймаут явно
            return jsonify({"status": "error", "message": "Таймаут ожидания ответа от бота"}), 504

    except Exception as e:
        req_logger.error(f"Ошибка во время ожидания или обработки ответа для '{request_key}': {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Ошибка обработки: {e}"}), 500
    finally:
        # Гарантированно удаляем запрос из словаря
        with pending_requests_lock:
            removed_data = pending_requests.pop(request_key, None)
            if removed_data:
                req_logger.info(f"Запрос '{request_key}' удален из ожидания (в finally).")


# --- Логика Pyrogram (без изменений) ---
# ... (send_text_to_bot, get_bot_id, setup_pyrogram_handlers, handle_voice_message) ...
async def send_text_to_bot(text_to_send):
    # ... (без изменений) ...
    global pyrogram_client, TARGET_BOT_ID
    pyro_logger = logging.getLogger("PyrogramClient")
    if not pyrogram_client or not TARGET_BOT_ID:
        pyro_logger.error("Pyrogram клиент или ID бота не инициализированы для отправки.")
        return False
    try:
        await pyrogram_client.send_message(chat_id=TARGET_BOT_ID, text=text_to_send)
        return True
    except FloodWait as e:
        pyro_logger.warning(f"Flood wait: {e.value} секунд при отправке '{text_to_send[:50]}...'.")
        await asyncio.sleep(e.value + 1)
        try:
             await pyrogram_client.send_message(chat_id=TARGET_BOT_ID, text=text_to_send)
             return True
        except Exception as inner_e:
             pyro_logger.error(f"Повторная ошибка при отправке '{text_to_send[:50]}...' боту {TARGET_BOT_USERNAME} после FloodWait: {inner_e}")
             return False
    except Exception as e:
        pyro_logger.error(f"Ошибка при отправке сообщения '{text_to_send[:50]}...' боту {TARGET_BOT_USERNAME}: {e}")
        return False

async def get_bot_id():
    # ... (без изменений) ...
    global pyrogram_client, TARGET_BOT_ID, TARGET_BOT_USERNAME
    main_logger = logging.getLogger(__name__)
    if not pyrogram_client or not pyrogram_client.is_connected:
        main_logger.warning("Pyrogram клиент не готов для получения ID бота.")
        return
    main_logger.info(f"Попытка получить ID для @{TARGET_BOT_USERNAME}")
    try:
        user = await pyrogram_client.get_users(TARGET_BOT_USERNAME)
        if user:
            TARGET_BOT_ID = user.id
            main_logger.info(f"ID для бота {TARGET_BOT_USERNAME} определен: {TARGET_BOT_ID}")
        else:
            main_logger.error(f"Не удалось найти пользователя/бота с username {TARGET_BOT_USERNAME}")
            TARGET_BOT_ID = None
    except Exception as e:
        main_logger.error(f"Не удалось получить ID для бота {TARGET_BOT_USERNAME}: {e}")
        TARGET_BOT_ID = None


def setup_pyrogram_handlers(client):
    # ... (без изменений) ...
    pyro_logger = logging.getLogger("PyrogramHandler")
    @client.on_message(filters.private & filters.user(TARGET_BOT_USERNAME) & filters.voice)
    async def handle_voice_message(client, message):
        # ... (логика обработки аудио без изменений) ...
        global pending_requests, pending_requests_lock, DEBUG_WAV_DIR
        pyro_logger.info(f"Получено голосовое сообщение от бота {TARGET_BOT_USERNAME}")
        request_key = None
        if message.reply_to_message and message.reply_to_message.text:
            request_key = message.reply_to_message.text.strip()
            pyro_logger.info(f"Ответ на сообщение с текстом: '{request_key}'")
        else:
            pyro_logger.warning("Не удалось определить исходное сообщение (reply_to_message отсутствует или без текста). Игнорирование.")
            return

        request_data = None
        event_to_set = None
        with pending_requests_lock:
            request_data = pending_requests.get(request_key)
            if request_data:
                event_to_set = request_data.get('event')
                if request_data.get('result') or request_data.get('error'):
                     pyro_logger.warning(f"Запрос '{request_key}' уже имеет результат/ошибку.")
                     return
        if not request_data or not event_to_set:
             pyro_logger.warning(f"Получено аудио для '{request_key}', но соответствующий активный запрос не найден в pending_requests.")
             return

        audio_base64_result_string = None
        error_occurred = None
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # ... (скачивание и конвертация) ...
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                safe_filename_part = "".join(c if c.isalnum() else "_" for c in request_key[:30])
                ogg_filename = f"voice_{timestamp}.ogg"
                wav_filename = f"voice_{timestamp}.wav"
                ogg_path = os.path.join(temp_dir, ogg_filename)
                wav_path = os.path.join(temp_dir, wav_filename)

                pyro_logger.info(f"Скачивание OGG для '{request_key}' в: {ogg_path}")
                await message.download(file_name=ogg_path)
                pyro_logger.info("OGG скачано успешно.")

                pyro_logger.info(f"Конвертация {ogg_path} в стандартный WAV (128k, 16b, mono) в {wav_path}")
                try:
                    audio = AudioSegment.from_ogg(ogg_path)
                    standard_audio = audio.set_frame_rate(128000).set_sample_width(2).set_channels(1)
                    standard_audio.export(wav_path, format="wav")
                    pyro_logger.info("Конвертация в стандартный WAV завершена.")
                    # ... (логгирование инфо о WAV) ...
                except Exception as convert_err:
                    pyro_logger.error(f"Ошибка конвертации OGG в WAV: {convert_err}", exc_info=True)
                    raise convert_err

                pyro_logger.info(f"Чтение WAV файла и кодирование в Base64: {wav_path}")
                with open(wav_path, "rb") as audio_file:
                    audio_data = audio_file.read()
                audio_base64_result_string = base64.b64encode(audio_data).decode("utf-8")
                pyro_logger.info(f"Аудио для '{request_key}' успешно закодировано в Base64 (длина строки: {len(audio_base64_result_string)}).")

        except Exception as e:
            pyro_logger.error(f"Ошибка при обработке голосового сообщения для '{request_key}': {e}", exc_info=True)
            error_occurred = e

        final_result_set = False
        with pending_requests_lock:
            current_request_data = pending_requests.get(request_key)
            if current_request_data and current_request_data['event'] == event_to_set:
                 if not current_request_data.get('result') and not current_request_data.get('error'):
                    if error_occurred:
                        current_request_data['error'] = error_occurred
                        pyro_logger.info(f"Ошибка записана для '{request_key}'.")
                    elif audio_base64_result_string:
                        current_request_data['result'] = audio_base64_result_string
                        pyro_logger.info(f"Строка Base64 записана для '{request_key}'.")
                    else:
                        current_request_data['error'] = Exception("Неизвестная ошибка обработки аудио (нет результата)")
                        pyro_logger.warning(f"Нет ни строки Base64, ни явной ошибки для '{request_key}', записываем общую ошибку.")
                    final_result_set = True
                 else:
                    pyro_logger.warning(f"Попытка записать результат/ошибку для '{request_key}', но он уже установлен.")
            else:
                 pyro_logger.warning(f"Запись для '{request_key}' исчезла или изменилась перед записью результата/ошибки.")

        if final_result_set and event_to_set:
            pyro_logger.info(f"Установка события для '{request_key}', чтобы разбудить Flask.")
            event_to_set.set()
        elif event_to_set:
             pyro_logger.warning(f"Результат/ошибка для '{request_key}' не были записаны (или уже были), событие НЕ УСТАНАВЛИВАЕТСЯ.")


# --- Функции запуска (без изменений) ---
# ... (run_flask, main_telegram_logic) ...
def run_flask():
    main_logger = logging.getLogger(__name__)
    main_logger.info(f"Запуск Flask сервера на http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, threaded=True, use_reloader=False)

async def main_telegram_logic():
    main_logger = logging.getLogger(__name__)
    global pyrogram_client, telegram_loop, TARGET_BOT_ID
    # ... (проверка API ID/HASH, создание клиента, start, get_bot_id) ...
    if not API_ID or not API_HASH:
        main_logger.error("API_ID и API_HASH должны быть установлены!")
        return
    telegram_loop = asyncio.get_running_loop()
    main_logger.info(f"Инициализация клиента Pyrogram с сессией '{SESSION_NAME}'...")
    client = Client(SESSION_NAME, api_id=int(API_ID), api_hash=API_HASH, workers=4)
    pyrogram_client = client
    setup_pyrogram_handlers(client)
    try:
        await client.start()
        main_logger.info("Клиент Pyrogram успешно запущен.")
        user_info = await client.get_me()
        main_logger.info(f"Вход выполнен как: {user_info.first_name} (@{user_info.username}) ID: {user_info.id}")
        await get_bot_id()
        if not TARGET_BOT_ID:
             main_logger.warning(f"Не удалось определить ID бота {TARGET_BOT_USERNAME} при запуске.")
        main_logger.info("Pyrogram готов к приему и отправке сообщений. Ожидание...")
        await asyncio.Future()
    except Exception as e:
        main_logger.exception(f"Критическая ошибка при запуске или работе Pyrogram: {e}")
    finally:
        # ... (остановка клиента) ...
        if client and client.is_connected:
            main_logger.info("Остановка клиента Pyrogram...")
            await client.stop()
            main_logger.info("Клиент Pyrogram остановлен.")
        else:
             main_logger.info("Клиент Pyrogram не был запущен или уже остановлен.")


# --- Точка входа (без изменений) ---
if __name__ == "__main__":
    # ... (запуск Flask в потоке, запуск asyncio.run(main_telegram_logic)) ...
    flask_thread = threading.Thread(target=run_flask, name="FlaskThread", daemon=True)
    flask_thread.start()
    try:
        main_logger = logging.getLogger(__name__)
        main_logger.info("Запуск основного цикла Telegram (asyncio)...")
        asyncio.run(main_telegram_logic())
    except KeyboardInterrupt:
        main_logger.info("Получен сигнал KeyboardInterrupt (Ctrl+C). Завершение работы...")
    except Exception as e:
        main_logger.exception(f"Непредвиденная ошибка в главном потоке: {e}")
    finally:
        main_logger.info("Скрипт завершает работу.")

# --- END OF FILE app.py ---
