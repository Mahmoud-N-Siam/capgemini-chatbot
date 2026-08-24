import logging
import uuid
from typing import Any, Dict, List, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import Settings

logger = logging.getLogger(__name__)

class APIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class CapgeminiClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or Settings.CAPGEMINI_API_KEY
        self.base_url = base_url or Settings.CAPGEMINI_API_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'CapgeminiChatbot/1.0'
        })

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10),
           retry=retry_if_exception_type((requests.exceptions.ConnectionError,
                                           requests.exceptions.Timeout, requests.exceptions.HTTPError)))
    def _make_request(self, method: str, endpoint: str, payload: Optional[Dict] = None,
                      params: Optional[Dict] = None, timeout: int = 30) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            response = self.session.request(method=method, url=url, json=payload, params=params, timeout=timeout)
            if response.status_code == 429:
                retry_after = int(response.headers.get('retry-after', 5))
                raise requests.exceptions.HTTPError(f"Rate limited: {retry_after}s")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            details = {'url': url, 'status_code': status_code, 'response': e.response.text if e.response else None}
            raise APIError(f"API request failed with status {status_code}", status_code=status_code, details=details)
        except requests.exceptions.Timeout:
            raise APIError("Request timed out", status_code=408)
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {str(e)}")

    def generate_text(self, prompt: str, max_tokens: Optional[int] = None,
                      temperature: Optional[float] = None, system_message: Optional[str] = None) -> str:
        payload = {'prompt': prompt, 'max_tokens': max_tokens or Settings.MAX_TOKENS,
                   'temperature': temperature or Settings.TEMPERATURE}
        if system_message:
            payload['system'] = system_message
        try:
            response = self._make_request('POST', 'generate', payload)
            return response.get('text', '') or response.get('content', '')
        except APIError as e:
            logger.error(f"Text generation failed: {e}")
            raise

    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None,
             temperature: Optional[float] = None, model: Optional[str] = None):
        payload = {'messages': messages, 'max_tokens': max_tokens or Settings.MAX_TOKENS,
                   'temperature': temperature or Settings.TEMPERATURE}
        if model:
            payload['model'] = model
        try:
            response = self._make_request('POST', 'chat', payload)
            content = response.get('content', '') or response.get('message', {}).get('content', '') or \
                     response.get('choices', [{}])[0].get('message', {}).get('content', '')
            return {'id': str(uuid.uuid4()), 'content': content, 'role': 'assistant',
                    'model': model or response.get('model')}
        except APIError as e:
            logger.error(f"Chat failed: {e}")
            raise

    def get_models(self) -> List[Dict[str, Any]]:
        try:
            response = self._make_request('GET', 'models')
            return response.get('data', response.get('models', []))
        except APIError as e:
            logger.error(f"Failed to get models: {e}")
            return []

    def health_check(self) -> bool:
        try:
            self._make_request('GET', 'health')
            return True
        except APIError:
            return False