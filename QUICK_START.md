# 🚀 Quick Start Guide - HWP API

## 📦 Prerequisites

- Docker & Docker Compose (권장)
- 또는 Python 3.11+ 

## 🎯 1분 안에 시작하기

### 방법 1: Docker Compose (가장 쉬운 방법)

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/hwp_api.git
cd hwp_api

# 2. 개발 환경 시작
docker-compose -f docker-compose.dev.yml up

# 3. API 테스트 (새 터미널에서)
curl http://localhost:8000/health
```

✅ **완료!** API가 http://localhost:8000 에서 실행 중입니다.

### 방법 2: 로컬 Python 환경

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/hwp_api.git
cd hwp_api

# 2. Python 가상환경 생성
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. Redis 시작 (Docker 사용)
docker run -d -p 6379:6379 redis:7-alpine

# 5. API 서버 시작
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 🧪 API 테스트하기

### 1. 웹 브라우저로 테스트

1. **테스트 페이지 열기**: `examples/javascript/index.html` 파일을 브라우저에서 열기
2. **파일 선택**: HWP, HWPX, 또는 PDF 파일 선택
3. **추출**: "텍스트 추출" 버튼 클릭

### 2. cURL로 테스트

```bash
# HWP 파일을 JSON으로 추출
curl -X POST "http://localhost:8000/api/v1/extract/hwp-to-json" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.hwp"

# 텍스트로 추출
curl -X POST "http://localhost:8000/api/v1/extract/hwp-to-text" \
  -F "file=@document.hwp"
```

### 3. Python 클라이언트로 테스트

```bash
# Python 클라이언트 예제 실행
cd examples/python
pip install -r requirements.txt
python client.py document.hwp --format json
```

### 4. Postman으로 테스트

1. Postman 열기
2. Import → `postman_collection.json` 파일 선택
3. Environment 변수 설정:
   - `base_url`: http://localhost:8000
4. 원하는 요청 실행

## 📊 API 문서 확인

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## 🔧 환경 설정

### 필수 환경 변수

`.env` 파일 생성:

```env
# 필수 설정
SECRET_KEY=your-secret-key-here
REDIS_URL=redis://localhost:6379/0

# 선택 설정
DEBUG=true
LOG_LEVEL=DEBUG
CORS_ORIGINS=*
MAX_UPLOAD_SIZE=104857600  # 100MB
CACHE_ENABLED=true
RATE_LIMIT_ENABLED=false  # 개발 환경에서는 비활성화
```

### CORS 설정 (웹앱 통합용)

```env
# 모든 origin 허용 (개발용)
CORS_ORIGINS=*

# 특정 origin만 허용 (프로덕션)
CORS_ORIGINS=http://localhost:3000,https://your-app.com
```

## 🌐 웹 애플리케이션과 통합

### React 예제

```jsx
// FileExtractor.jsx
import React, { useState } from 'react';

function FileExtractor() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);

  const handleExtract = async () => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('http://localhost:8000/api/v1/extract/hwp-to-json', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    setResult(data);
  };

  return (
    <div>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={handleExtract}>Extract</button>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}
```

### Vue.js 예제

```vue
<template>
  <div>
    <input type="file" @change="handleFileSelect" />
    <button @click="extractFile">Extract</button>
    <pre v-if="result">{{ result }}</pre>
  </div>
</template>

<script>
export default {
  data() {
    return {
      file: null,
      result: null
    };
  },
  methods: {
    handleFileSelect(event) {
      this.file = event.target.files[0];
    },
    async extractFile() {
      const formData = new FormData();
      formData.append('file', this.file);

      const response = await fetch('http://localhost:8000/api/v1/extract/hwp-to-json', {
        method: 'POST',
        body: formData
      });

      this.result = await response.json();
    }
  }
};
</script>
```

## 🐳 Docker 명령어 참고

```bash
# 서비스 시작
docker-compose -f docker-compose.dev.yml up

# 백그라운드 실행
docker-compose -f docker-compose.dev.yml up -d

# 로그 확인
docker-compose -f docker-compose.dev.yml logs -f api

# 서비스 중지
docker-compose -f docker-compose.dev.yml down

# 데이터 포함 완전 삭제
docker-compose -f docker-compose.dev.yml down -v
```

## 📁 프로젝트 구조

```
hwp_api/
├── app/                    # 메인 애플리케이션
│   ├── api/               # API 엔드포인트
│   ├── core/              # 핵심 설정
│   ├── models/            # 데이터 모델
│   └── services/          # 비즈니스 로직
├── examples/              # 사용 예제
│   ├── javascript/        # JavaScript/HTML 예제
│   └── python/            # Python 클라이언트
├── tests/                 # 테스트 코드
├── docker-compose.dev.yml # 개발 환경 설정
├── requirements.txt       # Python 의존성
└── API_INTEGRATION_GUIDE.md # 상세 통합 가이드
```

## 🔍 디버깅

### API 로그 확인
```bash
# Docker 사용 시
docker-compose -f docker-compose.dev.yml logs -f api

# 로컬 실행 시
uvicorn app.main:app --reload --log-level debug
```

### Redis 연결 테스트
```bash
redis-cli ping
# 응답: PONG
```

### 데이터베이스 확인 (Docker 사용 시)
- Adminer: http://localhost:8080
- Server: `postgres`
- Username: `hwp_dev`
- Password: `devpass123`
- Database: `hwp_api_dev`

## 🆘 도움이 필요하신가요?

- **API 문서**: http://localhost:8000/docs
- **통합 가이드**: [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md)
- **GitHub Issues**: https://github.com/your-org/hwp_api/issues

## ⚡ 성능 팁

1. **캐싱 활용**: 동일한 파일 반복 요청 시 자동 캐싱
2. **비동기 처리**: 10MB 이상 파일은 async 엔드포인트 사용
3. **압축**: 큰 응답은 gzip 압축 지원

## 🔐 보안 참고사항

개발 환경 설정은 **개발 용도로만** 사용하세요:
- CORS가 모든 origin 허용 (`*`)
- Rate limiting 비활성화
- Debug 모드 활성화

프로덕션 환경에서는 반드시 보안 설정을 강화하세요.