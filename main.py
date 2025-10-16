import os
import logging
import tempfile
import subprocess
import requests
import json
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

# Створюємо Flask додаток для порту
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Speech Recognition Bot is running!"

@app.route('/health')
def health():
    return "✅ Bot is healthy"

class SpeechRecognitionBot:
    def __init__(self, token: str):
        self.bot = telebot.TeleBot(token)
        self.setup_handlers()
        
        # Мови для розпізнавання
        self.languages = {
            'uk': 'Українська',
            'ru': 'Російська', 
            'en': 'Англійська'
        }
        
        logger.info("🤖 Бот ініціалізовано з реальним розпізнаванням мови!")

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

🚀 Бот використовує AI для реального розпізнавання мови!
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
            self.process_video_note(message)

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
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return output_path
            else:
                logger.error(f"FFmpeg помилка: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("Таймаут конвертації аудіо")
            return None
        except Exception as e:
            logger.error(f"Помилка конвертації: {e}")
            return None

    def recognize_with_whisper(self, audio_path: str, language: str = "auto") -> Optional[str]:
        """
        Реальне розпізнавання мови через Whisper API
        """
        try:
            # Використовуємо безкоштовний Whisper API через Hugging Face
            API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"
            
            headers = {
                "Authorization": "Bearer hf_your_token_here",  # Можна використовувати без токена для демо
            }
            
            # Читаємо аудіо файл
            with open(audio_path, "rb") as f:
                data = f.read()
            
            # Надсилаємо запит до API
            response = requests.post(API_URL, headers=headers, data=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if 'text' in result:
                    text = result['text'].strip()
                    if text:
                        logger.info(f"Успішне розпізнавання: {text[:100]}...")
                        return text
            else:
                logger.warning(f"API помилка: {response.status_code} - {response.text}")
                
        except requests.exceptions.Timeout:
            logger.warning("Таймаут Whisper API")
        except Exception as e:
            logger.error(f"Помилка Whisper API: {e}")
        
        # Якщо API не спрацював, використовуємо локальне розпізнавання
        return self.recognize_with_speech_recognition(audio_path, language)

    def recognize_with_speech_recognition(self, audio_path: str, language: str) -> Optional[str]:
        """
        Розпізнавання через speech_recognition бібліотеку
        """
        try:
            import speech_recognition as sr
            
            # Відображення мов для speech_recognition
            lang_map = {
                'uk': 'uk-UA',
                'ru': 'ru-RU',
                'en': 'en-US'
            }
            
            recognizer = sr.Recognizer()
            
            with sr.AudioFile(audio_path) as source:
                # Налаштування для покращення якості
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = recognizer.record(source)
                
                # Спершу пробуємо Google Speech Recognition
                try:
                    text = recognizer.recognize_google(audio_data, language=lang_map.get(language, 'en-US'))
                    if text:
                        logger.info(f"Google Speech Recognition: {text[:100]}...")
                        return text
                except Exception as e:
                    logger.warning(f"Google Speech Recognition failed: {e}")
                
                # Потім пробуємо Sphinx (офлайн)
                try:
                    text = recognizer.recognize_sphinx(audio_data)
                    if text:
                        logger.info(f"Sphinx Recognition: {text[:100]}...")
                        return text
                except Exception as e:
                    logger.warning(f"Sphinx Recognition failed: {e}")
                    
        except ImportError:
            logger.warning("Бібліотека speech_recognition не встановлена")
        except Exception as e:
            logger.error(f"Помилка speech_recognition: {e}")
            
        return None

    def recognize_speech(self, audio_path: str) -> Dict[str, str]:
        """
        Головна функція розпізнавання мови
        """
        results = {}
        
        logger.info("Початок реального розпізнавання мови...")
        
        # Спершу пробуємо автоматичне розпізнавання
        text = self.recognize_with_whisper(audio_path, "auto")
        
        if text and len(text.strip()) > 5:
            results['Автоматично'] = text
            logger.info("Успішне автоматичне розпізнавання")
        else:
            # Якщо автоматичне не спрацювало, пробуємо для кожної мови
            for lang_code, lang_name in self.languages.items():
                try:
                    logger.info(f"Спроба розпізнавання для мови: {lang_name}")
                    
                    text = self.recognize_with_whisper(audio_path, lang_code)
                    
                    if not text:
                        text = self.recognize_with_speech_recognition(audio_path, lang_code)
                    
                    if text and len(text.strip()) > 5:
                        results[lang_name] = text
                        logger.info(f"Успішне розпізнавання для {lang_name}")
                        break
                        
                except Exception as e:
                    logger.error(f"Помилка розпізнавання для {lang_name}: {e}")
                    continue
        
        # Якщо жоден метод не спрацював, повертаємо помилку
        if not results:
            logger.error("Не вдалося розпізнати мову жодним методом")
            results = {
                'Помилка': "Не вдалося розпізнати мову. Можливі причини:\n• Занадто коротке аудіо\n• Сильний фоновий шум\n• Непідтримувана мова\n• Проблеми з інтернет-з'єднанням\n\nСпробуйте ще раз з більш чітким аудіо."
            }
        
        return results

    def combine_results(self, results: Dict[str, str]) -> str:
        """Об'єднання результатів розпізнавання"""
        if not results or 'Помилка' in results:
            error_msg = results.get('Помилка', 'Не вдалося розпізнати мову')
            return f"❌ {error_msg}"
        
        combined_text = "🎤 **РЕЗУЛЬТАТ РОЗПІЗНАВАННЯ**\n\n"
        
        for lang, text in results.items():
            combined_text += f"**🌍 Мова: {lang}**\n"
            combined_text += f"📝 {text}\n\n"
        
        combined_text += "---\n"
        combined_text += "✅ Голос успішно конвертовано в текст!"
        
        return combined_text

    def process_audio_message(self, message: Message, file_obj, file_type: str):
        """Обробка аудіо повідомлень"""
        processing_msg = self.bot.reply_to(message, "🔍 Завантаження аудіо...")
        
        temp_file = None
        wav_file = None
        
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
                return

            self.bot.edit_message_text(
                "🎤 Розпізнавання мови... Це може зайняти кілька секунд",
                message.chat.id,
                processing_msg.message_id
            )

            # Розпізнавання мови
            results = self.recognize_speech(wav_file)
            combined_text = self.combine_results(results)

            # Відправка результату
            self.bot.edit_message_text(
                combined_text,
                message.chat.id,
                processing_msg.message_id
            )
            
            logger.info(f"✅ Успішно оброблено {file_type}")

        except Exception as e:
            logger.error(f"❌ Помилка обробки аудіо: {e}")
            self.bot.edit_message_text(
                "❌ Сталася помилка під час обробки",
                message.chat.id,
                processing_msg.message_id
            )
        finally:
            # Очищення тимчасових файлів
            self.cleanup_files(temp_file, wav_file)

    def process_video_note(self, message: Message):
        """Обробка відеокружок"""
        try:
            processing_msg = self.bot.reply_to(message, "🔍 Завантаження відеокружки...")
            
            # Завантаження відео
            temp_video = self.download_file(message.video_note.file_id)
            if not temp_video:
                self.bot.edit_message_text(
                    "❌ Помилка завантаження відео",
                    message.chat.id,
                    processing_msg.message_id
                )
                return

            self.bot.edit_message_text(
                "🔄 Видобуток аудіо з відео...",
                message.chat.id,
                processing_msg.message_id
            )

            # Видобуток аудіо з відео
            audio_file = self.extract_audio_from_video(temp_video)
            if not audio_file:
                self.bot.edit_message_text(
                    "❌ Помилка видобутку аудіо з відео",
                    message.chat.id,
                    processing_msg.message_id
                )
                self.cleanup_files(temp_video)
                return

            self.bot.edit_message_text(
                "🎤 Розпізнавання мови з відео...",
                message.chat.id,
                processing_msg.message_id
            )

            # Розпізнавання мови
            results = self.recognize_speech(audio_file)
            combined_text = self.combine_results(results)

            # Відправка результату
            self.bot.edit_message_text(
                combined_text,
                message.chat.id,
                processing_msg.message_id
            )
            
            logger.info("✅ Успішно оброблено відеокружку")

        except Exception as e:
            logger.error(f"❌ Помилка обробки відеокружки: {e}")
            self.bot.reply_to(message, "❌ Помилка обробки відеокружки")
        finally:
            # Очищення тимчасових файлів
            self.cleanup_files(temp_video, audio_file)

    def extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """Видобуток аудіо з відеофайлу"""
        try:
            audio_path = video_path + '.wav'
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn', '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000',
                '-y', audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return audio_path
            else:
                logger.error(f"FFmpeg помилка (відео): {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Помилка видобутку аудіо з відео: {e}")
            return None

    def cleanup_files(self, *files):
        """Очищення тимчасових файлів"""
        for file_path in files:
            try:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Помилка видалення файлу {file_path}: {e}")

    def run_polling(self):
        """Запуск бота в режимі polling"""
        logger.info("🚀 Запуск Telegram бота з реальним розпізнаванням мови...")
        try:
            self.bot.infinity_polling(timeout=90, long_polling_timeout=90)
        except Exception as e:
            logger.error(f"Помилка бота: {e}")
            import time
            time.sleep(10)
            logger.info("🔄 Перезапуск бота...")
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