import os
import logging
import tempfile
import subprocess
from typing import Optional
import telebot
from telebot.types import Message, Voice, Audio, VideoNote
from flask import Flask

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Створюємо Flask додаток для порту
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Speech Recognition Bot is running!"

class SpeechRecognitionBot:
    def __init__(self, token: str):
        self.bot = telebot.TeleBot(token)
        self.setup_handlers()
        logger.info("🤖 Бот ініціалізовано!")

    def setup_handlers(self):
        """Налаштування обробників повідомлень"""
        
        @self.bot.message_handler(commands=['start', 'help'])
        def send_welcome(message: Message):
            welcome_text = """
🎤 Бот для розпізнавання голосових повідомлень

📌 Надсилайте:
• Голосові повідомлення
• Аудіофайли  
• Відеокружки

🌍 Підтримувані мови:
• Українська
• Російська
• Англійська

🚀 Бот працює на Render!
            """
            self.bot.reply_to(message, welcome_text)

        @self.bot.message_handler(commands=['status', 'ping'])
        def send_status(message: Message):
            self.bot.reply_to(message, "✅ Бот активний та працює!")

        @self.bot.message_handler(content_types=['voice'])
        def handle_voice(message: Message):
            self.process_audio_message(message, message.voice, "голосове повідомлення")

        @self.bot.message_handler(content_types=['audio'])
        def handle_audio(message: Message):
            self.process_audio_message(message, message.audio, "аудіофайл")

        @self.bot.message_handler(content_types=['video_note'])
        def handle_video_note(message: Message):
            self.bot.reply_to(message, "📹 Обробка відеокружок тимчасово в розробці...")

    def download_file(self, file_id: str) -> Optional[str]:
        """Завантаження файлу з Telegram"""
        try:
            file_info = self.bot.get_file(file_id)
            downloaded_file = self.bot.download_file(file_info.file_path)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
                temp_file.write(downloaded_file)
                return temp_file.name
        except Exception as e:
            logger.error(f"Помилка завантаження файлу: {e}")
            return None

    def convert_to_wav(self, input_path: str) -> Optional[str]:
        """Конвертація аудіо у WAV формат"""
        try:
            output_path = input_path + '.wav'
            cmd = [
                'ffmpeg', '-i', input_path,
                '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000',
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return output_path
            else:
                logger.error(f"FFmpeg помилка: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Помилка конвертації: {e}")
            return None

    def recognize_speech_demo(self) -> str:
        """Демо-функція розпізнавання мови"""
        return """🎤 Демонстрація роботи бота

✅ Аудіо успішно оброблено!
✅ Конвертація пройшла успішно
✅ Бот працює коректно

🌍 У реальній версії тут буде розпізнаний текст українською, російською та англійською мовами.

💡 Для повної функціональності потрібно додати API розпізнавання мови."""

    def process_audio_message(self, message: Message, file_obj, file_type: str):
        """Обробка аудіо повідомлень"""
        processing_msg = self.bot.reply_to(message, "🔍 Завантаження аудіо...")
        
        try:
            # Завантаження файлу
            temp_file = self.download_file(file_obj.file_id)
            if not temp_file:
                self.bot.edit_message_text(
                    "❌ Помилка завантаження файлу",
                    message.chat.id,
                    processing_msg.message_id
                )
                return

            self.bot.edit_message_text(
                "🔄 Конвертація аудіо...",
                message.chat.id,
                processing_msg.message_id
            )

            # Конвертація у WAV
            wav_file = self.convert_to_wav(temp_file)
            if not wav_file:
                self.bot.edit_message_text(
                    "❌ Помилка конвертації аудіо",
                    message.chat.id,
                    processing_msg.message_id
                )
                self.cleanup_files(temp_file)
                return

            self.bot.edit_message_text(
                "🎤 Розпізнавання мови...",
                message.chat.id,
                processing_msg.message_id
            )

            # Розпізнавання мови (демо)
            result_text = self.recognize_speech_demo()

            # Відправка результату
            self.bot.edit_message_text(
                result_text,
                message.chat.id,
                processing_msg.message_id
            )
            
            logger.info(f"Успішно оброблено {file_type}")

        except Exception as e:
            logger.error(f"Помилка обробки аудіо: {e}")
            self.bot.edit_message_text(
                "❌ Сталася помилка під час обробки",
                message.chat.id,
                processing_msg.message_id
            )
        finally:
            # Очищення тимчасових файлів
            self.cleanup_files(temp_file, wav_file)

    def cleanup_files(self, *files):
        """Очищення тимчасових файлів"""
        for file_path in files:
            try:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Помилка видалення файлу: {e}")

    def run_polling(self):
        """Запуск бота в режимі polling"""
        logger.info("🚀 Запуск Telegram бота (Web Service)...")
        try:
            self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Помилка бота: {e}")
            import time
            time.sleep(10)
            self.run_polling()

def start_bot():
    """Запуск бота"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("❌ Не вказано TELEGRAM_BOT_TOKEN")
        return None

    logger.info("✅ Токен знайдено, запускаємо бота...")
    bot = SpeechRecognitionBot(token)
    return bot

if __name__ == '__main__':
    # Запускаємо бота
    bot_instance = start_bot()
    if bot_instance:
        # Запускаємо Flask на порті 10000
        port = int(os.environ.get('PORT', 10000))
        logger.info(f"🌐 Запуск веб-сервера на порті {port}")
        
        # Запускаємо бота в окремому потоці
        import threading
        bot_thread = threading.Thread(target=bot_instance.run_polling)
        bot_thread.daemon = True
        bot_thread.start()
        
        # Запускаємо Flask сервер
        app.run(host='0.0.0.0', port=port, debug=False)