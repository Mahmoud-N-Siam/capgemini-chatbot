import logging
import uuid
import json
import asyncio
from typing import Any, Dict, List, Optional, Callable
import websockets
from config.settings import Settings

logger = logging.getLogger(__name__)

class APIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class CapgeminiClient:
    """WebSocket-based client for Generative Engine API with Claude Sonnet 4.5"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or Settings.CAPGEMINI_API_KEY
        self.base_url = base_url or Settings.CAPGEMINI_API_URL

        if not self.api_key:
            raise ValueError("API key is required")

        logger.info(f"Initialized client with base_url: {self.base_url}")

    async def _connect(self):
        """Establish WebSocket connection"""
        try:
            logger.debug(f"Connecting to WebSocket: {self.base_url}")
            # Use additional_headers for websockets v13+
            websocket = await websockets.connect(
                self.base_url,
                additional_headers=[("x-api-key", self.api_key)]
            )
            logger.info("WebSocket connection established")
            return websocket
        except TypeError:
            # Fallback for older websockets versions
            logger.debug("Using extra_headers (older websockets version)")
            websocket = await websockets.connect(
                self.base_url,
                extra_headers={"x-api-key": self.api_key}
            )
            logger.info("WebSocket connection established (legacy)")
            return websocket
        except Exception as e:
            logger.error(f"Connection failed: {type(e).__name__}: {e}")
            raise

    async def _send_message(self, websocket, payload: Dict[str, Any]):
        """Send message through WebSocket"""
        message = json.dumps(payload)
        logger.debug(f"Sending message: {message[:200]}...")
        await websocket.send(message)

    async def _receive_messages(self, websocket, on_token: Optional[Callable] = None) -> str:
        """Receive and process streaming messages"""
        full_response = ""
        message_count = 0

        try:
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=Settings.API_TIMEOUT)
                except asyncio.TimeoutError as e:
                    raise APIError("Timed out waiting for model response") from e
                message_count += 1
                logger.debug(f"Received message {message_count}: {message[:200]}...")

                try:
                    data = json.loads(message)
                    is_final_response = data.get('action') == 'final_response'

                    # Handle different response formats
                    if 'data' in data:
                        data_content = data['data']

                        # Check for content field
                        if 'content' in data_content:
                            content = data_content['content']
                            if content:
                                if is_final_response:
                                    if not full_response:
                                        full_response = content
                                        if on_token:
                                            on_token(content)
                                    elif not content.startswith(full_response):
                                        full_response = content
                                    logger.debug(f"Processed final content: {content[:100]}...")
                                else:
                                    full_response += content
                                    if on_token:
                                        on_token(content)
                                    logger.debug(f"Added content: {content[:100]}...")

                        # Some API versions send tokens instead of content.
                        elif 'token' in data_content:
                            token = data_content['token']
                            if isinstance(token, dict) and 'value' in token:
                                token_value = token['value']
                            else:
                                token_value = str(token)

                            full_response += token_value
                            if on_token:
                                on_token(token_value)

                    # Check if response is complete
                    if (data.get('event') == 'complete' or data.get('type') == 'final'
                            or data.get('action') == 'final_response'):
                        logger.info("Received completion signal")
                        break

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                    logger.debug(f"Raw message: {message}")
                    continue

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
        except APIError:
            # Timeouts and protocol errors must reach the caller instead of
            # being reported as an empty response.
            raise
        except Exception as e:
            logger.error(f"Error receiving messages: {type(e).__name__}: {e}")

        logger.info(f"Received {message_count} messages, total response length: {len(full_response)}")
        return full_response

    async def generate_text_async(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        workspace_id: Optional[str] = None,
        on_token: Optional[Callable] = None,
        model: Optional[str] = None
    ) -> str:
        """Async text generation with Claude Sonnet 4.5"""

        session_id = str(uuid.uuid4())

        payload = {
            "action": "run",
            "modelInterface": Settings.MODEL_INTERFACE,
            "adapterInterfaceVersion": Settings.MODEL_ADAPTER_VERSION,
            "data": {
                "mode": "chain",
                "text": prompt,
                "modelName": model or Settings.MODEL_NAME,
                "provider": Settings.MODEL_PROVIDER,
                "sessionId": session_id,
                "files": [],
                "modelKwargs": {
                    "maxTokens": Settings.MAX_TOKENS if max_tokens is None else max_tokens,
                    "temperature": Settings.TEMPERATURE if temperature is None else temperature,
                    "streaming": Settings.STREAMING,
                    "topP": Settings.TOP_P
                }
            }
        }

        if system_prompt:
            payload["data"]["systemPrompt"] = system_prompt
        if workspace_id or Settings.WORKSPACE_ID:
            payload["data"]["workspaceId"] = workspace_id or Settings.WORKSPACE_ID
            payload["data"]["ragKwargs"] = {"docLimit": Settings.DOC_LIMIT}

        try:
            async with await self._connect() as websocket:
                await self._send_message(websocket, payload)
                response = await self._receive_messages(websocket, on_token)

                if not response:
                    raise APIError("Received empty response from API")

                return response

        except APIError:
            raise
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket error: {type(e).__name__}: {e}")
            raise APIError(f"WebSocket connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__}: {e}")
            raise APIError(f"Request failed: {str(e)}")

    def generate_text(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_message: Optional[str] = None
    ) -> str:
        """Synchronous wrapper for generate_text_async"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.generate_text_async(prompt, max_tokens, temperature, system_message)
            )
        finally:
            loop.close()

    async def chat_async(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        workspace_id: Optional[str] = None,
        on_token: Optional[Callable] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Async chat with conversation history"""

        system_prompt = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                user_messages.append(msg)

        prompt = "\n\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in user_messages
        ])

        response_content = await self.generate_text_async(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            workspace_id=workspace_id,
            on_token=on_token,
            model=model
        )

        return {
            'id': str(uuid.uuid4()),
            'content': response_content,
            'role': 'assistant',
            'model': model or Settings.MODEL_NAME
        }

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        on_token: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Synchronous wrapper for chat_async"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.chat_async(messages, max_tokens, temperature, model=model, on_token=on_token)
            )
        finally:
            loop.close()

    def health_check(self) -> bool:
        """Check API health via WebSocket"""
        async def _check():
            try:
                async with await self._connect() as websocket:
                    # Just connecting successfully is enough
                    logger.info("Health check: Connection successful")
                    return True
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_check())
        finally:
            loop.close()

    def get_models(self) -> List[Dict[str, Any]]:
        """Return current model configuration"""
        return [{
            "provider": Settings.MODEL_PROVIDER,
            "name": Settings.MODEL_NAME,
            "interface": Settings.MODEL_INTERFACE,
            "adapter_version": Settings.MODEL_ADAPTER_VERSION,
            "streaming": Settings.STREAMING
        }]
