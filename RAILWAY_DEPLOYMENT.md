# Railway 배포 가이드

## 1. Railway 프로젝트 생성

### 1.1 새 서비스 추가
1. Railway Dashboard → New Project
2. "Deploy from GitHub repo" 선택
3. 이 저장소 연결: `Jerome87hyunil/text_parser` (또는 모노레포의 경우 루트)

### 1.2 Root Directory 설정 (모노레포의 경우)
Settings → Build → Root Directory: `text_parser`

---

## 2. 환경 변수 설정

### 2.1 필수 환경 변수
Railway Dashboard → Variables 탭에서 설정:

```bash
# 서버 설정
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# 보안 키 (Generate 버튼 사용)
SECRET_KEY=<Generate>
JWT_SECRET_KEY=<Generate>

# 메모리 최적화 (512MB RAM용)
WORKERS=1
MAX_UPLOAD_SIZE=10485760
MAX_FILE_SIZE=10485760
PROCESS_TIMEOUT=300

# 파일 형식
ALLOWED_EXTENSIONS=hwp,hwpx,pdf

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100/hour
RATE_LIMIT_EXTRACTION=30/hour

# CORS (Next.js 앱 도메인)
CORS_ORIGINS=https://your-nextjs-app.vercel.app,http://localhost:3000
```

### 2.2 선택적 환경 변수
```bash
# Redis 캐싱 (Railway Redis 서비스 추가 시)
# REDIS_URL=redis://default:password@host:port
# CACHE_ENABLED=true
# CACHE_TTL=3600

# Database (필요 시)
# DATABASE_URL=postgresql://...
```

---

## 3. 빌드 설정

### 3.1 Dockerfile 사용
Settings → Build:
- Builder: Dockerfile
- Dockerfile Path: `Dockerfile.railway`

### 3.2 자동 배포
Settings → Triggers:
- Branch: `main`
- Auto Deploy: Enabled

---

## 4. 헬스체크 확인

배포 후 확인:
```bash
curl https://your-service.railway.app/health
# Expected: {"status": "healthy"}

curl https://your-service.railway.app/
# Expected: {"project": "HWP to PDF API", "version": "0.1.0", ...}
```

---

## 5. Next.js 앱 연동

### 5.1 환경 변수 업데이트
Vercel/Next.js 프로젝트의 환경 변수:

```bash
# .env.local (또는 Vercel Dashboard)
TEXT_PARSER_URL=https://your-hwp-api.railway.app
```

### 5.2 코드 변경 불필요
`src/lib/document-parser.ts`는 이미 `TEXT_PARSER_URL` 환경변수를 사용:
```typescript
const TEXT_PARSER_URL = process.env.TEXT_PARSER_URL || "https://hwp-api.onrender.com";
```

---

## 6. 모니터링

### 6.1 Railway 내장 모니터링
- Metrics 탭에서 CPU, Memory, Network 확인
- Logs 탭에서 실시간 로그 확인

### 6.2 메모리 경고 로그
메모리 80% 초과 시 자동 로그:
```
Memory high: process_rss_mb=450, system_percent=82%
```

---

## 7. 비용 예상

| 사용량 | 예상 비용 |
|-------|----------|
| 저사용 (하루 10-50 요청) | ~$2-5/월 |
| 중간 사용 (하루 100-500 요청) | ~$5-10/월 |
| 고사용 (하루 1000+ 요청) | ~$10-20/월 |

---

## 8. Render에서 마이그레이션

### 8.1 병행 운영 (권장)
1. Railway 배포 완료 후 테스트
2. Next.js 앱의 `TEXT_PARSER_URL`을 Railway로 변경
3. 1-2일 모니터링 후 Render 서비스 삭제

### 8.2 롤백 방법
문제 발생 시 `TEXT_PARSER_URL`을 다시 Render로 변경:
```bash
TEXT_PARSER_URL=https://hwp-api.onrender.com
```

---

## 9. 트러블슈팅

### 9.1 OOM 에러
- WORKERS=1 확인
- MAX_FILE_SIZE 줄이기 (5MB)
- Railway Plan 업그레이드 고려

### 9.2 콜드 스타트
Railway는 항상 실행 상태 유지 (Render Free와 다름)

### 9.3 빌드 실패
```bash
# 로컬 테스트
docker build -f Dockerfile.railway -t hwp-api .
docker run -p 8000:8000 hwp-api
```

---

## 변경 이력

| 날짜 | 변경 |
|-----|------|
| 2025-01-02 | 초기 작성 (Render → Railway 마이그레이션) |
