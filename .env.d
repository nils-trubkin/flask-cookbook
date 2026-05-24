# Server configuration
HOSTNAME=your-hostname
FLASK_PROTOCOL=http
FLASK_HOST=0.0.0.0
FLASK_PORT=8001
FLASK_WORKERS=4

# Env variables for the kiosk app
RECIPES_DIR=recipes

# Env variables for the receipts part
RECEIPTS_DIR=receipts

# Env variables for the backup part
BACKUP_DIR=backups

# Env variables for the speech recognition
MODEL_FILE=vosk-model-small-en-us-0.15
# Wake word model: path to a .tflite file, or a built-in name (e.g. "alexa", "hey_jarvis")
# Falls back to "alexa" if the file or name is not found
WAKE_WORD_MODEL=wake_words/hey_cookbook.tflite
