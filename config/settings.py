import os
from pathlib import Path

class Settings:
    CAPGEMINI_API_KEY: str = os.getenv("CAPGEMINI_API_KEY", "")
    CAPGEMINI_API_URL: str = os.getenv("CAPGEMINI_API_URL", "https://api.generative.engine.capgemini.com/v1")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    PORT: int = int(os.getenv("PORT", "5000"))
    UPLOAD_FOLDER: Path = Path(os.getenv("UPLOAD_FOLDER", "./uploads"))
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "2000"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "2000"))
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".txt", ".md"}
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    @classmethod
    def validate(cls):
        if not cls.CAPGEMINI_API_KEY:
            raise ValueError("CAPGEMINI_API_KEY required")
        cls.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        (cls.UPLOAD_FOLDER / ".gitkeep").touch(exist_ok=True)

try:
    Settings.validate()
except ValueError:
    pass