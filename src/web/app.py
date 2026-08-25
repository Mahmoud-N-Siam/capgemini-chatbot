import logging
import secrets
from pathlib import Path
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from config.settings import Settings

logger = logging.getLogger(__name__)

def create_app():
    Settings.validate()
    app = Flask(__name__)
    app.config['SECRET_KEY'] = Settings.SECRET_KEY or secrets.token_hex(32)
    app.config['UPLOAD_FOLDER'] = str(Settings.UPLOAD_FOLDER)
    app.config['MAX_CONTENT_LENGTH'] = Settings.MAX_FILE_SIZE
    app.config['PORT'] = Settings.PORT
    app.config['DEBUG'] = Settings.DEBUG
    # Flask 3 moved key sorting onto the JSON provider.
    app.json.sort_keys = False

    logging.basicConfig(
        level=logging.DEBUG if Settings.DEBUG else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    @app.errorhandler(RequestEntityTooLarge)
    def handle_too_large(error):
        return jsonify({'error': f'Upload exceeds the {Settings.MAX_FILE_SIZE} byte limit'}), 413

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': error.description}), error.code
        return error

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        logger.exception("Unhandled application error")
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        raise error

    from src.web.routes import api_routes, web_routes
    app.register_blueprint(api_routes)
    app.register_blueprint(web_routes)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    return app