# Render 배포 가이드

## 📋 사전 준비사항

1. **GitHub 저장소 생성**
   - 코드를 GitHub에 푸시
   - Private 저장소도 가능 (Render와 연동 필요)

2. **Render 계정 생성**
   - [Render](https://render.com) 회원가입
   - GitHub 계정과 연동

## 🚀 배포 단계

### 1. GitHub에 코드 푸시

```bash
# Git 초기화 (이미 되어있다면 생략)
git init

# 모든 파일 추가
git add .

# 커밋
git commit -m "Initial commit for Render deployment"

# GitHub 원격 저장소 추가
git remote add origin https://github.com/YOUR_USERNAME/hwp_api.git

# 푸시
git push -u origin main
```

### 2. render.yaml 파일 수정

`render.yaml` 파일에서 다음 항목들을 수정:

```yaml
repo: https://github.com/Jerome87hyunil/text_parser.git  # ✅ 이미 설정됨
CORS_ORIGINS: https://hwp-api.onrender.com  # ✅ Render 기본 도메인 설정됨
```

### 3. Render에서 배포

#### 방법 1: Blueprint 사용 (권장)

1. Render 대시보드에서 "New" → "Blueprint" 클릭
2. GitHub 저장소 연결
3. `render.yaml` 파일이 자동으로 감지됨
4. "Apply" 클릭하여 모든 서비스 생성

#### 방법 2: 개별 서비스 생성

1. **Web Service 생성**
   - "New" → "Web Service"
   - GitHub 저장소 연결
   - Runtime: Docker
   - Region: Singapore (한국 근접)
   - 환경 변수 설정

2. **Database 생성**
   - "New" → "PostgreSQL"
   - Name: hwp-api-db
   - Region: Singapore

3. **Redis 생성**
   - "New" → "Redis"
   - Name: hwp-api-redis
   - Region: Singapore

### 4. 환경 변수 설정

Render 대시보드에서 다음 환경 변수들을 설정:

#### 필수 환경 변수

```bash
# 자동 생성되는 변수
DATABASE_URL  # PostgreSQL 연결 시 자동 생성
REDIS_URL     # Redis 연결 시 자동 생성
SECRET_KEY    # Generate 옵션 사용
JWT_SECRET_KEY  # Generate 옵션 사용

# 수동 설정 필요 (render.yaml에 이미 설정됨)
# CORS_ORIGINS는 자동으로 설정됩니다:
# - https://hwp-api.onrender.com (Render 기본 도메인)
# - http://localhost:3000 (로컬 개발용)
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

#### 선택적 환경 변수

```bash
# 이메일 설정 (알림 기능 사용 시)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Sentry (에러 모니터링)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# AWS S3 (대용량 파일 저장)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=hwp-api-files
```

## 🔧 배포 후 설정

### 1. 데이터베이스 마이그레이션

Render Shell에서 실행:

```bash
# Render 대시보드 → Web Service → Shell 탭
alembic upgrade head
```

### 2. 헬스체크 확인

```bash
curl https://hwp-api.onrender.com/health
```

### 3. 도메인 정보

**Render 기본 도메인**: `https://hwp-api.onrender.com`
- 배포 즉시 사용 가능
- SSL 인증서 자동 포함
- 무료 제공

**커스텀 도메인 설정 (선택사항)**
1. Render 대시보드 → Settings → Custom Domains
2. 도메인 추가 후 DNS 설정
3. SSL 인증서는 자동 발급

## 📊 모니터링

### 로그 확인

- Render 대시보드 → Logs 탭
- 실시간 로그 스트리밍 가능

### 메트릭 확인

- CPU, Memory, Network 사용량
- Response time, Request count
- Error rate

## 🔄 자동 배포

GitHub main 브랜치에 푸시하면 자동으로 재배포:

```bash
git add .
git commit -m "Update features"
git push origin main
```

## ⚠️ 주의사항

1. **Free Tier 제한사항**
   - 750시간/월 무료
   - 15분 동안 요청이 없으면 슬립 모드
   - 디스크 공간 제한

2. **파일 저장**
   - Render는 ephemeral 파일시스템 사용
   - 영구 저장이 필요한 파일은 S3 등 외부 스토리지 사용

3. **성능 최적화**
   - Redis 캐싱 적극 활용
   - 대용량 파일 처리는 백그라운드 작업(Celery) 사용
   - 이미지/파일 최적화

## 🛠️ 트러블슈팅

### 배포 실패 시

1. Build 로그 확인
2. requirements.txt 의존성 확인
3. Dockerfile 문법 오류 확인

### 성능 이슈

1. Worker 수 조정 (WORKERS 환경 변수)
2. Plan 업그레이드 고려
3. 캐싱 전략 최적화

### 데이터베이스 연결 실패

1. DATABASE_URL 형식 확인
2. IP 허용 목록 확인
3. 연결 풀 설정 조정

## 📞 지원

- [Render Documentation](https://render.com/docs)
- [Render Community](https://community.render.com)
- [Status Page](https://status.render.com)