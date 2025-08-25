# HWP/HWPX/PDF to JSON API - Integration Guide

## 📋 Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
- [Development Environment Setup](#development-environment-setup)
- [API Authentication](#api-authentication)
- [API Endpoints](#api-endpoints)
- [Integration Examples](#integration-examples)
- [Testing with Your Web App](#testing-with-your-web-app)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [CORS Configuration](#cors-configuration)
- [WebSocket Support](#websocket-support)
- [Performance Tips](#performance-tips)

## Overview

The HWP API provides RESTful endpoints for extracting text and structured data from HWP (한글), HWPX, and PDF files. It's designed for easy integration with web applications, mobile apps, and other services.

### Key Features
- 🔄 Synchronous and asynchronous processing
- 📊 Multiple output formats (JSON, Text, Markdown)
- 🔐 JWT-based authentication
- ⚡ Redis caching for improved performance
- 📈 Real-time processing with WebSocket support
- 🌐 CORS support for browser-based applications

## Quick Start

### Base URL
```
Development: http://localhost:8000
Production: https://your-api-domain.com
```

### Basic Request Example
```bash
# Extract text from HWP file
curl -X POST "http://localhost:8000/api/v1/extract/hwp-to-json" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.hwp"
```

## Development Environment Setup

### Option 1: Docker Compose (Recommended)

1. **Clone the repository**
```bash
git clone https://github.com/your-org/hwp_api.git
cd hwp_api
```

2. **Create environment file**
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Start services**
```bash
docker-compose up -d
```

4. **Verify installation**
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

### Option 2: Local Python Environment

1. **Install Python 3.11+**
```bash
python --version  # Should be 3.11 or higher
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Start Redis (required for caching)**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

4. **Run the API server**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Docker Compose for Development

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=true
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./app:/app/app  # Hot reload
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

Run with:
```bash
docker-compose -f docker-compose.dev.yml up
```

## API Authentication

### Public Endpoints (No Authentication Required)
- `/api/v1/extract/hwp-to-json`
- `/api/v1/extract/hwp-to-text`
- `/api/v1/extract/hwp-to-markdown`
- `/health`

### Protected Endpoints (JWT Required)

1. **Get Access Token**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass"
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

2. **Use Token in Requests**
```bash
curl -X POST "http://localhost:8000/api/v1/extract/auth/hwp-to-json" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -F "file=@document.hwp"
```

## API Endpoints

### 1. File Extraction Endpoints

#### Extract to JSON
**Endpoint:** `POST /api/v1/extract/hwp-to-json`

**Request:**
```http
POST /api/v1/extract/hwp-to-json
Content-Type: multipart/form-data

file: [binary file data]
include_metadata: true (optional)
include_styles: false (optional)
```

**Response:**
```json
{
  "status": "success",
  "filename": "document.hwp",
  "content": {
    "paragraphs": [
      {
        "text": "문서 내용",
        "style": "Normal",
        "level": 0
      }
    ],
    "tables": [],
    "images": [],
    "metadata": {
      "title": "문서 제목",
      "author": "작성자",
      "created_date": "2024-01-01T00:00:00",
      "pages": 10
    }
  },
  "processing_time": 0.234
}
```

#### Extract to Plain Text
**Endpoint:** `POST /api/v1/extract/hwp-to-text`

**Response:**
```json
{
  "status": "success",
  "filename": "document.hwp",
  "text": "문서의 전체 텍스트 내용...",
  "word_count": 1234,
  "processing_time": 0.123
}
```

#### Extract to Markdown
**Endpoint:** `POST /api/v1/extract/hwp-to-markdown`

**Response:**
```json
{
  "status": "success",
  "filename": "document.hwp",
  "markdown": "# 제목\n\n## 부제목\n\n본문 내용...",
  "processing_time": 0.156
}
```

### 2. Asynchronous Processing

#### Submit Async Job
**Endpoint:** `POST /api/v1/async/submit`

**Request:**
```json
{
  "file": "[base64 encoded file]",
  "filename": "document.hwp",
  "extraction_type": "json",
  "options": {
    "include_metadata": true
  }
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Task submitted successfully"
}
```

#### Check Job Status
**Endpoint:** `GET /api/v1/async/status/{task_id}`

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "result_url": "/api/v1/async/result/550e8400-e29b-41d4-a716-446655440000"
}
```

### 3. Streaming for Large Files

**Endpoint:** `POST /api/v1/stream/extract`

**Usage:**
```javascript
const eventSource = new EventSource('/api/v1/stream/extract');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.progress}%`);
  if (data.chunk) {
    processChunk(data.chunk);
  }
};
```

## Integration Examples

### JavaScript/TypeScript (Fetch API)

```javascript
// Simple file extraction
async function extractHWPFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('include_metadata', 'true');

  try {
    const response = await fetch('http://localhost:8000/api/v1/extract/hwp-to-json', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Extraction failed:', error);
    throw error;
  }
}

// With authentication
async function extractWithAuth(file, token) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('http://localhost:8000/api/v1/extract/auth/hwp-to-json', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  return response.json();
}
```

### React Component Example

```jsx
import React, { useState } from 'react';
import axios from 'axios';

function HWPExtractor() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setError(null);
  };

  const handleExtract = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(
        'http://localhost:8000/api/v1/extract/hwp-to-json',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data'
          },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            console.log(`Upload Progress: ${percentCompleted}%`);
          }
        }
      );

      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>HWP File Extractor</h2>
      
      <input 
        type="file" 
        accept=".hwp,.hwpx,.pdf"
        onChange={handleFileChange}
      />
      
      <button 
        onClick={handleExtract} 
        disabled={!file || loading}
      >
        {loading ? 'Extracting...' : 'Extract Text'}
      </button>

      {error && (
        <div style={{ color: 'red' }}>
          Error: {error}
        </div>
      )}

      {result && (
        <div>
          <h3>Extraction Result:</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default HWPExtractor;
```

### Python Integration

```python
import requests
import json

class HWPAPIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.token = None
    
    def authenticate(self, username, password):
        """Get JWT token for authenticated endpoints"""
        response = requests.post(
            f"{self.base_url}/api/v1/auth/token",
            data={"username": username, "password": password}
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            return True
        return False
    
    def extract_to_json(self, file_path, authenticated=False):
        """Extract HWP file to JSON format"""
        endpoint = "/api/v1/extract/hwp-to-json"
        if authenticated:
            endpoint = "/api/v1/extract/auth/hwp-to-json"
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            headers = {}
            if authenticated and self.token:
                headers['Authorization'] = f'Bearer {self.token}'
            
            response = requests.post(
                f"{self.base_url}{endpoint}",
                files=files,
                headers=headers
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Extraction failed: {response.text}")
    
    def extract_async(self, file_path):
        """Submit file for async processing"""
        import base64
        
        with open(file_path, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode()
        
        response = requests.post(
            f"{self.base_url}/api/v1/async/submit",
            json={
                "file": file_content,
                "filename": file_path.split('/')[-1],
                "extraction_type": "json"
            }
        )
        
        if response.status_code == 200:
            return response.json()["task_id"]
        else:
            raise Exception(f"Async submission failed: {response.text}")
    
    def check_async_status(self, task_id):
        """Check async task status"""
        response = requests.get(
            f"{self.base_url}/api/v1/async/status/{task_id}"
        )
        return response.json()
    
    def get_async_result(self, task_id):
        """Get async task result"""
        response = requests.get(
            f"{self.base_url}/api/v1/async/result/{task_id}"
        )
        return response.json()

# Usage example
if __name__ == "__main__":
    client = HWPAPIClient()
    
    # Simple extraction
    result = client.extract_to_json("document.hwp")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Async extraction for large files
    task_id = client.extract_async("large_document.hwp")
    print(f"Task submitted: {task_id}")
    
    # Poll for status
    import time
    while True:
        status = client.check_async_status(task_id)
        print(f"Status: {status['status']}, Progress: {status.get('progress', 0)}%")
        if status['status'] in ['completed', 'failed']:
            break
        time.sleep(2)
    
    if status['status'] == 'completed':
        result = client.get_async_result(task_id)
        print("Extraction completed!")
```

### Vue.js Integration

```vue
<template>
  <div id="hwp-extractor">
    <h2>HWP 파일 텍스트 추출기</h2>
    
    <div class="upload-section">
      <input 
        type="file" 
        @change="handleFileSelect"
        accept=".hwp,.hwpx,.pdf"
        :disabled="processing"
      />
      
      <button 
        @click="extractFile"
        :disabled="!selectedFile || processing"
      >
        {{ processing ? '처리 중...' : '텍스트 추출' }}
      </button>
    </div>

    <div v-if="error" class="error">
      {{ error }}
    </div>

    <div v-if="result" class="result">
      <h3>추출 결과:</h3>
      <div class="metadata" v-if="result.metadata">
        <p><strong>제목:</strong> {{ result.metadata.title }}</p>
        <p><strong>작성자:</strong> {{ result.metadata.author }}</p>
        <p><strong>페이지 수:</strong> {{ result.metadata.pages }}</p>
      </div>
      <div class="content">
        <pre>{{ result.text || JSON.stringify(result.content, null, 2) }}</pre>
      </div>
    </div>

    <div v-if="progress > 0 && progress < 100" class="progress">
      <div class="progress-bar" :style="{width: progress + '%'}">
        {{ progress }}%
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'HWPExtractor',
  data() {
    return {
      selectedFile: null,
      processing: false,
      result: null,
      error: null,
      progress: 0,
      apiUrl: process.env.VUE_APP_API_URL || 'http://localhost:8000'
    };
  },
  methods: {
    handleFileSelect(event) {
      this.selectedFile = event.target.files[0];
      this.error = null;
      this.result = null;
    },
    
    async extractFile() {
      if (!this.selectedFile) {
        this.error = '파일을 선택해주세요';
        return;
      }

      this.processing = true;
      this.error = null;
      this.progress = 0;

      const formData = new FormData();
      formData.append('file', this.selectedFile);

      try {
        const response = await axios.post(
          `${this.apiUrl}/api/v1/extract/hwp-to-json`,
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data'
            },
            onUploadProgress: (progressEvent) => {
              this.progress = Math.round(
                (progressEvent.loaded * 100) / progressEvent.total
              );
            }
          }
        );

        this.result = response.data;
        this.progress = 100;
      } catch (error) {
        this.error = error.response?.data?.detail || '추출 실패';
        this.progress = 0;
      } finally {
        this.processing = false;
      }
    },
    
    async extractLargeFile() {
      // For large files, use async processing
      const formData = new FormData();
      formData.append('file', this.selectedFile);

      try {
        // Submit async job
        const submitResponse = await axios.post(
          `${this.apiUrl}/api/v1/async/submit`,
          {
            file: await this.fileToBase64(this.selectedFile),
            filename: this.selectedFile.name,
            extraction_type: 'json'
          }
        );

        const taskId = submitResponse.data.task_id;
        
        // Poll for status
        const pollInterval = setInterval(async () => {
          const statusResponse = await axios.get(
            `${this.apiUrl}/api/v1/async/status/${taskId}`
          );
          
          this.progress = statusResponse.data.progress || 0;
          
          if (statusResponse.data.status === 'completed') {
            clearInterval(pollInterval);
            const resultResponse = await axios.get(
              `${this.apiUrl}/api/v1/async/result/${taskId}`
            );
            this.result = resultResponse.data;
            this.processing = false;
          } else if (statusResponse.data.status === 'failed') {
            clearInterval(pollInterval);
            this.error = '처리 실패';
            this.processing = false;
          }
        }, 2000);
      } catch (error) {
        this.error = error.message;
        this.processing = false;
      }
    },
    
    fileToBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = reject;
      });
    }
  }
};
</script>

<style scoped>
.error {
  color: red;
  margin: 10px 0;
}

.progress {
  width: 100%;
  height: 20px;
  background-color: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
  margin: 20px 0;
}

.progress-bar {
  height: 100%;
  background-color: #4CAF50;
  text-align: center;
  line-height: 20px;
  color: white;
  transition: width 0.3s;
}

.result {
  margin-top: 20px;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 5px;
}

.content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
```

## Testing with Your Web App

### 1. CORS Configuration

For browser-based applications, configure CORS in your `.env` file:

```bash
# .env
CORS_ORIGINS=http://localhost:3000,http://localhost:8080,https://your-webapp.com
```

Or allow all origins for development:
```bash
CORS_ORIGINS=*
```

### 2. Local Testing Setup

Create a test HTML file:

```html
<!DOCTYPE html>
<html>
<head>
    <title>HWP API Test</title>
</head>
<body>
    <h1>HWP API Integration Test</h1>
    
    <input type="file" id="fileInput" accept=".hwp,.hwpx,.pdf">
    <button onclick="testExtraction()">Test Extraction</button>
    
    <div id="result"></div>

    <script>
        async function testExtraction() {
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            
            if (!file) {
                alert('Please select a file');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch('http://localhost:8000/api/v1/extract/hwp-to-json', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                document.getElementById('result').innerHTML = 
                    '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            } catch (error) {
                document.getElementById('result').innerHTML = 
                    '<p style="color: red;">Error: ' + error.message + '</p>';
            }
        }
    </script>
</body>
</html>
```

### 3. Testing with Postman

Import the Postman collection (see `postman_collection.json` in the repo) or create requests manually:

1. **Create new request**
   - Method: POST
   - URL: `http://localhost:8000/api/v1/extract/hwp-to-json`

2. **Set up body**
   - Select "form-data"
   - Add key "file" with type "File"
   - Select your HWP file

3. **Send request and check response**

### 4. Integration Testing Checklist

- [ ] File upload works correctly
- [ ] Response format matches expectations
- [ ] Error handling for invalid files
- [ ] Authentication flow (if using protected endpoints)
- [ ] Large file handling (async processing)
- [ ] CORS headers are correct
- [ ] Rate limiting doesn't block legitimate requests
- [ ] Caching improves performance for repeated requests

## Error Handling

### Common Error Responses

```json
// 400 Bad Request - Invalid file type
{
  "detail": "File must be HWP, HWPX, or PDF format",
  "status_code": 400
}

// 413 Payload Too Large
{
  "detail": "File too large. Maximum size: 104857600 bytes",
  "status_code": 413
}

// 429 Too Many Requests
{
  "detail": "Rate limit exceeded. Try again in 60 seconds",
  "status_code": 429,
  "retry_after": 60
}

// 500 Internal Server Error
{
  "detail": "Failed to parse file",
  "status_code": 500,
  "error_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Error Handling Best Practices

```javascript
async function safeExtract(file) {
  try {
    const response = await fetch('/api/v1/extract/hwp-to-json', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      switch (response.status) {
        case 400:
          console.error('Invalid file format');
          break;
        case 413:
          console.error('File too large, use async endpoint');
          // Fallback to async processing
          return await submitAsyncJob(file);
        case 429:
          const retryAfter = error.retry_after || 60;
          console.error(`Rate limited, retry after ${retryAfter} seconds`);
          // Implement exponential backoff
          await sleep(retryAfter * 1000);
          return await safeExtract(file); // Retry
        case 500:
          console.error('Server error:', error.error_id);
          // Log error ID for debugging
          break;
      }
      
      throw new Error(error.detail);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Network error:', error);
    throw error;
  }
}
```

## Rate Limiting

### Default Limits
- Anonymous users: 100 requests/hour
- Authenticated users: 1000 requests/hour
- File extraction: 20 requests/hour (anonymous), 200 requests/hour (authenticated)

### Handling Rate Limits

```javascript
class APIClient {
  constructor() {
    this.retryCount = 0;
    this.maxRetries = 3;
  }
  
  async makeRequest(url, options) {
    try {
      const response = await fetch(url, options);
      
      if (response.status === 429) {
        const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
        
        if (this.retryCount < this.maxRetries) {
          this.retryCount++;
          console.log(`Rate limited, waiting ${retryAfter} seconds...`);
          await this.sleep(retryAfter * 1000);
          return this.makeRequest(url, options);
        }
      }
      
      this.retryCount = 0;
      return response;
    } catch (error) {
      throw error;
    }
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

## CORS Configuration

### Server-side Configuration

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-webapp.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Client-side Headers

```javascript
fetch('http://localhost:8000/api/v1/extract/hwp-to-json', {
  method: 'POST',
  credentials: 'include',  // Include cookies
  headers: {
    'Origin': 'http://localhost:3000'
  },
  body: formData
});
```

## WebSocket Support

For real-time updates during processing:

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Connected to WebSocket');
  
  // Submit extraction job
  ws.send(JSON.stringify({
    action: 'extract',
    file_id: 'abc123',
    type: 'json'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'progress':
      updateProgressBar(data.progress);
      break;
    case 'result':
      displayResult(data.content);
      break;
    case 'error':
      showError(data.message);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket connection closed');
};
```

## Performance Tips

### 1. Use Caching
Repeated requests for the same file will be served from cache:
```javascript
// The API automatically caches results
// Same file + same options = cached response
```

### 2. Compress Large Responses
```javascript
// Request compressed response
fetch('/api/v1/extract/hwp-to-json', {
  headers: {
    'Accept-Encoding': 'gzip, deflate'
  }
});
```

### 3. Use Async for Large Files
```javascript
// Files > 10MB should use async processing
if (file.size > 10 * 1024 * 1024) {
  const taskId = await submitAsyncJob(file);
  const result = await pollForResult(taskId);
} else {
  const result = await extractDirectly(file);
}
```

### 4. Batch Processing
```javascript
// Process multiple files efficiently
async function batchProcess(files) {
  const promises = files.map(file => 
    extractFile(file).catch(err => ({error: err, file: file.name}))
  );
  
  const results = await Promise.allSettled(promises);
  return results;
}
```

## Troubleshooting

### Common Issues and Solutions

1. **CORS Error**
   - Check that your origin is in the allowed origins list
   - Ensure credentials are handled correctly

2. **File Size Error**
   - Use async endpoint for files > 100MB
   - Consider chunked upload for very large files

3. **Authentication Failed**
   - Check token expiration
   - Refresh token if needed

4. **Slow Performance**
   - Enable caching
   - Use async processing for large files
   - Check network latency

5. **Character Encoding Issues**
   - Ensure UTF-8 encoding throughout
   - Check Content-Type headers

## Support and Resources

- API Documentation: http://localhost:8000/docs
- OpenAPI Schema: http://localhost:8000/openapi.json
- GitHub Issues: https://github.com/your-org/hwp_api/issues
- Email Support: api-support@your-domain.com

## License

MIT License - See LICENSE file for details