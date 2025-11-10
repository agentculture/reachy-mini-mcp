#!/usr/bin/env python3
"""
Hearing Event Client - External application to receive events

This client connects to the Unix Domain Socket and receives
hearing events emitted by the reachy-hearing service.

Usage:
    python3 hearing_event_client.py

The client will automatically reconnect if the connection is lost.
"""

import socket
import json
import time
import sys


class HearingEventClient:
    """Client to receive hearing events via Unix Domain Socket"""
    
    def __init__(self, socket_path="/tmp/reachy_sockets/hearing.sock"):
        self.socket_path = socket_path
        self.socket = None
        self.running = False
        
    def connect(self):
        """Connect to the Unix Domain Socket"""
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket.connect(self.socket_path)
                print(f"[INFO] Connected to {self.socket_path}")
                return True
            except (FileNotFoundError, ConnectionRefusedError) as e:
                if attempt < max_retries - 1:
                    print(f"[WARN] Connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"[INFO] Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print(f"[ERROR] Failed to connect after {max_retries} attempts")
                    return False
            except Exception as e:
                print(f"[ERROR] Unexpected error connecting: {e}")
                return False
                
        return False
        
    def disconnect(self):
        """Disconnect from the socket"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            print("[INFO] Disconnected")
            
    def receive_events(self):
        """Receive and process events"""
        buffer = ""
        
        while self.running:
            try:
                # Receive data
                data = self.socket.recv(4096)
                
                if not data:
                    print("[WARN] Connection closed by server")
                    return False
                    
                # Decode and add to buffer
                buffer += data.decode('utf-8')
                
                # Process complete messages (separated by newlines)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self.handle_event(line)
                        
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError) as e:
                print(f"[WARN] Connection lost: {e}")
                return False
            except Exception as e:
                print(f"[ERROR] Error receiving data: {e}")
                return False
                
        return True
        
    def handle_event(self, message):
        """Handle a received event"""
        try:
            event = json.loads(message)
            
            # Pretty print the event
            timestamp = event.get("timestamp", "N/A")
            event_type = event.get("type", "unknown")
            data = event.get("data", {})
            
            print(f"\n{'='*60}")
            print(f"[EVENT] Type: {event_type}")
            print(f"[EVENT] Time: {timestamp}")
            print(f"[EVENT] Data: {json.dumps(data, indent=2)}")
            print(f"{'='*60}\n")
            
            # You can add custom handling for specific event types here
            if event_type == "speech_detected":
                self.handle_speech(data)
            elif event_type == "sound_detected":
                self.handle_sound(data)
            elif event_type == "keyword_spotted":
                self.handle_keyword(data)
                
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse event: {e}")
        except Exception as e:
            print(f"[ERROR] Error handling event: {e}")
            
    def handle_speech(self, data):
        """Handle speech detection event"""
        text = data.get("text", "")
        confidence = data.get("confidence", 0)
        print(f"  → Speech: '{text}' (confidence: {confidence:.2%})")
        
    def handle_sound(self, data):
        """Handle sound detection event"""
        sound_type = data.get("type", "unknown")
        intensity = data.get("intensity", 0)
        direction = data.get("direction", "unknown")
        print(f"  → Sound: {sound_type} from {direction} (intensity: {intensity})")
        
    def handle_keyword(self, data):
        """Handle keyword spotted event"""
        keyword = data.get("keyword", "")
        confidence = data.get("confidence", 0)
        print(f"  → Keyword spotted: '{keyword}' (confidence: {confidence:.2%})")
        
    def start(self):
        """Start the client with auto-reconnect"""
        print("[INFO] Starting Hearing Event Client...")
        print(f"[INFO] Socket path: {self.socket_path}")
        print("[INFO] Press Ctrl+C to exit\n")
        
        self.running = True
        
        try:
            while self.running:
                # Connect to server
                if not self.connect():
                    print("[ERROR] Failed to connect. Exiting...")
                    break
                    
                # Receive events
                success = self.receive_events()
                
                # Disconnect
                self.disconnect()
                
                # Auto-reconnect if still running
                if self.running and not success:
                    print("[INFO] Attempting to reconnect in 3 seconds...")
                    time.sleep(3)
                else:
                    break
                    
        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")
        except Exception as e:
            print(f"[ERROR] Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
            self.disconnect()
            
        print("[INFO] Client stopped")


if __name__ == "__main__":
    client = HearingEventClient()
    client.start()
