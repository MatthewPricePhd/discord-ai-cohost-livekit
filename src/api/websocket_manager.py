"""
WebSocket connection management for OpenAI Realtime API
"""
import asyncio
import json
from typing import Optional, Dict, Any, Callable, List
from enum import Enum

import websockets
from websockets.client import WebSocketClientProtocol

from ..config import get_logger, settings

logger = get_logger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class WebSocketManager:
    """Manages WebSocket connection to OpenAI Realtime API"""
    
    def __init__(self, model_override: Optional[str] = None):
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.state = ConnectionState.DISCONNECTED
        if model_override:
            self.url = f"wss://api.openai.com/v1/realtime?model={model_override}"
        else:
            self.url = settings.openai_realtime_url
        self.headers = settings.openai_realtime_headers
        
        # Event handlers
        self.message_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self.connection_handlers: List[Callable[[ConnectionState], None]] = []
        self.error_handlers: List[Callable[[Exception], None]] = []
        
        # Reconnection settings
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2.0
        self.reconnect_backoff = 1.5
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Message queue for offline messages
        self._message_queue: List[Dict[str, Any]] = []
        self._max_queue_size = 100
        
    def add_message_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], None]):
        """Add a message handler for specific event types"""
        self.message_handlers[event_type] = handler
        logger.debug("Added message handler", event_type=event_type)
    
    def add_connection_handler(self, handler: Callable[[ConnectionState], None]):
        """Add a connection state change handler"""
        self.connection_handlers.append(handler)
        logger.debug("Added connection handler")
    
    def add_error_handler(self, handler: Callable[[Exception], None]):
        """Add an error handler"""
        self.error_handlers.append(handler)
        logger.debug("Added error handler")
    
    async def connect(self) -> bool:
        """Connect to OpenAI Realtime API"""
        if self.state == ConnectionState.CONNECTED:
            logger.debug("Already connected to WebSocket")
            return True
        
        try:
            self._set_state(ConnectionState.CONNECTING)
            logger.info("Connecting to OpenAI Realtime API", url=self.url)
            
            self.websocket = await websockets.connect(
                self.url,
                additional_headers=self.headers,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self._set_state(ConnectionState.CONNECTED)
            logger.info("Successfully connected to OpenAI Realtime API")
            
            # Start message handling task
            asyncio.create_task(self._message_loop())
            
            # Send queued messages
            await self._send_queued_messages()
            
            return True
            
        except Exception as e:
            self._set_state(ConnectionState.FAILED)
            logger.error("Failed to connect to OpenAI Realtime API", error=str(e))
            self._trigger_error_handlers(e)
            
            # Start reconnection if not already running
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())
            
            return False
    
    async def disconnect(self):
        """Disconnect from OpenAI Realtime API"""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            logger.info("Disconnected from OpenAI Realtime API")
        
        self._set_state(ConnectionState.DISCONNECTED)
        self.websocket = None
    
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send a message to the API"""
        if self.state != ConnectionState.CONNECTED or not self.websocket:
            # Queue message for later sending
            if len(self._message_queue) < self._max_queue_size:
                self._message_queue.append(message)
                logger.debug("Queued message for later sending", 
                           queue_size=len(self._message_queue))
            else:
                logger.warning("Message queue full, dropping message")
            return False
        
        try:
            message_json = json.dumps(message)
            await self.websocket.send(message_json)
            logger.debug("Sent message to API", message_type=message.get('type'))
            return True
            
        except Exception as e:
            logger.error("Failed to send message", error=str(e))
            self._trigger_error_handlers(e)
            
            # Try to reconnect
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())
            
            return False
    
    async def _message_loop(self):
        """Main message receiving loop"""
        try:
            while self.state == ConnectionState.CONNECTED and self.websocket:
                try:
                    message_raw = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=30.0
                    )
                    
                    message = json.loads(message_raw)
                    await self._handle_message(message)
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await self.websocket.ping()
                    
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket connection closed by server")
                    break
                    
                except Exception as e:
                    logger.error("Error in message loop", error=str(e))
                    self._trigger_error_handlers(e)
                    break
        
        finally:
            if self.state == ConnectionState.CONNECTED:
                self._set_state(ConnectionState.DISCONNECTED)
                
                # Start reconnection
                if not self._reconnect_task or self._reconnect_task.done():
                    self._reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message from API"""
        message_type = message.get('type')
        
        logger.debug("Received message from API", message_type=message_type)
        
        # Call specific handler if available
        if message_type in self.message_handlers:
            try:
                await asyncio.create_task(
                    self._call_handler(self.message_handlers[message_type], message)
                )
            except Exception as e:
                logger.error("Error in message handler", 
                           message_type=message_type, 
                           error=str(e))
                self._trigger_error_handlers(e)
        else:
            logger.debug("No handler for message type", message_type=message_type)
    
    async def _call_handler(self, handler: Callable, *args):
        """Call handler function, supporting both sync and async"""
        if asyncio.iscoroutinefunction(handler):
            await handler(*args)
        else:
            handler(*args)
    
    async def _reconnect_loop(self):
        """Handle automatic reconnection with exponential backoff"""
        attempt = 0
        delay = self.reconnect_delay
        
        while attempt < self.max_reconnect_attempts and self.state != ConnectionState.CONNECTED:
            attempt += 1
            self._set_state(ConnectionState.RECONNECTING)
            
            logger.info("Attempting to reconnect", 
                       attempt=attempt, 
                       max_attempts=self.max_reconnect_attempts,
                       delay=delay)
            
            await asyncio.sleep(delay)
            
            if await self.connect():
                logger.info("Reconnection successful", attempt=attempt)
                return
            
            delay *= self.reconnect_backoff
            delay = min(delay, 60.0)  # Cap at 60 seconds
        
        logger.error("Reconnection failed after all attempts", 
                    attempts=self.max_reconnect_attempts)
        self._set_state(ConnectionState.FAILED)
    
    async def _send_queued_messages(self):
        """Send any queued messages"""
        if not self._message_queue:
            return
        
        logger.info("Sending queued messages", count=len(self._message_queue))
        
        messages_to_send = self._message_queue.copy()
        self._message_queue.clear()
        
        for message in messages_to_send:
            success = await self.send_message(message)
            if not success:
                # Re-queue failed messages at front
                self._message_queue.insert(0, message)
                break
    
    def _set_state(self, state: ConnectionState):
        """Update connection state and notify handlers"""
        if self.state != state:
            old_state = self.state
            self.state = state
            
            logger.info("Connection state changed", 
                       old_state=old_state.value, 
                       new_state=state.value)
            
            # Notify connection handlers
            for handler in self.connection_handlers:
                try:
                    asyncio.create_task(self._call_handler(handler, state))
                except Exception as e:
                    logger.error("Error in connection handler", error=str(e))
    
    def _trigger_error_handlers(self, error: Exception):
        """Trigger all error handlers"""
        for handler in self.error_handlers:
            try:
                asyncio.create_task(self._call_handler(handler, error))
            except Exception as e:
                logger.error("Error in error handler", error=str(e))
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.state == ConnectionState.CONNECTED
    
    @property
    def connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        return {
            "state": self.state.value,
            "url": self.url,
            "is_connected": self.is_connected,
            "queue_size": len(self._message_queue),
            "websocket_closed": self.websocket is None or getattr(self.websocket, 'closed', True)
        }