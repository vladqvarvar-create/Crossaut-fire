import os
import logging
import tempfile
import subprocess
import requests
import json
import wave
from typing import Optional, Dict
import telebot
from telebot.types import Message, Voice, Audio, VideoNote

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SpeechRecognitionBot:
    def __init__(self, token: str):
        self.bot = telebot.TeleBot(token)
        self.setup_handlers()
        
        self.whisper_token = os.getenv('HUGGINGFACE_TOKEN', '')
        logger.info("🤖 Бот ініціалізовано!")

    def setup_handlers(self):
        @self.bot.message_handler(commands=['start', 'help'])
        def send_welcome(message: Message):
            welcome_text = """
🎤 Бот для РЕАЛЬНОГО розпізнавання голосу

📌 Надсилайте голосові повідомлення
🌍 Мови: Українська, Російська, Англійська
🚀 Використовує Whisper AI
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
            else:
                logger.error(f"FFmpeg помилка: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Помилка конвертації: {e}")
            return None

    def recognize_with_whisper_api(self, audio_path: str) -> Optional[str]:
        """Реальне розпізнавання через Whisper API"""
        try:
            if not self.whisper_token:
                logger.warning("❌ Whisper токен не вказано")
                return None

            API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"
            
            headers = {"Authorization": f"Bearer {self.whisper_token}"}
            
            # Перевіряємо чи файл існує і не порожній
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                logger.error("❌ Аудіо файл не існує або порожній")
                return None
            
            with open(audio_path, "rb") as f:
                data = f.read()
            
            logger.info("📡 Надсилання до Whisper API...")
            response = requests.post(API_URL, headers=headers, data=data, timeout=60)
            
            logger.info(f"🔔 Whisper статус: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('text', '').strip()
                if text and len(text) > 1:  # Зменшимо мінімальну довжину тексту
                    logger.info(f"✅ Whisper успішно розпізнав текст: {text[:50]}...")
                    return text
                else:
                    logger.warning("❌ Whisper повернув порожній текст")
                    return None
                    
            elif response.status_code == 503:
                # Модель завантажується
                error_info = response.json().get('error', '')
                logger.warning(f"⏳ Модель завантажується: {error_info}")
                return None
                
            else:
                error_text = response.text[:500] if response.text else "Немає деталей"
                logger.error(f"❌ Whisper помилка {response.status_code}: {error_text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Помилка запиту до Whisper: {e}")
            return None

    def get_audio_info(self, audio_path: str) -> Dict[str, any]:
        """Отримання інформації про аудіо"""
        try:
            with wave.open(audio_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration = frames / float(rate)
                
                return {
                    'duration': duration,
                    'sample_rate': rate,
                    'channels': wav_file.getnchannels(),
                    'frames': frames
                }
        except Exception as e:
            logger.error(f"Помилка аналізу аудіо: {e}")
            return {'duration': 0, 'sample_rate': 0, 'channels': 0, 'frames': 0}

    def recognize_speech(self, audio_path: str) -> Dict[str, str]:
        """Основна функція розпізнавання"""
        logger.info("🔍 Початок реального розпізнавання...")
        
        # Отримуємо інформацію про аудіо
        audio_info = self.get_audio_info(audio_path)
        logger.info(f"📊 Аудіо: {audio_info['duration']:.1f}с, {audio_info['sample_rate']}Hz")
        
        # Перевіряємо тривалість аудіо
        if audio_info['duration'] < 0.5:
            return {
                'Помилка': "❌ Аудіо занадто коротке (менше 0.5 секунди)"
            }
        
        # 1. Спроба Whisper API
        if self.whisper_token:
            text = self.recognize_with_whisper_api(audio_path)
            if text:
                return {'Whisper AI': text}
        
        # 2. Якщо Whisper не спрацював
        if audio_info['duration'] > 0:
            return {
                'Інформація': f"""🔊 Аудіо аналіз:
• Тривалість: {audio_info['duration']:.1f} секунд
• Частота: {audio_info['sample_rate']} Hz
• Канали: {audio_info['channels']}

❌ Не вдалося розпізнати мову.

💡 Можливі причини:
• Whisper API тимчасово недоступний
• Модель завантажується (зачекайте 20-30 сек)
• Проблеми з інтернет-з'єднанням
• Аудіо занадто коротке або тихе

🔄 Спробуйте ще раз через декілька хвилин."""
            }
        else:
            return {
                'Помилка': "❌ Не вдалося обробити аудіо файл. Спробуйте інше голосове повідомлення."
            }

    def combine_results(self, results: Dict[str, str]) -> str:
        if not results:
            return "❌ Не вдалося обробити аудіо."
        
        if 'Помилка' in results:
            return results['Помилка']
            
        if 'Інформація' in results:
            return results['Інформація']
        
        # Реальний розпізнаний текст
        combined_text = "🎤 **ТЕКСТ РОЗПІЗНАНО З ГОЛОСУ:**\n\n"
        
        for service, text in results.items():
            combined_text += f"**{service}:**\n"
            combined_text += f"{text}\n\n"
        
        combined_text += "✅ Голос успішно конвертовано в текст!"
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
            logger.info("✅ Обробка завершена")

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

    def run(self):
        """Запуск бота без Flask"""
        logger.info("🚀 Запуск бота...")
        try:
            self.bot.infinity_polling(timeout=90, long_polling_timeout=90)
        except Exception as e:
            logger.error(f"Помилка: {e}")
            import time
            time.sleep(10)
            logger.info("🔄 Перезапуск бота...")
            self.run()

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ Немає TELEGRAM_BOT_TOKEN")
        return

    # Перевіряємо токен Whisper
    whisper_token = os.getenv('HUGGINGFACE_TOKEN', '')
    if whisper_token:
        logger.info("✅ Whisper токен знайдено")
    else:
        logger.warning("⚠️ Whisper токен не вказано, розпізнавання може не працювати")

    bot = SpeechRecognitionBot(token)
    bot.run()

if __name__ == '__main__':
    main()