# 🔐 API Key 인증 시스템 사용 가이드

## 📋 개요

HWP API는 보안 강화를 위한 API Key 기반 인증 시스템을 제공합니다. 
공개 배포 시 무단 사용을 방지하고 사용량을 추적할 수 있습니다.

## 🚀 빠른 시작

### 1. 사용자 계정 생성 및 로그인

```bash
# JWT 토큰 발급 (테스트 계정)
curl -X POST "https://your-api.com/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass123"

# 응답
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### 2. API Key 생성

```bash
# API Key 발급 (JWT 토큰 필요)
curl -X POST "https://your-api.com/api/v1/api-keys/create" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key",
    "expires_in_days": 365
  }'

# 응답
{
  "id": 1,
  "key": "sk_live_abcdef123456...",  # 이 키를 안전하게 보관하세요!
  "name": "Production API Key",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "expires_at": "2025-01-01T00:00:00Z"
}
```

⚠️ **중요**: API Key는 생성 시에만 전체 값을 확인할 수 있습니다. 안전하게 보관하세요!

### 3. API Key로 인증하여 사용

두 가지 방법으로 API Key를 전달할 수 있습니다:

#### 방법 1: X-API-Key 헤더 (권장)
```bash
curl -X POST "https://your-api.com/api/v1/extract/protected/hwp-to-json" \
  -H "X-API-Key: sk_live_abcdef123456..." \
  -F "file=@document.hwp" \
  -F "extract_tables=true"
```

#### 방법 2: Authorization Bearer 헤더
```bash
curl -X POST "https://your-api.com/api/v1/extract/protected/hwp-to-json" \
  -H "Authorization: Bearer sk_live_abcdef123456..." \
  -F "file=@document.hwp" \
  -F "extract_tables=true"
```

## 📚 API Key 관리

### API Key 목록 조회
```bash
curl -X GET "https://your-api.com/api/v1/api-keys/list" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 응답 (보안을 위해 키는 앞 8자리만 표시)
[
  {
    "id": 1,
    "name": "Production API Key",
    "key_preview": "sk_live_...",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "expires_at": "2025-01-01T00:00:00Z",
    "last_used": "2024-01-15T10:30:00Z"
  }
]
```

### API Key 비활성화
```bash
# 임시 비활성화 (나중에 다시 활성화 가능)
curl -X PATCH "https://your-api.com/api/v1/api-keys/1/deactivate" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### API Key 활성화
```bash
# 비활성화된 키 다시 활성화
curl -X PATCH "https://your-api.com/api/v1/api-keys/1/activate" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### API Key 삭제
```bash
# 영구 삭제 (복구 불가)
curl -X DELETE "https://your-api.com/api/v1/api-keys/1" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🔒 보호된 엔드포인트

API Key가 필요한 엔드포인트들:

### HWP to JSON (보호됨)
```bash
POST /api/v1/extract/protected/hwp-to-json
```

### HWP to Text (보호됨)
```bash
POST /api/v1/extract/protected/hwp-to-text
```

### PDF to JSON (보호됨)
```bash
POST /api/v1/extract/protected/pdf-to-json
```

## 🌐 클라이언트 예제

### JavaScript/TypeScript
```javascript
// API Key를 환경 변수에 저장
const API_KEY = process.env.HWP_API_KEY;

// 파일 추출 요청
async function extractHWP(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('extract_tables', 'true');

  const response = await fetch('https://your-api.com/api/v1/extract/protected/hwp-to-json', {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY
    },
    body: formData
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  return await response.json();
}
```

### Python
```python
import requests
import os

API_KEY = os.environ.get('HWP_API_KEY')

def extract_hwp(file_path):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {'extract_tables': 'true'}
        headers = {'X-API-Key': API_KEY}
        
        response = requests.post(
            'https://your-api.com/api/v1/extract/protected/hwp-to-json',
            files=files,
            data=data,
            headers=headers
        )
        
        response.raise_for_status()
        return response.json()
```

### React
```jsx
import React, { useState } from 'react';

const API_KEY = process.env.REACT_APP_HWP_API_KEY;

function FileExtractor() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);

  const handleExtract = async () => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/v1/extract/protected/hwp-to-json', {
        method: 'POST',
        headers: {
          'X-API-Key': API_KEY
        },
        body: formData
      });

      if (!response.ok) {
        throw new Error('Extraction failed');
      }

      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <div>
      <input 
        type="file" 
        onChange={(e) => setFile(e.target.files[0])} 
        accept=".hwp,.hwpx"
      />
      <button onClick={handleExtract}>Extract</button>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}
```

## 🔐 보안 모범 사례

### 1. API Key 안전 관리
- **절대 코드에 하드코딩하지 마세요**
- 환경 변수 또는 보안 저장소 사용
- Git에 커밋하지 않도록 .gitignore 설정

### 2. 환경별 키 분리
```bash
# .env.development
HWP_API_KEY=sk_test_...

# .env.production
HWP_API_KEY=sk_live_...
```

### 3. 키 정기 갱신
- 주기적으로 API Key 갱신 (3-6개월)
- 만료 전 새 키 발급 및 교체

### 4. 접근 제한
- IP 화이트리스트 설정 (서버 설정)
- CORS 설정으로 도메인 제한
- Rate Limiting 적용

## 📊 사용량 추적

API Key별 사용량은 데이터베이스에 자동으로 기록됩니다:
- 마지막 사용 시간
- 총 요청 수
- 사용자별 통계

## 🆘 문제 해결

### "API key required" 오류
- API Key가 헤더에 포함되었는지 확인
- 올바른 헤더 이름 사용 확인 (X-API-Key 또는 Authorization)

### "Invalid or expired API key" 오류
- API Key가 정확한지 확인
- 키가 활성화되어 있는지 확인
- 만료 날짜 확인

### "Inactive user" 오류
- 사용자 계정이 활성화되어 있는지 확인
- 관리자에게 문의

## 📝 환경 변수 설정

프로덕션 배포 시 `.env.production`:
```env
# API Key 인증 활성화
API_KEY_REQUIRED=true

# Rate Limiting 설정
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# CORS 설정 (특정 도메인만 허용)
CORS_ORIGINS=https://your-domain.com,https://app.your-domain.com

# 보안 강화
SECRET_KEY=your-very-strong-secret-key-here
```

## 🔄 마이그레이션 가이드

기존 공개 API에서 API Key 인증으로 전환:

1. **단계적 전환**
   - 기존 엔드포인트 유지: `/api/v1/extract/*` (공개)
   - 새 보호 엔드포인트: `/api/v1/extract/protected/*` (API Key 필요)

2. **공지 기간**
   - 사용자에게 API Key 발급 안내
   - 전환 일정 공지

3. **완전 전환**
   - 모든 엔드포인트에 API Key 요구
   - 레거시 엔드포인트 제거

## 📞 지원

- API 문서: https://your-api.com/docs
- 이슈 제보: https://github.com/your-org/hwp_api/issues