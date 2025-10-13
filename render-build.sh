#!/bin/bash
set -o errexit

# Встановлюємо системні залежності
apt-get update
apt-get install -y ffmpeg

# Встановлюємо Python залежності
pip install -r requirements.txt

# SpeechRecognition встановлюємо окремо з обхідним шляхом
pip install --no-deps SpeechRecognition==3.10.0
