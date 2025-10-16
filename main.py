import os
import logging
import tempfile
import subprocess
import requests
import random
from typing import Optional, Dict
import telebot
from telebot.types import Message, Voice, Audio, VideoNote
from flask import Flask

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Speech Recognition Bot is running!"

class SpeechRecognitionBot:
    def __init__(self, token: str):
        self.bot = telebot.TeleBot(token)
        self.setup_handlers()
        
        self.languages = {
            'uk': {'name': 'Українська', 'code': 'uk-UA'},
            'ru': {'name': 'Російська', 'code': 'ru-RU'}, 
            'en': {'name': 'Англійська', 'code': 'en-US'}
        }
        
        # Токен для Whisper (опційно)
        self.whisper_token = os.getenv('HUGGINGFACE_TOKEN', '')
        
        logger.info("🤖 Бот з реальним розпізнаванням!")

    def setup_handlers(self):
        @self.bot.message_handler(commands=['start', 'help'])
        def send_welcome(message: Message):
            welcome_text = """
🎤 Бот для РЕАЛЬНОГО розпізнавання голосу

📌 Надсилайте голосові повідомлення
🌍 Мови: UA, RU, EN
🚀 Використовує Whisper AI та Google Speech
            """
            self.bot.reply_to(message, welcome_text)

        @self.bot.message_handler(content_types=['voice'])
        def handle_voice(message: Message):
            self.process_audio_message(message, message.voice)

    def download_file(self, file_id: str) -> Optional[str]:
        try:
            file_info = self.bot.get_file(file_id)
            downloaded_file = self.bot.download_file(file_info.file_path)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
                temp_file.write(downloaded_file)
                return temp_file.name
        except Exception as e:
            logger.error(f"Помилка завантаження: {e}")
            return None

    def convert_to_wav(self, input_path: str) -> Optional[str]:
        try:
            output_path = input_path + '.wav'
            cmd = [
                'ffmpeg', '-i', input_path,
                '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000',
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return output_path
        except Exception as e:
            logger.error(f"Помилка конвертації: {e}")
        return None

    def recognize_with_whisper(self, audio_path: str) -> Optional[str]:
        """Реальне розпізнавання через Whisper API"""
        try:
            API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"
            
            headers = {}
            if self.whisper_token:
                headers["Authorization"] = f"Bearer {self.whisper_token}"
            
            with open(audio_path, "rb") as f:
                data = f.read()
            
            response = requests.post(API_URL, headers=headers, data=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('text', '').strip()
                if text:
                    logger.info(f"Whisper розпізнав: {text[:100]}...")
                    return text
            else:
                logger.warning(f"Whisper API: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Whisper помилка: {e}")
        
        return None

    def recognize_with_google_speech(self, audio_path: str, language_code: str) -> Optional[str]:
        """Розпізнавання через Google Speech"""
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            
            with sr.AudioFile(audio_path) as source:
                # Покращуємо якість для кращого розпізнавання
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = recognizer.record(source)
                
                text = recognizer.recognize_google(audio_data, language=language_code)
                if text:
                    logger.info(f"Google розпізнав: {text[:100]}...")
                    return text
                    
        except Exception as e:
            logger.warning(f"Google Speech помилка: {e}")
        
        return None

    def recognize_speech(self, audio_path: str) -> Dict[str, str]:
        """Основна функція розпізнавання"""
        results = {}
        
        logger.info("🔍 Початок реального розпізнавання...")
        
        # 1. Спершу пробуємо Whisper (найкраща якість)
        text = self.recognize_with_whisper(audio_path)
        
        if text:
            results['Whisper AI'] = text
        else:
            # 2. Якщо Whisper не спрацював, пробуємо Google Speech для кожної мови
            for lang_code, lang_info in self.languages.items():
                text = self.recognize_with_google_speech(audio_path, lang_info['code'])
                if text:
                    results[lang_info['name']] = text
                    break
        
        # 3. Якщо нічого не спрацювало
        if not results:
            logger.error("❌ Жоден сервіс не зміг розпізнати мову")
            results['Помилка'] = "Не вдалося розпізнати мову. Перевірте:\n• Якість аудіо\n• Чи підтримується мова\n• Інтернет-з'єднання"
        
        return results

    def combine_results(self, results: Dict[str, str]) -> str:
        if not results or 'Помилка' in results:
            return f"❌ {results.get('Помилка', 'Помилка розпізнавання')}"
        
        combined_text = "🎤 **ТЕКСТ РОЗПІЗНАНО З ГОЛОСУ:**\n\n"
        
        for service, text in results.items():
            combined_text += f"**{service}:**\n"
            combined_text += f"{text}\n\n"
        
        return combined_text

    def process_audio_message(self, message: Message, file_obj):
        processing_msg = self.bot.reply_to(message, "🔍 Завантаження аудіо...")
        
        temp_file, wav_file = None, None
        
        try:
            # Завантаження
            temp_file = self.download_file(file_obj.file_id)
            if not temp_file:
                self.bot.edit_message_text("❌ Помилка завантаження", message.chat.id, processing_msg.message_id)
                return

            # Конвертація
            self.bot.edit_message_text("🔄 Конвертація аудіо...", message.chat.id, processing_msg.message_id)
            wav_file = self.convert_to_wav(temp_file)
            if not wav_file:
                self.bot.edit_message_text("❌ Помилка конвертації", message.chat.id, processing_msg.message_id)
                return

            # Розпізнавання
            self.bot.edit_message_text("🎤 Розпізнавання мови...", message.chat.id, processing_msg.message_id)
            results = self.recognize_speech(wav_file)
            combined_text = self.combine_results(results)

            # Результат
            self.bot.edit_message_text(combined_text, message.chat.id, processing_msg.message_id)
            logger.info("✅ Успішне розпізнавання")

        except Exception as e:
            logger.error(f"❌ Помилка: {e}")
            self.bot.edit_message_text("❌ Помилка обробки", message.chat.id, processing_msg.message_id)
        finally:
            self.cleanup_files(temp_file, wav_file)

    def cleanup_files(self, *files):
        for file_path in files:
            try:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Помилка видалення: {e}")

    def run_polling(self):
        logger.info("🚀 Запуск бота...")
        try:
            self.bot.infinity_polling(timeout=90, long_polling_timeout=90)
        except Exception as e:
            logger.error(f"Помилка: {e}")
            import time
            time.sleep(10)
            self.run_polling()

def start_bot():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ Немає токену")
        return None

    logger.info("✅ Запуск бота...")
    return SpeechRecognitionBot(token)

if __name__ == '__main__':
    bot_instance = start_bot()
    if bot_instance:
        port = int(os.environ.get('PORT', 10000))
        logger.info(f"🌐 Порт: {port}")
        
        import threading
        bot_thread = threading.Thread(target=bot_instance.run_polling)
        bot_thread.daemon = True
        bot_thread.start()
        
        app.run(host='0.0.0.0', port=port, debug=False)