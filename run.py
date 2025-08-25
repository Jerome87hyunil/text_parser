#!/usr/bin/env python
"""
Server runner for Render deployment
"""
import os
import uvicorn

if __name__ == "__main__":
    # Use PORT environment variable from Render
    port = int(os.environ.get("PORT", 8000))
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )