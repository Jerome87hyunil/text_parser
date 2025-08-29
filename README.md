# HWP/HWPX/PDF to JSON API

한글(HWP), HWPX, PDF 파일에서 텍스트와 구조화된 데이터를 추출하는 고성능 RESTful API

## ✨ 주요 기능

- 📄 **다양한 파일 형식 지원**: HWP, HWPX, PDF
- 🔄 **다중 출력 형식**: JSON, Plain Text, Markdown
- ⚡ **고성능 처리**: Redis 캐싱, 비동기 처리
- 🔐 **보안**: JWT 인증, 파일 검증, Rate Limiting
- 📊 **모니터링**: Prometheus 메트릭, 상세 로깅
- 🌐 **웹앱 통합 지원**: CORS, WebSocket, 스트리밍
- 🆕 **향상된 HWP 파싱**: 8,000자 이상 추출 (기존 995자 → 8,749자, 780% 개선)

## 🚀 Quick Start

### Docker Compose로 1분 안에 시작하기

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/hwp_api.git
cd hwp_api

# 2. 개발 환경 시작
docker-compose -f docker-compose.dev.yml up

# 3. API 테스트
curl http://localhost:8000/health
```

API가 http://localhost:8000 에서 실행됩니다.

**상세 가이드**: [QUICK_START.md](QUICK_START.md)

## 📖 문서

- **[API Integration Guide](API_INTEGRATION_GUIDE.md)** - 웹앱 통합 상세 가이드
- **[API Usage Guide](API_USAGE_GUIDE.md)** - Render 배포 버전 사용 가이드
- **[HWP Parser Improvements](HWP_PARSER_IMPROVEMENTS.md)** - HWP 파서 개선 사항 (2025.08.29)
- **[Quick Start Guide](QUICK_START.md)** - 빠른 시작 가이드
- **[API Documentation](http://localhost:8000/docs)** - Swagger UI (서버 실행 후)
- **[Postman Collection](postman_collection.json)** - API 테스트 컬렉션

## 🧪 사용 예제

### JavaScript/HTML
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('http://localhost:8000/api/v1/extract/hwp-to-json', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log(result);
```

**전체 예제**: [examples/javascript/index.html](examples/javascript/index.html)

### Python
```python
from examples.python.client import HWPAPIClient

client = HWPAPIClient("http://localhost:8000")
result = client.extract_file("document.hwp", format="json")
print(result)
```

**전체 예제**: [examples/python/client.py](examples/python/client.py)

### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/extract/hwp-to-json" \
  -F "file=@document.hwp"
```

## 🏗️ 아키텍처

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│   FastAPI   │────▶│   Parser    │
│  (Web/App)  │     │   Server    │     │  (HWP/PDF)  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │    Redis    │     │ PostgreSQL  │
                    │   (Cache)   │     │    (DB)     │
                    └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Celery    │
                    │  (Async)    │
                    └─────────────┘
```

## 📦 설치

### 요구사항
- Python 3.11+
- Redis 7+
- PostgreSQL 15+ (선택사항)
- Docker & Docker Compose (권장)

### 로컬 설치
```bash
# Python 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# Redis 시작
docker run -d -p 6379:6379 redis:7-alpine

# 서버 실행
uvicorn app.main:app --reload
```

## 🔧 설정

### 환경 변수 (.env)
```env
# 필수
SECRET_KEY=your-secret-key-here
REDIS_URL=redis://localhost:6379/0

# 선택
DATABASE_URL=postgresql://user:pass@localhost/dbname
CORS_ORIGINS=http://localhost:3000,https://your-app.com
MAX_UPLOAD_SIZE=104857600  # 100MB
CACHE_TTL=3600  # 1 hour
```

## 📡 API 엔드포인트

### 파일 추출
- `POST /api/v1/extract/hwp-to-json` - JSON 형식으로 추출
- `POST /api/v1/extract/hwp-to-text` - 텍스트로 추출
- `POST /api/v1/extract/hwp-to-markdown` - Markdown으로 추출

### 비동기 처리
- `POST /api/v1/async/submit` - 비동기 작업 제출
- `GET /api/v1/async/status/{task_id}` - 작업 상태 확인
- `GET /api/v1/async/result/{task_id}` - 결과 가져오기

### 인증
- `POST /api/v1/auth/token` - 토큰 발급
- `GET /api/v1/auth/me` - 현재 사용자 정보

**전체 목록**: [API Documentation](http://localhost:8000/docs)

## 🌐 웹앱 통합

### CORS 설정
```python
# 개발 환경 - 모든 origin 허용
CORS_ORIGINS=*

# 프로덕션 - 특정 origin만 허용
CORS_ORIGINS=https://your-app.com,https://api.your-app.com
```

### React 통합 예제
```jsx
function FileExtractor() {
  const [file, setFile] = useState(null);
  
  const handleExtract = async () => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('http://localhost:8000/api/v1/extract/hwp-to-json', {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    console.log(result);
  };
  
  return (
    <div>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={handleExtract}>Extract</button>
    </div>
  );
}
```

## 🧪 테스트

```bash
# 단위 테스트
pytest tests/

# 특정 테스트
pytest tests/test_api.py

# 커버리지 확인
pytest --cov=app tests/
```

## 🐳 Docker 배포

### 개발 환경
```bash
docker-compose -f docker-compose.dev.yml up
```

### 프로덕션 환경
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 📊 모니터링

- **Prometheus 메트릭**: http://localhost:9090
- **Grafana 대시보드**: http://localhost:3000
- **Flower (Celery)**: http://localhost:5555

## 🔒 보안

- JWT 기반 인증
- Rate Limiting
- 파일 타입 검증
- 파일 크기 제한
- SQL Injection 방어
- XSS 방어

## 📈 성능

- **처리 속도**: ~0.5초/페이지 (평균)
- **동시 처리**: 100+ 동시 요청 지원
- **캐싱**: Redis 캐싱으로 반복 요청 90% 속도 향상
- **대용량 파일**: 스트리밍 및 비동기 처리로 500MB+ 파일 지원

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 라이선스

MIT License - [LICENSE](LICENSE) 파일 참조

## 🆘 지원

- **문제 보고**: [GitHub Issues](https://github.com/your-org/hwp_api/issues)
- **문서**: [API Integration Guide](API_INTEGRATION_GUIDE.md)
- **이메일**: support@your-domain.com

## 🏆 크레딧

- FastAPI - 고성능 웹 프레임워크
- hwp5 - HWP 파일 파싱
- PyMuPDF - PDF 처리
- Redis - 캐싱 및 메시지 브로커
- Celery - 비동기 작업 처리

---

**Version**: 0.2.0 | **Last Updated**: 2025-08-15