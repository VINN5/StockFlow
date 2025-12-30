import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-fallback'
    MONGODB_URI = os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017/stockflow'