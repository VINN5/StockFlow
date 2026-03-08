import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY    = os.environ.get('SECRET_KEY') or 'dev-secret-fallback'
    MONGODB_URI   = os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017/stockflow'

    # M-Pesa Daraja API
    MPESA_CONSUMER_KEY    = os.environ.get('MPESA_CONSUMER_KEY', '')
    MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET', '')
    MPESA_SHORTCODE       = os.environ.get('MPESA_SHORTCODE', '174379')
    MPESA_PASSKEY         = os.environ.get('MPESA_PASSKEY', '')
    MPESA_CALLBACK_URL    = os.environ.get('MPESA_CALLBACK_URL', '')
    MPESA_ENV             = os.environ.get('MPESA_ENV', 'sandbox')

    # Africa's Talking SMS
    AT_API_KEY   = os.environ.get('AT_API_KEY', '')
    AT_USERNAME  = os.environ.get('AT_USERNAME', 'sandbox')
    AT_SENDER_ID = os.environ.get('AT_SENDER_ID', 'StockFlow')