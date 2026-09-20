#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from src.web.app import create_app
from config.settings import Settings

if __name__ == '__main__':
    Settings.validate()
    app = create_app()
    port = int(app.config.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=app.config.get('DEBUG', False))