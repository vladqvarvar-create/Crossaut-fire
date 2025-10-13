import os
import telebot
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import requests
import re
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

def download_file(url, file_path):
    response = requests.get(url, timeout=30)
    with open(file_path, 'wb') as f:
        f.write(response.content)

def convert_audio_to_wav(input_path):
    """Конвертує аудіо в WAV"""
    try:
        if input_path.endswith('.oga') or input_path.endswith('.ogg'):
            audio = AudioSegment.from_ogg(input_path)
        else:
            audio = AudioSegment.from_file(input_path)
        
        # Оптимальні налаштування для розпізнавання
        audio = audio.set_frame_rate(16000)
        audio = audio.set_channels(1)
        
        # Нормалізація гучності
        if audio.dBFS < -25:
            audio = audio + 8
        
        wav_path = input_path.replace('.oga', '.wav').replace('.ogg', '.wav')
        audio.export(wav_path, format="wav")
        
        logger.info(f"Аудіо конвертовано: {len(audio)}ms")
        return wav_path
        
    except Exception as e:
        logger.error(f"Помилка конвертації: {e}")
        return None

def transcribe_audio(audio_path, language='uk-UA'):
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.pause_threshold = 0.8
    
    try:
        with sr.AudioFile(audio_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)
            
            if len(audio_data.frame_data) == 0:
                return ""
            
            text = recognizer.recognize_google(audio_data, language=language, timeout=25)
            logger.info(f"Розпізнано {language}: {text[:50]}...")
            return text
            
    except sr.UnknownValueError:
        return ""
    except Exception as e:
        logger.error(f"Помилка розпізнавання {language}: {e}")
        return ""

def transcribe_all_languages(audio_path):
    """Розпізнає аудіо трьома мовами"""
    results = {}
    
    languages = [
        ('uk-UA', '🇺🇦 Українська'),
        ('ru-RU', '🇷🇺 Російська'), 
        ('en-US', '🇬🇧 Англійська')
    ]
    
    for lang_code, lang_name in languages:
        text = transcribe_audio(audio_path, lang_code)
        if text and len(text.strip()) > 1:  # Мінімум 2 символи
            results[lang_name] = text
    
    return results

def format_results(results, file_type):
    """Форматує результати"""
    if not results:
        return f"""
📁 Тип: {file_type}
❌ Не вдалося розпізнати мову

💡 Можливі причини:
• Занадто коротке аудіо (менше 2 секунд)
• Сильний шум на фоні
• Дуже тихий голос
• Мова не підтримується

🎤 Поради:
• Говоріть чітко та голосно
• Тримайте мікрофон ближче
• Записуйте в тихому місці
• Тривалість 3-30 секунд
"""
    
    formatted = f"📁 Тип: {file_type}\n"
    formatted += f"🎯 Розпізнано мов: {len(results)}\n\n"
    
    for lang, text in results.items():
        # Покращуємо текст
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            text = text[0].upper() + text[1:]
            if text[-1] not in ['.', '!', '?']:
                text += '.'
            
            formatted += f"{lang}:\n{text}\n\n"
    
    return formatted

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🎤 Бот для розпізнавання мови на Render!

🌟 Підтримує мови:
• Українська 🇺🇦 • Російська 🇷🇺 • Англійська 🇬🇧
• Суржик та змішані мови 🔀

📁 Працює з:
• Голосовими повідомленнями 🎤
• Аудіо файлами 🎵  
• Відеокружками 🎥

💡 Для кращого розпізнавання:
• Говоріть чітко та досить голосно
• Тривалість: 3-30 секунд
• Мінімум шумів на фоні

Надішліть голосове повідомлення і бот розпізнає його!
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['status'])
def status(message):
    bot.reply_to(message, "✅ Бот працює нормально на Render!")

@bot.message_handler(content_types=['voice', 'audio', 'video_note'])
def handle_audio(message):
    temp_path, wav_path = None, None
    
    try:
        msg = bot.reply_to(message, "🔄 Обробка аудіо...")
        
        # Визначаємо тип файлу
        if message.voice:
            file_info = bot.get_file(message.voice.file_id)
            file_type = "голосове повідомлення"
        elif message.audio:
            file_info = bot.get_file(message.audio.file_id)
            file_type = "аудіо файл"
        elif message.video_note:
            file_info = bot.get_file(message.video_note.file_id)
            file_type = "відеокружок"
        else:
            bot.edit_message_text("❌ Непідтримуваний тип файлу", message.chat.id, msg.message_id)
            return
        
        # Завантажуємо файл
        bot.edit_message_text("📥 Завантаження...", message.chat.id, msg.message_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        
        temp_path = tempfile.NamedTemporaryFile(delete=False, suffix='.oga').name
        download_file(file_url, temp_path)
        
        # Конвертуємо
        bot.edit_message_text("🔧 Конвертація...", message.chat.id, msg.message_id)
        wav_path = convert_audio_to_wav(temp_path)
        
        if not wav_path:
            bot.edit_message_text("❌ Помилка обробки аудіо", message.chat.id, msg.message_id)
            return
        
        # Розпізнаємо
        bot.edit_message_text("🎤 Розпізнавання...", message.chat.id, msg.message_id)
        results = transcribe_all_languages(wav_path)
        
        # Відправляємо результат
        final_text = format_results(results, file_type)
        bot.edit_message_text(final_text, message.chat.id, msg.message_id)
        
    except Exception as e:
        logger.error(f"Помилка: {e}")
        error_msg = f"❌ Помилка: {str(e)}"
        try:
            bot.edit_message_text(error_msg, message.chat.id, msg.message_id)
        except:
            bot.reply_to(message, error_msg)
    
    finally:
        # Очищаємо тимчасові файли
        for path in [temp_path, wav_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except:
                    pass

@bot.message_handler(content_types=['text'])
def handle_text(message):
    bot.reply_to(message, "🎤 Надішліть голосове повідомлення для розпізнавання!")

if __name__ == "__main__":
    logger.info("🚀 Бот запускається на Render...")
    bot.infinity_polling()
