#!/usr/bin/env python3
"""
Hearing Event Emitter - Emits events via Unix Domain Socket

This service creates a Unix Domain Socket server that emits hearing events
to connected clients. External applications can connect to the socket to
receive real-time event notifications.
"""

import socket
import os
import json
import time
import sys
import threading
from datetime import datetime
from pathlib import Path


class HearingEventEmitter:
    """Emits hearing events via Unix Domain Socket"""
    
    def __init__(self, socket_path="/tmp/reachy_sockets/hearing.sock"):
        self.socket_path = socket_path
        self.clients = []
        self.server_socket = None
        self.running = False
        self.lock = threading.Lock()
        
    def setup_socket(self):
        """Create and configure the Unix Domain Socket"""
        # Ensure directory exists
        socket_dir = os.path.dirname(self.socket_path)
        Path(socket_dir).mkdir(parents=True, exist_ok=True)
        
        # Remove existing socket file if it exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        
        # Create Unix Domain Socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        
        # Set permissions to allow external connections
        os.chmod(self.socket_path, 0o666)
        
        self.server_socket.listen(5)
        print(f"[INFO] Listening on Unix socket: {self.socket_path}")
        
    def accept_connections(self):
        """Accept new client connections"""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    client_socket, _ = self.server_socket.accept()
                    with self.lock:
                        self.clients.append(client_socket)
                    print(f"[INFO] Client connected. Total clients: {len(self.clients)}")
                except socket.timeout:
                    continue
            except Exception as e:
                if self.running:
                    print(f"[ERROR] Error accepting connection: {e}")
                    
    def emit_event(self, event_type, data):
        """Emit an event to all connected clients"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }
        
        message = json.dumps(event) + "\n"
        message_bytes = message.encode('utf-8')
        
        with self.lock:
            disconnected = []
            for client in self.clients:
                try:
                    client.sendall(message_bytes)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    disconnected.append(client)
                    
            # Remove disconnected clients
            for client in disconnected:
                try:
                    client.close()
                except:
                    pass
                self.clients.remove(client)
                
            if disconnected:
                print(f"[INFO] Removed {len(disconnected)} disconnected client(s). Active: {len(self.clients)}")
    
    def generate_sample_events(self):
        """Generate sample hearing events for demonstration"""
        event_types = [
            ("speech_detected", {"text": "Hello", "confidence": 0.95, "language": "en"}),
            ("sound_detected", {"type": "clap", "intensity": 0.8, "direction": "front"}),
            ("keyword_spotted", {"keyword": "reachy", "confidence": 0.92}),
            ("noise_level", {"level": 65, "unit": "dB"}),
            ("voice_activity", {"active": True, "duration": 2.3}),
        ]
        
        counter = 0
        while self.running:
            time.sleep(3)  # Emit event every 3 seconds
            
            event_type, data = event_types[counter % len(event_types)]
            data["sequence"] = counter
            
            self.emit_event(event_type, data)
            print(f"[EVENT] Emitted: {event_type} - {data}")
            
            counter += 1
            
    def start(self):
        """Start the event emitter service"""
        print("[INFO] Starting Hearing Event Emitter...")
        self.running = True
        
        try:
            self.setup_socket()
            
            # Start connection acceptor thread
            accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
            accept_thread.start()
            
            # Generate and emit events
            self.generate_sample_events()
            
        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")
        except Exception as e:
            print(f"[ERROR] Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()
            
    def stop(self):
        """Stop the service and cleanup"""
        print("[INFO] Stopping service...")
        self.running = False
        
        # Close all client connections
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        # Remove socket file
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except:
                pass
                
        print("[INFO] Service stopped")


if __name__ == "__main__":
    emitter = HearingEventEmitter()
    emitter.start()
