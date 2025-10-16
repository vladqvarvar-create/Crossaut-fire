import os
import logging
import tempfile
import subprocess
from typing import Optional, Dict
import telebot
from telebot.types import Message, Voice, Audio, VideoNote

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class SpeechRecognitionBot:
    def __init__(self, token: str):
        self.bot = telebot.TeleBot(token)
        self.setup_handlers()
        
        # Мови для розпізнавання
        self.languages = {
            'uk': 'Українська',
            'ru': 'Русский', 
            'en': 'English'
        }
        
        logger.info("Бот ініціалізовано та готовий до роботи")

    def setup_handlers(self):
        """Налаштування обробників повідомлень"""
        @self.bot.message_handler(commands=['start', 'help'])
        def send_welcome(message: Message):
            welcome_text = """
🎤 Бот для розпізнавання голосових повідомлень

📌 Підтримувані формати:
• Голосові повідомлення
• Аудіофайли
• Відеокружки

🌍 Підтримувані мови:
• Українська
• Російська 
• Англійська

💡 Просто надішліть голосове повідомлення, аудіо або відеокружку!
            """
            self.bot.reply_to(message, welcome_text)

        @self.bot.message_handler(commands=['status'])
        def send_status(message: Message):
            status_text = "✅ Бот працює нормально! Надішліть голосове повідомлення для розпізнавання."
            self.bot.reply_to(message, status_text)

        @self.bot.message_handler(content_types=['voice'])
        def handle_voice(message: Message):
            self.process_audio_message(message, message.voice, 'voice')

        @self.bot.message_handler(content_types=['audio'])
        def handle_audio(message: Message):
            self.process_audio_message(message, message.audio, 'audio')

        @self.bot.message_handler(content_types=['video_note'])
        def handle_video_note(message: Message):
            self.process_video_note(message, message.video_note)

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
            
            # Використання ffmpeg для конвертації
            cmd = [
                'ffmpeg', '-i', input_path,
                '-acodec', 'pcm_s16le',
                '-ac', '1',
                '-ar', '16000',
                '-y', output_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg помилка: {result.stderr}")
                return None
                
            return output_path
        except subprocess.TimeoutExpired:
            logger.error("Таймаут конвертації аудіо")
            return None
        except Exception as e:
            logger.error(f"Помилка конвертації: {e}")
            return None

    def extract_audio_from_video_note(self, video_path: str) -> Optional[str]:
        """Видобуток аудіо з відеокружки"""
        try:
            audio_path = video_path + '.wav'
            
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn', '-acodec', 'pcm_s16le',
                '-ac', '1', '-ar', '16000',
                '-y', audio_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg помилка (відео): {result.stderr}")
                return None
                
            return audio_path
        except Exception as e:
            logger.error(f"Помилка видобутку аудіо з відео: {e}")
            return None

    def recognize_speech(self, audio_path: str) -> Dict[str, str]:
        """
        Розпізнавання мови з використанням безкоштовних сервісів
        """
        results = {}
        
        # Список доступних сервісів розпізнавання
        services = [
            self.recognize_with_google,
            self.recognize_with_mozilla
        ]
        
        for service in services:
            try:
                for lang_code, lang_name in self.languages.items():
                    logger.info(f"Спроба розпізнавання {lang_name}")
                    text = service(audio_path, lang_code)
                    
                    if text and len(text.strip()) > 5:
                        results[lang_name] = text
                        logger.info(f"Успішне розпізнавання {lang_name}")
                        break
                        
            except Exception as e:
                logger.error(f"Помилка сервісу розпізнавання: {e}")
                continue
                
            if results:  # Якщо отримали результати, виходимо
                break
                
        return results

    def recognize_with_google(self, audio_path: str, language: str) -> Optional[str]:
        """
        Заглушка для Google Speech Recognition
        У реальному використанні потрібно використовувати speech_recognition або прямі API виклики
        """
        try:
            # Імітація обробки
            logger.info(f"Імітація Google розпізнавання для {language}")
            
            # Тут буде реальна логіка з використанням:
            # - Google Speech-to-Text API
            # - або бібліотеки speech_recognition
            
            return f"Це демонстраційний текст розпізнавання для мови {self.languages[language]}. У реальній версії тут буде розпізнаний текст з вашого аудіо."
            
        except Exception as e:
            logger.error(f"Помилка Google розпізнавання: {e}")
            return None

    def recognize_with_mozilla(self, audio_path: str, language: str) -> Optional[str]:
        """
        Заглушка для Mozilla DeepSpeech
        """
        try:
            logger.info(f"Імітація Mozilla розпізнавання для {language}")
            
            # Тут буде реалізація з використанням DeepSpeech
            # Потребує завантаження моделей для кожної мови
            
            return f"DeepSpeech розпізнавання для {self.languages[language]}. Це демонстраційний текст."
            
        except Exception as e:
            logger.error(f"Помилка Mozilla розпізнавання: {e}")
            return None

    def combine_results(self, results: Dict[str, str]) -> str:
        """Об'єднання результатів розпізнавання"""
        if not results:
            return "❌ Не вдалося розпізнати мову. Спробуйте ще раз з більш чітким аудіо."
        
        combined_text = "🎤 Результат розпізнавання:\n\n"
        
        for lang, text in results.items():
            combined_text += f"🌍 {lang}:\n{text}\n\n"
        
        combined_text += "💡 Це демонстраційна версія. Для повної функціональності потрібно налаштувати API розпізнавання мови."
        return combined_text

    def cleanup_files(self, *files):
        """Очищення тимчасових файлів"""
        for file_path in files:
            try:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Помилка видалення файлу {file_path}: {e}")

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

            # Розпізнавання мови
            results = self.recognize_speech(wav_file)
            combined_text = self.combine_results(results)

            # Відправка результату
            self.bot.edit_message_text(
                combined_text,
                message.chat.id,
                processing_msg.message_id
            )
            
            logger.info(f"Успішно оброблено {file_type} повідомлення")

        except Exception as e:
            logger.error(f"Помилка обробки аудіо: {e}")
            self.bot.edit_message_text(
                "❌ Сталася помилка під час обробки. Спробуйте ще раз.",
                message.chat.id,
                processing_msg.message_id
            )
        finally:
            # Очищення тимчасових файлів
            self.cleanup_files(temp_file, wav_file)

    def process_video_note(self, message: Message, video_note: VideoNote):
        """Обробка відеокружок"""
        processing_msg = self.bot.reply_to(message, "🔍 Завантаження відео...")
        
        try:
            # Завантаження відео
            temp_video = self.download_file(video_note.file_id)
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

            # Видобуток аудіо
            audio_file = self.extract_audio_from_video_note(temp_video)
            if not audio_file:
                self.bot.edit_message_text(
                    "❌ Помилка видобутку аудіо з відео",
                    message.chat.id,
                    processing_msg.message_id
                )
                self.cleanup_files(temp_video)
                return

            self.bot.edit_message_text(
                "🎤 Розпізнавання мови...",
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
            
            logger.info("Успішно оброблено відеокружку")

        except Exception as e:
            logger.error(f"Помилка обробки відеокружки: {e}")
            self.bot.edit_message_text(
                "❌ Сталася помилка під час обробки відео",
                message.chat.id,
                processing_msg.message_id
            )
        finally:
            # Очищення тимчасових файлів
            self.cleanup_files(temp_video, audio_file)

    def run(self):
        """Запуск бота"""
        logger.info("Запуск бота на Render...")
        try:
            self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Помилка запуску бота: {e}")
            # Перезапуск через 10 секунд
            import time
            time.sleep(10)
            self.run()

def main():
    """Основна функція"""
    # Отримання токену з змінних середовища Render
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("Не вказано TELEGRAM_BOT_TOKEN у змінних середовища")
        print("ПОМИЛКА: Вкажіть TELEGRAM_BOT_TOKEN у налаштуваннях Render")
        return

    logger.info("Токен знайдено, запуск бота...")
    
    # Створення та запуск бота
    bot = SpeechRecognitionBot(token)
    bot.run()

if __name__ == '__main__':
    main()