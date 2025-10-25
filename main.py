import os
import logging
import tempfile
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import speech_recognition as sr
from pydub import AudioSegment
import requests
from pytube import YouTube
import moviepy.editor as mp
from langdetect import detect, LangDetectError
from googletrans import Translator

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class VoiceToTextConverter:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.translator = Translator()
        
    def download_file(self, file_url, file_path):
        """Скачивание файла по URL"""
        try:
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Файл успешно скачан: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка скачивания файла: {str(e)}")
            return False

    def convert_to_wav(self, input_path, output_path):
        """Конвертация аудио в WAV формат"""
        try:
            audio = AudioSegment.from_file(input_path)
            audio = audio.set_frame_rate(16000).set_channels(1)
            audio.export(output_path, format="wav")
            logger.info(f"Файл конвертирован в WAV: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка конвертации в WAV: {str(e)}")
            return False

    def extract_audio_from_video(self, video_path, audio_path):
        """Извлечение аудио из видео"""
        try:
            video = mp.VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path, verbose=False, logger=None)
            logger.info(f"Аудио извлечено из видео: {audio_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка извлечения аудио из видео: {str(e)}")
            return False

    def transcribe_audio(self, audio_path, language='uk-UA'):
        """Транскрибация аудио в текст"""
        try:
            with sr.AudioFile(audio_path) as source:
                audio_data = self.recognizer.record(source)
                
            # Определяем язык для распознавания
            lang_map = {
                'ukrainian': 'uk-UA',
                'russian': 'ru-RU', 
                'english': 'en-US'
            }
            
            # Пробуем распознать с разными языками
            text = ""
            for lang_name, lang_code in lang_map.items():
                try:
                    text = self.recognizer.recognize_google(audio_data, language=lang_code)
                    logger.info(f"Текст распознан на языке: {lang_name}")
                    break
                except sr.UnknownValueError:
                    continue
                except sr.RequestError as e:
                    logger.error(f"Ошибка сервиса распознавания для {lang_name}: {e}")
                    continue
            
            return text if text else None
            
        except Exception as e:
            logger.error(f"Ошибка транскрибации: {str(e)}")
            return None

    def detect_and_translate_mixed_language(self, text):
        """Обнаружение и перевод смешанного языка"""
        try:
            # Определяем язык текста
            detected_lang = detect(text)
            logger.info(f"Обнаружен язык: {detected_lang}")
            
            # Если текст не на украинском, переводим его
            if detected_lang != 'uk':
                try:
                    translated = self.translator.translate(text, dest='uk')
                    return translated.text
                except Exception as e:
                    logger.error(f"Ошибка перевода: {str(e)}")
                    return text
            
            return text
            
        except LangDetectError as e:
            logger.error(f"Ошибка определения языка: {str(e)}")
            return text
        except Exception as e:
            logger.error(f"Неожиданная ошибка при работе с языком: {str(e)}")
            return text

    async def process_voice_message(self, file_url):
        """Обработка голосового сообщения"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_ogg:
            temp_ogg_path = temp_ogg.name
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_wav:
            temp_wav_path = temp_wav.name

        try:
            # Скачиваем файл
            if not self.download_file(file_url, temp_ogg_path):
                return "❌ Ошибка скачивания файла"

            # Конвертируем в WAV
            if not self.convert_to_wav(temp_ogg_path, temp_wav_path):
                return "❌ Ошибка конвертации аудио"

            # Распознаем речь
            text = self.transcribe_audio(temp_wav_path)
            if not text:
                return "❌ Не удалось распознать речь"

            # Обрабатываем смешанные языки
            final_text = self.detect_and_translate_mixed_language(text)
            
            return f"📝 Распознанный текст:\n\n{final_text}"

        except Exception as e:
            logger.error(f"Общая ошибка обработки голосового сообщения: {str(e)}")
            return f"❌ Произошла ошибка при обработке: {str(e)}"
        finally:
            # Очистка временных файлов
            for path in [temp_ogg_path, temp_wav_path]:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except Exception as e:
                    logger.error(f"Ошибка удаления временного файла {path}: {e}")

    async def process_video_message(self, file_url):
        """Обработка видео сообщения"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
            temp_video_path = temp_video.name
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_wav:
            temp_wav_path = temp_wav.name

        try:
            # Скачиваем видео
            if not self.download_file(file_url, temp_video_path):
                return "❌ Ошибка скачивания видео"

            # Извлекаем аудио
            if not self.extract_audio_from_video(temp_video_path, temp_wav_path):
                return "❌ Ошибка извлечения аудио из видео"

            # Распознаем речь
            text = self.transcribe_audio(temp_wav_path)
            if not text:
                return "❌ Не удалось распознать речь в видео"

            # Обрабатываем смешанные языки
            final_text = self.detect_and_translate_mixed_language(text)
            
            return f"🎥 Текст из видео:\n\n{final_text}"

        except Exception as e:
            logger.error(f"Общая ошибка обработки видео: {str(e)}")
            return f"❌ Произошла ошибка при обработке видео: {str(e)}"
        finally:
            # Очистка временных файлов
            for path in [temp_video_path, temp_wav_path]:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except Exception as e:
                    logger.error(f"Ошибка удаления временного файла {path}: {e}")

# Создаем экземпляр конвертера
converter = VoiceToTextConverter()

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик голосовых сообщений"""
    try:
        await update.message.reply_text("🎤 Обрабатываю голосовое сообщение...")
        
        voice_file = await update.message.voice.get_file()
        result = await converter.process_voice_message(voice_file.file_url)
        
        await update.message.reply_text(result)
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике голосовых сообщений: {str(e)}")
        await update.message.reply_text("❌ Произошла ошибка при обработке голосового сообщения")

async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик видео сообщений"""
    try:
        await update.message.reply_text("🎥 Обрабатываю видео...")
        
        video_file = await update.message.video.get_file()
        result = await converter.process_video_message(video_file.file_url)
        
        await update.message.reply_text(result)
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике видео сообщений: {str(e)}")
        await update.message.reply_text("❌ Произошла ошибка при обработке видео")

async def handle_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик видеокружков"""
    try:
        await update.message.reply_text("⭕ Обрабатываю видеосообщение...")
        
        video_note_file = await update.message.video_note.get_file()
        result = await converter.process_video_message(video_note_file.file_url)
        
        await update.message.reply_text(result)
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике видеокружков: {str(e)}")
        await update.message.reply_text("❌ Произошла ошибка при обработке видеосообщения")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = """
🤖 Добро пожаловать в Voice2Text бот!

Я могу конвертировать в текст:
• 🎤 Голосовые сообщения
• 🎥 Видео сообщения  
• ⭕ Видеокружки

Поддерживаемые языки:
🇺🇦 Украинский
🇷🇺 Русский  
🇬🇧 Английский

Если в сообщении смешанные языки, я автоматически переведу русские и английские слова на украинский.

Просто отправьте мне голосовое или видео сообщение!
    """
    await update.message.reply_text(welcome_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке обновления {update}: {context.error}")
    
    if update and update.message:
        try:
            await update.message.reply_text("❌ Произошла внутренняя ошибка. Попробуйте позже.")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {e}")

def main():
    """Основная функция"""
    # Получаем токен бота из переменных окружения
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return

    try:
        # Создаем приложение
        application = Application.builder().token(bot_token).build()
        
        # Добавляем обработчики
        application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
        application.add_handler(MessageHandler(filters.VIDEO, handle_video_message))
        application.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))
        application.add_handler(MessageHandler(filters.COMMAND, start_command))
        
        # Добавляем обработчик ошибок
        application.add_error_handler(error_handler)
        
        logger.info("Бот запущен успешно!")
        
        # Запускаем бота
        port = int(os.environ.get('PORT', 8443))
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=bot_token,
            webhook_url=f"https://your-app-name.onrender.com/{bot_token}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {str(e)}")

if __name__ == '__main__':
    main()