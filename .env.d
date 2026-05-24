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

# Env variables for the PicoVoice SDK
PICOVOICE_ACCESS_KEY=your-secret-api-key
WAKE_WORD_FILE=Hey-Cookbook_en_raspberry-pi_v3_0_0.ppn
MODEL_FILE=vosk-model-small-en-us-0.15
