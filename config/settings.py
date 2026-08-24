import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

class Settings:
    # API Configuration
    CAPGEMINI_API_KEY: str = os.getenv("CAPGEMINI_API_KEY", "")
    CAPGEMINI_API_URL: str = os.getenv("CAPGEMINI_API_URL", "wss://ws.generative.engine.capgemini.com/")
    OPENAI_API_URL: str = os.getenv("OPENAI_API_URL", "https://openai.generative.engine.capgemini.com/v1")

    # Model Configuration
    MODEL_NAME: str = os.getenv("MODEL_NAME", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "bedrock")
    MODEL_INTERFACE: str = os.getenv("MODEL_INTERFACE", "multimodal")
    MODEL_ADAPTER_VERSION: str = os.getenv("MODEL_ADAPTER_VERSION", "v2")

    # Application Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    PORT: int = int(os.getenv("PORT", "5000"))
    UPLOAD_FOLDER: Path = Path(os.getenv("UPLOAD_FOLDER", str(PROJECT_ROOT / "uploads")))
    if not UPLOAD_FOLDER.is_absolute():
        UPLOAD_FOLDER = PROJECT_ROOT / UPLOAD_FOLDER
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))
    API_TIMEOUT: float = float(os.getenv("API_TIMEOUT", "60"))
    WEB_SEARCH_ENABLED: bool = os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true"
    WEB_SEARCH_TIMEOUT: float = float(os.getenv("WEB_SEARCH_TIMEOUT", "8"))
    WEB_SEARCH_MAX_RESULTS: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))

    # Model Parameters
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
    TOP_P: float = float(os.getenv("TOP_P", "0.9"))
    STREAMING: bool = os.getenv("STREAMING", "true").lower() == "true"

    # RAG Settings
    WORKSPACE_ID: str = os.getenv("WORKSPACE_ID", "")
    DOC_LIMIT: int = int(os.getenv("DOC_LIMIT", "3"))

    # Chunking
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "2000"))
    ALLOWED_EXTENSIONS: set = {".docx", ".txt", ".md"}

    # Embeddings
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")

    @classmethod
    def validate(cls):
        if not cls.CAPGEMINI_API_KEY:
            raise ValueError("CAPGEMINI_API_KEY required")
        cls.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        (cls.UPLOAD_FOLDER / ".gitkeep").touch(exist_ok=True)
