#!/usr/bin/env python3
"""
Production startup script that runs both Streamlit and FastAPI concurrently.
This enables both the web UI and the Stripe webhook endpoint.

Usage:
    python start_services.py
    
Environment:
    PORT - Main port for Streamlit (default: 8501)
    API_PORT - Port for FastAPI/webhooks (default: 8000)
"""

import os
import subprocess
import sys
import signal
import time

def main():
    # Get ports from environment
    streamlit_port = os.getenv("PORT", "8501")
    api_port = os.getenv("API_PORT", "8000")
    
    print(f"🚀 Starting Promptly Services...")
    print(f"   Streamlit: port {streamlit_port}")
    print(f"   API Server: port {api_port}")
    
    # Start FastAPI in background
    api_process = subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "api_server:app",
        "--host", "0.0.0.0",
        "--port", api_port
    ])
    
    # Start Streamlit in foreground
    streamlit_process = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run",
        "app.py",
        "--server.port", streamlit_port,
        "--server.address", "0.0.0.0",
        "--server.headless", "true"
    ])
    
    # Handle graceful shutdown
    def shutdown(signum, frame):
        print("\n👋 Shutting down services...")
        api_process.terminate()
        streamlit_process.terminate()
        api_process.wait()
        streamlit_process.wait()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    
    # Wait for processes
    try:
        while True:
            # Check if either process has died
            if api_process.poll() is not None:
                print("❌ API server stopped unexpectedly")
                streamlit_process.terminate()
                sys.exit(1)
            if streamlit_process.poll() is not None:
                print("❌ Streamlit stopped unexpectedly")
                api_process.terminate()
                sys.exit(1)
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)

if __name__ == "__main__":
    main()
