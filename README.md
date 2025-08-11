# HWP to PDF Converter API

한글(HWP/HWPX) 파일을 PDF로 변환하는 RESTful API 서비스입니다.

## 🚀 주요 기능

- HWP/HWPX 파일 업로드 및 PDF 변환
- 비동기 작업 처리 (Celery + Redis)
- 변환 상태 실시간 추적
- 변환된 PDF 다운로드
- 파일 크기 및 형식 검증

## 📋 요구사항

- Python 3.11+
- Redis (비동기 처리용)
- LibreOffice (선택적, 폴백 변환용)

## 🛠️ 설치 방법

### 1. 저장소 클론
```bash
git clone https://github.com/yourusername/hwp_api.git
cd hwp_api
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 설정
```bash
cp .env.example .env
# .env 파일을 편집하여 설정값 수정
```

### 5. 스토리지 디렉토리 생성
```bash
mkdir -p storage/uploads storage/converted
```

## 🏃‍♂️ 실행 방법

### 개발 서버 실행
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Redis 실행 (Docker 사용)
```bash
docker run -d -p 6379:6379 redis:alpine
```

### Celery Worker 실행 (Phase 2+)
```bash
celery -A app.workers.tasks worker --loglevel=info
```

## 📡 API 사용법

### 1. HWP 파일 변환 요청
```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
  -F "file=@document.hwp"
```

응답:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "File uploaded successfully. Conversion started."
}
```

### 2. 변환 상태 확인
```bash
curl "http://localhost:8000/api/v1/convert/{task_id}/status"
```

응답:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "message": "Conversion completed successfully"
}
```

### 3. PDF 다운로드
```bash
curl -O "http://localhost:8000/api/v1/convert/{task_id}/download"
```

## 🧪 테스트

```bash
# 모든 테스트 실행
pytest

# 커버리지 포함
pytest --cov=app

# 특정 테스트만 실행
pytest tests/test_converter.py
```

## 📁 프로젝트 구조

```
hwp_api/
├── app/
│   ├── api/          # API 엔드포인트
│   ├── core/         # 핵심 설정 및 유틸리티
│   ├── models/       # 데이터 모델
│   ├── services/     # 비즈니스 로직
│   ├── converters/   # 변환 엔진
│   └── workers/      # 비동기 작업
├── tests/            # 테스트 코드
├── docker/           # Docker 설정
├── scripts/          # 유틸리티 스크립트
└── storage/          # 파일 저장소
```

## 🔧 개발 가이드

### 코드 스타일
```bash
# 코드 포맷팅
black app tests

# 린팅
ruff check app tests

# 타입 체크
mypy app
```

### 브랜치 전략
- `main`: 프로덕션 준비 코드
- `develop`: 개발 브랜치
- `feature/*`: 기능 개발
- `hotfix/*`: 긴급 수정

## 📝 라이선스

MIT License

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📞 문의

프로젝트 관련 문의사항은 이슈를 생성해주세요.