import logging
from datetime import datetime
from pathlib import Path
from typing import Union
import docx

logger = logging.getLogger(__name__)

class DocumentProcessor:
    @staticmethod
    def extract_text(file_path: Union[str, Path]) -> str:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        extension = file_path.suffix.lower()
        if extension == '.docx':
            return DocumentProcessor._extract_docx(file_path)
        elif extension in ('.txt', '.md'):
            return DocumentProcessor._extract_text_file(file_path)
        else:
            raise ValueError(f"Unsupported file format: {extension}")

    @staticmethod
    def _extract_docx(file_path: Path) -> str:
        try:
            doc = docx.Document(str(file_path))
            return "\n".join([para.text for para in doc.paragraphs]).strip()
        except Exception as e:
            raise ValueError(f"Failed to process DOCX: {str(e)}")

    @staticmethod
    def _extract_text_file(file_path: Path) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            raise ValueError(f"Failed to read text file: {str(e)}")

    @staticmethod
    def get_file_info(file_path: Union[str, Path]) -> dict:
        file_path = Path(file_path)
        stat = file_path.stat()
        return {
            'file_name': file_path.name,
            'file_path': str(file_path),
            'file_size': stat.st_size,
            'file_type': file_path.suffix.lower(),
            'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }