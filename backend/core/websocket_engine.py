"""WebSocket Engine - Real-time Audio Streaming

Production-grade WebSocket server for streaming audio between client and server
with support for bidirectional real-time communication (barge-in detection).
"""

import asyncio
import logging
import json
from typing import Dict, Callable, Optional, Set
from dataclasses import dataclass, asdict
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class AudioMessage:
    """WebSocket audio message structure"""
    type: str  # 'audio', 'text', 'control'
    data: bytes  # Audio data (PCM)
    timestamp: float  # Server timestamp
    message_id: str  # Unique message identifier
    sequence: int  # Sequence number for ordering

@dataclass
class WebSocketConfig:
    """WebSocket Configuration"""
    host: str = "0.0.0.0"
    port: int = 8765
    max_connections: int = 100
    buffer_size: int = 4096  # 4KB audio chunks
    heartbeat_interval: float = 30.0  # Seconds
    connection_timeout: float = 60.0  # Seconds
    enable_barge_in: bool = True
    audio_format: str = "pcm16"  # 16-bit PCM
    sample_rate: int = 24000  # 24kHz

class WebSocketEngine:
    """Real-time WebSocket streaming engine"""
    
    def __init__(self, config: Optional[WebSocketConfig] = None):
        """Initialize WebSocket Engine
        
        Args:
            config: WebSocketConfig object
        """
        self.config = config or WebSocketConfig()
        self.server = None
        self.connected_clients: Dict[str, 'ClientConnection'] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self.logger = logger
        self.callbacks: Dict[str, list[Callable]] = {
            'on_connect': [],
            'on_disconnect': [],
            'on_audio': [],
            'on_text': [],
            'on_barge_in': []
        }
        
    async def start(self) -> None:
        """Start WebSocket server"""
        try:
            import websockets
            from websockets.server import serve
            
            self.logger.info(
                f"Starting WebSocket server on {self.config.host}:{self.config.port}"
            )
            
            self.server = await serve(
                self.handle_connection,
                self.config.host,
                self.config.port,
                # RunPod WebSocket optimizations
                max_size=10_000_000,  # 10MB max message
                max_queue=64,  # Message queue
                compression=None,  # Disable compression for latency
                ping_interval=self.config.heartbeat_interval,
                ping_timeout=self.config.connection_timeout,
            )
            
            self.is_running = True
            self.logger.info("WebSocket server started successfully")
            
        except ImportError:
            self.logger.error("websockets library not found. Install: pip install websockets")
            raise
        except Exception as e:
            self.logger.error(f"Error starting WebSocket server: {str(e)}")
            raise
    
    async def handle_connection(self, websocket, path: str) -> None:
        """Handle new WebSocket connection
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        client_id = str(uuid.uuid4())[:8]
        connection = ClientConnection(client_id, websocket, self.config)
        
        self.connected_clients[client_id] = connection
        self.logger.info(f"Client connected: {client_id} (Total: {len(self.connected_clients)})")
        
        # Trigger connect callbacks
        for callback in self.callbacks['on_connect']:
            try:
                await callback(client_id, connection)
            except Exception as e:
                self.logger.error(f"Error in on_connect callback: {str(e)}")
        
        try:
            async for message in websocket:
                await self.process_message(client_id, connection, message)
        except Exception as e:
            self.logger.error(f"Error handling connection {client_id}: {str(e)}")
        finally:
            # Cleanup
            await connection.cleanup()
            del self.connected_clients[client_id]
            self.logger.info(f"Client disconnected: {client_id} (Total: {len(self.connected_clients)})")
            
            # Trigger disconnect callbacks
            for callback in self.callbacks['on_disconnect']:
                try:
                    await callback(client_id)
                except Exception as e:
                    self.logger.error(f"Error in on_disconnect callback: {str(e)}")
    
    async def process_message(self, client_id: str, connection: 'ClientConnection', message: bytes) -> None:
        """Process incoming WebSocket message
        
        Args:
            client_id: Client identifier
            connection: Client connection object
            message: Raw message data
        """
        try:
            # Try to parse as JSON (control messages)
            try:
                data = json.loads(message)
                message_type = data.get('type', 'text')
                
                if message_type == 'control':
                    await self.handle_control_message(client_id, data)
                elif message_type == 'text':
                    # Trigger text message callbacks
                    for callback in self.callbacks['on_text']:
                        try:
                            await callback(client_id, data.get('content', ''))
                        except Exception as e:
                            self.logger.error(f"Error in on_text callback: {str(e)}")
                elif message_type == 'barge_in':
                    # Client detected speech - interrupt TTS
                    if self.config.enable_barge_in:
                        for callback in self.callbacks['on_barge_in']:
                            try:
                                await callback(client_id, data.get('energy', 0.0))
                            except Exception as e:
                                self.logger.error(f"Error in on_barge_in callback: {str(e)}")
            except json.JSONDecodeError:
                # Binary audio data
                connection.buffer.append(message)
                connection.total_bytes_received += len(message)
                
                # Trigger audio callbacks
                for callback in self.callbacks['on_audio']:
                    try:
                        await callback(client_id, message)
                    except Exception as e:
                        self.logger.error(f"Error in on_audio callback: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"Error processing message from {client_id}: {str(e)}")
    
    async def handle_control_message(self, client_id: str, data: Dict) -> None:
        """Handle control messages (start, stop, etc.)
        
        Args:
            client_id: Client identifier
            data: Control message data
        """
        command = data.get('command', '')
        
        if command == 'start_session':
            self.logger.info(f"Session started: {client_id}")
        elif command == 'end_session':
            self.logger.info(f"Session ended: {client_id}")
        elif command == 'ping':
            # Heartbeat response
            await self.send_message(client_id, {'type': 'pong'})
    
    async def send_message(self, client_id: str, message: Dict) -> None:
        """Send message to specific client
        
        Args:
            client_id: Client identifier
            message: Message dictionary or bytes
        """
        if client_id not in self.connected_clients:
            self.logger.warning(f"Client {client_id} not connected")
            return
        
        try:
            connection = self.connected_clients[client_id]
            if isinstance(message, dict):
                await connection.websocket.send(json.dumps(message))
            else:
                await connection.websocket.send(message)
        except Exception as e:
            self.logger.error(f"Error sending message to {client_id}: {str(e)}")
    
    async def broadcast_audio(self, audio_data: bytes, exclude_client: Optional[str] = None) -> None:
        """Broadcast audio to all connected clients
        
        Args:
            audio_data: Audio chunk to broadcast
            exclude_client: Client ID to exclude (e.g., sender)
        """
        disconnected = []
        
        for client_id, connection in self.connected_clients.items():
            if exclude_client and client_id == exclude_client:
                continue
            
            try:
                await connection.websocket.send(audio_data)
            except Exception as e:
                self.logger.warning(f"Error broadcasting to {client_id}: {str(e)}")
                disconnected.append(client_id)
        
        # Cleanup disconnected clients
        for client_id in disconnected:
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """Register callback for events
        
        Args:
            event: Event name (on_connect, on_audio, etc.)
            callback: Async callback function
        """
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.info(f"Registered callback for {event}")
    
    async def get_status(self) -> Dict:
        """Get WebSocket engine status"""
        return {
            "is_running": self.is_running,
            "connected_clients": len(self.connected_clients),
            "max_connections": self.config.max_connections,
            "host": self.config.host,
            "port": self.config.port,
            "timestamp": datetime.now().isoformat()
        }
    
    async def shutdown(self) -> None:
        """Shutdown WebSocket server"""
        try:
            self.logger.info("Shutting down WebSocket server...")
            
            # Close all client connections
            for client_id, connection in list(self.connected_clients.items()):
                await connection.cleanup()
            
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            
            self.is_running = False
            self.logger.info("WebSocket server shut down successfully")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")

class ClientConnection:
    """Represents a single client connection"""
    
    def __init__(self, client_id: str, websocket, config: WebSocketConfig):
        self.client_id = client_id
        self.websocket = websocket
        self.config = config
        self.buffer: list[bytes] = []
        self.total_bytes_received = 0
        self.total_bytes_sent = 0
        self.connected_at = datetime.now()
    
    async def cleanup(self) -> None:
        """Cleanup client resources"""
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()
        except Exception:
            pass
        
        self.buffer.clear()

# Singleton instance
_websocket_instance: Optional[WebSocketEngine] = None

async def get_websocket_engine(config: Optional[WebSocketConfig] = None) -> WebSocketEngine:
    """Get or create WebSocket engine instance"""
    global _websocket_instance
    if _websocket_instance is None:
        _websocket_instance = WebSocketEngine(config)
    return _websocket_instance

async def shutdown_websocket_engine() -> None:
    """Shutdown WebSocket engine"""
    global _websocket_instance
    if _websocket_instance:
        await _websocket_instance.shutdown()
        _websocket_instance = None
