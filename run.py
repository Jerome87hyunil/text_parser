#!/usr/bin/env python
"""
Server runner for Render deployment
"""
import os
import sys
import uvicorn

if __name__ == "__main__":
    # Use PORT environment variable from Render
    port = int(os.environ.get("PORT", 10000))
    
    print(f"Starting server on port {port}", flush=True)
    sys.stdout.flush()
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )