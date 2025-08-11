#!/usr/bin/env python3
"""
Simple server startup script.
"""
import uvicorn
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Starting HWP API Server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🎯 New extraction endpoints:")
    print("   - POST /api/v1/extract/hwp-to-json")
    print("   - POST /api/v1/extract/hwp-to-text")
    print("   - POST /api/v1/extract/hwp-to-markdown")
    print("\nPress Ctrl+C to stop the server")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )