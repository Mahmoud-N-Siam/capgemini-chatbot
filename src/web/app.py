import logging
import os
from pathlib import Path
from flask import Flask
from flask_cors import CORS
from config.settings import Settings

logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'capgemini-chatbot-secret')
    app.config['UPLOAD_FOLDER'] = str(Settings.UPLOAD_FOLDER)
    app.config['MAX_CONTENT_LENGTH'] = Settings.MAX_FILE_SIZE
    app.config['JSON_SORT_KEYS'] = False
    CORS(app, resources={r'/api/*': {'origins': ['*'], 'methods': ['GET', 'POST', 'DELETE', 'OPTIONS'], 'allow_headers': ['Content-Type', 'Authorization']}})
    
    if Settings.DEBUG:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    from src.web.routes import api_routes, web_routes
    app.register_blueprint(api_routes)
    app.register_blueprint(web_routes)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    return app