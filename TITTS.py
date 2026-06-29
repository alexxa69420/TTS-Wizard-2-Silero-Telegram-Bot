# --- START OF FILE app.py ---

import os
import threading
import asyncio
import urllib.parse
import logging
import base64
import tempfile
from datetime import datetime
import time
import re
import ssl # <<< NEW: Для безопасного соединения с Twitch >>>

from dotenv import load_dotenv
from flask import Flask, request, Response, jsonify
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pydub import AudioSegment
from num2words import num2words
from pymystem3 import Mystem 

# --- КОНФИГУРАЦИЯ ---
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# --- TWITCH CONFIGURATION START ---
TWITCH_USERNAME = os.getenv("TWITCH_USERNAME")
TWITCH_TOKEN = os.getenv("TWITCH_TOKEN")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")
# --- TWITCH CONFIGURATION END ---

# Проверка, заданы ли настройки Telegram
if not API_ID or not API_HASH:
    print("--- Настройка Telegram ---")
    print("Файл .env не найден или в нём отсутствуют API_ID и API_HASH.")
    print("Получите их на https://my.telegram.org/apps и введите ниже:")

    API_ID = input("Введите API_ID: ").strip()
    API_HASH = input("Введите API_HASH: ").strip()
    
    # Сохраняем Telegram настройки
    with open(".env", "a") as f:
        f.write(f"\nAPI_ID={API_ID}\n")
        f.write(f"API_HASH={API_HASH}\n")

# Проверка, заданы ли настройки Twitch
if not TWITCH_USERNAME or not TWITCH_TOKEN or not TWITCH_CHANNEL:
    print("\n--- Настройка Twitch IRC ---")
    print("Для отправки сообщений в чат, нужно авторизоваться.")
    print("1. Введите имя вашего аккаунта Twitch (логин).")
    TWITCH_USERNAME = input("Twitch Username: ").strip().lower()
    
    print("2. Получите ACCESS TOKEN здесь: https://twitchtokengenerator.com")
    print("   Скопируйте его полностью.")
    TWITCH_TOKEN = input("Twitch OAuth Token: ").strip()
    if not TWITCH_TOKEN.startswith("oauth:"):
        TWITCH_TOKEN = f"oauth:{TWITCH_TOKEN}"

    print("3. Введите ссылку на канал (например: https://www.twitch.tv/ninja).")
    channel_input = input("Ссылка на канал или название: ").strip().lower()
    # Парсим название канала из ссылки, если введена ссылка
    if "twitch.tv/" in channel_input:
        TWITCH_CHANNEL = channel_input.split("twitch.tv/")[-1].split("/")[0]
    else:
        TWITCH_CHANNEL = channel_input
    
    # Дописываем Twitch настройки в .env
    with open(".env", "a") as f:
        f.write(f"TWITCH_USERNAME={TWITCH_USERNAME}\n")
        f.write(f"TWITCH_TOKEN={TWITCH_TOKEN}\n")
        f.write(f"TWITCH_CHANNEL={TWITCH_CHANNEL}\n")
    
    print("Настройки Twitch сохранены.\n")

# Преобразуем API_ID в int
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
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(threadName)s (%(funcName)s) - %(message)s')
logger = logging.getLogger(__name__)

# --- Глобальные переменные ---
pyrogram_client = None
telegram_loop = None
TARGET_BOT_ID = None
pending_requests = {}
pending_requests_lock = threading.Lock()

# --- Глобальные переменные Twitch ---
twitch_writer = None
twitch_reader = None

# Инициализация Mystem
try:
    mystem = Mystem(grammar_info=True, entire_input=False)
    logger.info("Mystem инициализирован успешно.")
    try:
        _ = mystem.analyze("тест")
    except Exception as init_err:
         logger.error(f"Ошибка при пробном запуске Mystem: {init_err}")
except Exception as e:
    logger.error(f"Не удалось инициализировать Mystem: {e}. Коррекция рода числительных будет отключена.")
    mystem = None 

# --- Инициализация Flask ---
app = Flask(__name__)

# --- Логика Flask ---

def correct_numeral_gender_mystem(text):
    if not mystem:
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
                cleaned_next_word = re.sub(r'[^\w\s]+$', '', next_word).strip()
                if cleaned_next_word:
                    try:
                        analysis = mystem.analyze(cleaned_next_word)
                        if analysis and 'analysis' in analysis[0] and analysis[0]['analysis']:
                            gr = analysis[0]['analysis'][0]['gr']
                            if gr.startswith('S,'):
                                gender = None
                                if 'жен' in gr: gender = 'femn'
                                elif 'сред' in gr: gender = 'neut'
                                elif 'муж' in gr: gender = 'masc'
                                if gender:
                                    if word == "один":
                                        if gender == 'femn': corrected_word = "одна"
                                        elif gender == 'neut': corrected_word = "одно"
                                    elif word == "два":
                                        if gender == 'femn': corrected_word = "две"
                    except Exception as e:
                        logger.warning(f"Ошибка анализа Mystem для '{cleaned_next_word}': {e}")
        corrected_words.append(corrected_word)
        i += 1
    return ' '.join(corrected_words)


@app.route('/synthesize/', methods=['GET'])
@app.route('/synthesize/<path:text>', methods=['GET'])
def handle_synthesize_request(text=''):
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
            text = text_param if text_param else qs
    if not text:
        return jsonify({"status": "error", "message": "Текст не предоставлен"}), 400
    try:
        decoded_text = urllib.parse.unquote(text).strip()
        if not decoded_text:
            return jsonify({"status": "error", "message": "Пустой текст после декодирования"}), 400
        req_logger.info(f"Оригинальный декодированный текст: '{decoded_text}'")
    except Exception as e:
        return jsonify({"status": "error", "message": "Ошибка декодирования текста"}), 400

    # --- Этап 1: Замена чисел на слова (num2words) ---
    text_after_num2words = decoded_text
    try:
        def replace_with_words(match):
            number_str = match.group(0)
            try:
                number = int(number_str)
                return num2words(number, lang='ru')
            except ValueError:
                return number_str
            except Exception:
                return number_str

        processed_text_stage1 = re.sub(r"[-]?\d+", replace_with_words, decoded_text)
        if processed_text_stage1 != decoded_text:
            text_after_num2words = processed_text_stage1
    except Exception as e:
        req_logger.error(f"Ошибка на этапе num2words: {e}", exc_info=True)

    # --- Этап 2: Коррекция рода (Mystem) ---
    text_to_send = text_after_num2words
    try:
        processed_text_stage2 = correct_numeral_gender_mystem(text_after_num2words)
        if processed_text_stage2 != text_after_num2words:
            text_to_send = processed_text_stage2
    except Exception as e:
        req_logger.error(f"Ошибка на этапе коррекции рода (Mystem): {e}", exc_info=True)

    # --- ОТПРАВКА В TWITCH (Параллельно) ---
    if telegram_loop and telegram_loop.is_running():
        # Отправляем в Twitch используя цикл событий Telegram (так как Twitch клиент асинхронный)
        req_logger.info(f"Планирование отправки в Twitch: '{text_to_send}'")
        asyncio.run_coroutine_threadsafe(send_twitch_message(text_to_send), telegram_loop)
    else:
        req_logger.error("Цикл событий не запущен, пропуск отправки в Twitch.")

    # --- Логика Telegram (без изменений) ---
    if not pyrogram_client or not pyrogram_client.is_connected:
        return jsonify({"status": "error", "message": "Клиент Telegram не готов"}), 503
    if not TARGET_BOT_ID:
        return jsonify({"status": "error", "message": "Не удалось определить ID бота"}), 500

    request_key = text_to_send
    loop = telegram_loop
    event = threading.Event()

    with pending_requests_lock:
        if request_key in pending_requests:
            return jsonify({"status": "error", "message": "Запрос с таким текстом уже обрабатывается"}), 429
        pending_requests[request_key] = {'event': event, 'result': None, 'error': None}

    req_logger.info(f"Отправка текста '{text_to_send}' боту Telegram...")
    send_future = asyncio.run_coroutine_threadsafe(send_text_to_bot(text_to_send), loop)
    try:
        sent_successfully = send_future.result(timeout=20)
        if not sent_successfully:
            raise Exception("Telegram async task returned False")
    except Exception as e:
        req_logger.error(f"Ошибка при отправке сообщения боту: {e}")
        with pending_requests_lock:
            pending_requests.pop(request_key, None)
        return jsonify({"status": "error", "message": f"Ошибка отправки в Telegram: {e}"}), 500

    audio_base64_string = None
    error_result = None
    try:
        event_was_set = event.wait(timeout=RESPONSE_TIMEOUT)
        if event_was_set:
            with pending_requests_lock:
                request_data = pending_requests.get(request_key)
                if request_data:
                    audio_base64_string = request_data.get('result')
                    error_result = request_data.get('error')
                else:
                    error_result = Exception("Внутренняя ошибка")

            if error_result:
                raise error_result
            elif audio_base64_string:
                return Response(audio_base64_string, mimetype="text/plain")
            else:
                raise Exception("Пустой результат")
        else:
            return jsonify({"status": "error", "message": "Таймаут ожидания ответа от бота"}), 504

    except Exception as e:
        req_logger.error(f"Ошибка: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Ошибка обработки: {e}"}), 500
    finally:
        with pending_requests_lock:
            pending_requests.pop(request_key, None)

# --- TWITCH LOGIC START ---

async def connect_to_twitch():
    """Устанавливает соединение с Twitch IRC."""
    global twitch_writer, twitch_reader
    logger = logging.getLogger("TwitchIRC")
    
    url = 'irc.chat.twitch.tv'
    port = 6697 # SSL порт
    
    try:
        logger.info(f"Подключение к Twitch ({TWITCH_CHANNEL})...")
        # Создаем SSL контекст
        ssl_ctx = ssl.create_default_context()
        
        twitch_reader, twitch_writer = await asyncio.open_connection(url, port, ssl=ssl_ctx)
        
        # Авторизация
        auth_msg = (
            f"PASS {TWITCH_TOKEN}\r\n"
            f"NICK {TWITCH_USERNAME}\r\n"
            f"JOIN #{TWITCH_CHANNEL}\r\n"
        )
        twitch_writer.write(auth_msg.encode('utf-8'))
        await twitch_writer.drain()
        
        logger.info("Отправлены данные авторизации Twitch.")
        
        # Запускаем фоновую задачу для поддержания соединения (PING/PONG)
        asyncio.create_task(twitch_listener())
        
    except Exception as e:
        logger.error(f"Не удалось подключиться к Twitch: {e}")

async def twitch_listener():
    """Слушает входящие сообщения от Twitch (нужно для PING/PONG)."""
    global twitch_reader, twitch_writer
    logger = logging.getLogger("TwitchListener")
    
    try:
        while True:
            data = await twitch_reader.read(2048)
            if not data:
                logger.warning("Twitch соединение закрыто сервером.")
                break
            
            message = data.decode('utf-8', errors='ignore')
            
            # Обработка PING (Twitch отключает, если не отвечать PONG)
            if message.startswith("PING"):
                # logger.debug("Получен PING от Twitch, отправляю PONG")
                response = "PONG :tmi.twitch.tv\r\n"
                twitch_writer.write(response.encode('utf-8'))
                await twitch_writer.drain()
            
            # Проверка успешного входа
            if "376" in message or "GLHF" in message:
                logger.info(f"Успешный вход в чат Twitch #{TWITCH_CHANNEL}!")
            
            # Логируем ошибки авторизации
            if "Login authentication failed" in message:
                logger.error("Ошибка авторизации Twitch! Проверьте токен.")
                
    except Exception as e:
        logger.error(f"Ошибка в цикле слушателя Twitch: {e}")
    finally:
        logger.info("Слушатель Twitch остановлен.")

async def send_twitch_message(text):
    """Отправляет сообщение в чат Twitch."""
    global twitch_writer
    logger = logging.getLogger("TwitchSender")
    
    if not twitch_writer:
        logger.error("Нет соединения с Twitch. Сообщение не отправлено.")
        # Пробуем переподключиться? (упрощенно - нет, просто лог)
        return

    try:
        # Формат IRC сообщения: PRIVMSG #channel :message
        # Важно: удаляем переносы строк, IRC их не любит
        clean_text = text.replace('\n', ' ').replace('\r', '')
        msg = f"PRIVMSG #{TWITCH_CHANNEL} :{clean_text}\r\n"
        
        twitch_writer.write(msg.encode('utf-8'))
        await twitch_writer.drain()
        logger.info(f"В Twitch отправлено: {clean_text}")
    except Exception as e:
        logger.error(f"Ошибка отправки в Twitch: {e}")

# --- TWITCH LOGIC END ---


# --- Логика Pyrogram ---
async def send_text_to_bot(text_to_send):
    global pyrogram_client, TARGET_BOT_ID
    pyro_logger = logging.getLogger("PyrogramClient")
    if not pyrogram_client or not TARGET_BOT_ID:
        return False
    for attempt in range(3):
        if pyrogram_client.is_connected:
            break
        pyro_logger.warning(f"Клиент переподключается, ждём... (попытка {attempt + 1}/3)")
        await asyncio.sleep(5)
    else:
        pyro_logger.error("Клиент не подключён после ожидания.")
        return False
    try:
        await pyrogram_client.send_message(chat_id=TARGET_BOT_ID, text=text_to_send)
        return True
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        try:
            await pyrogram_client.send_message(chat_id=TARGET_BOT_ID, text=text_to_send)
            return True
        except Exception:
            return False
    except Exception as e:
        pyro_logger.error(f"Ошибка при отправке сообщения боту: {e}")
        return False

async def get_bot_id():
    global pyrogram_client, TARGET_BOT_ID, TARGET_BOT_USERNAME
    main_logger = logging.getLogger(__name__)
    if not pyrogram_client or not pyrogram_client.is_connected:
        return
    try:
        user = await pyrogram_client.get_users(TARGET_BOT_USERNAME)
        if user:
            TARGET_BOT_ID = user.id
            main_logger.info(f"ID для бота {TARGET_BOT_USERNAME} определен: {TARGET_BOT_ID}")
    except Exception as e:
        main_logger.error(f"Не удалось получить ID для бота {TARGET_BOT_USERNAME}: {e}")

def setup_pyrogram_handlers(client):
    pyro_logger = logging.getLogger("PyrogramHandler")
    @client.on_message(filters.private & filters.user(TARGET_BOT_USERNAME) & filters.voice)
    async def handle_voice_message(client, message):
        global pending_requests, pending_requests_lock, DEBUG_WAV_DIR
        
        request_key = None
        if message.reply_to_message and message.reply_to_message.text:
            request_key = message.reply_to_message.text.strip()
        else:
            return

        request_data = None
        event_to_set = None
        with pending_requests_lock:
            request_data = pending_requests.get(request_key)
            if request_data:
                event_to_set = request_data.get('event')
                if request_data.get('result') or request_data.get('error'):
                     return
        
        if not request_data or not event_to_set:
             return

        audio_base64_result_string = None
        error_occurred = None
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                ogg_path = os.path.join(temp_dir, f"voice_{timestamp}.ogg")
                wav_path = os.path.join(temp_dir, f"voice_{timestamp}.wav")

                await message.download(file_name=ogg_path)
                
                audio = AudioSegment.from_ogg(ogg_path)
                standard_audio = audio.set_frame_rate(128000).set_sample_width(2).set_channels(1)
                standard_audio.export(wav_path, format="wav")
                
                with open(wav_path, "rb") as audio_file:
                    audio_data = audio_file.read()
                audio_base64_result_string = base64.b64encode(audio_data).decode("utf-8")
        except Exception as e:
            error_occurred = e

        final_result_set = False
        with pending_requests_lock:
            current_request_data = pending_requests.get(request_key)
            if current_request_data and current_request_data['event'] == event_to_set:
                 if not current_request_data.get('result') and not current_request_data.get('error'):
                    if error_occurred:
                        current_request_data['error'] = error_occurred
                    elif audio_base64_result_string:
                        current_request_data['result'] = audio_base64_result_string
                        final_result_set = True
                    else:
                        current_request_data['error'] = Exception("Неизвестная ошибка")

        if final_result_set and event_to_set:
            event_to_set.set()

# --- Функции запуска ---

def run_flask():
    main_logger = logging.getLogger(__name__)
    main_logger.info(f"Запуск Flask сервера на http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, threaded=True, use_reloader=False)

async def main_telegram_logic():
    main_logger = logging.getLogger(__name__)
    global pyrogram_client, telegram_loop, TARGET_BOT_ID
    
    if not API_ID or not API_HASH:
        return
    
    telegram_loop = asyncio.get_running_loop()
    
    # <<< NEW: Запуск подключения к Twitch >>>
    main_logger.info("Запуск подключения к Twitch IRC...")
    await connect_to_twitch()

    main_logger.info(f"Инициализация клиента Pyrogram...")
    client = Client(SESSION_NAME, api_id=int(API_ID), api_hash=API_HASH, workers=4)
    pyrogram_client = client
    setup_pyrogram_handlers(client)
    try:
        await client.start()
        main_logger.info("Клиент Pyrogram успешно запущен.")
        await get_bot_id()
        main_logger.info("Сервер готов к работе.")
        await asyncio.Future()
    except Exception as e:
        main_logger.exception(f"Критическая ошибка: {e}")
    finally:
        if client and client.is_connected:
            await client.stop()

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, name="FlaskThread", daemon=True)
    flask_thread.start()
    try:
        main_logger = logging.getLogger(__name__)
        asyncio.run(main_telegram_logic())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Ошибка: {e}")