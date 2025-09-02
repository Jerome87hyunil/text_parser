# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소의 코드 작업 시 참고할 가이드입니다.

## 🚨 중요 규칙
**모든 응답은 반드시 한글로 작성해야 합니다. 코드 주석, 문서, 커밋 메시지 등 모든 텍스트를 한글로 작성하세요.**

## 프로젝트 개요

한국어 HWP(한글 워드 프로세서), HWPX, PDF 파일에서 텍스트와 구조화된 데이터를 추출하는 FastAPI 기반 REST API입니다. AI 분석에 최적화되어 있으며 다양한 출력 형식(JSON, 일반 텍스트, Markdown)을 제공합니다.

## 핵심 아키텍처 구성요소

### 파서 전략 패턴
HWP 파싱 시스템은 폴백 메커니즘을 갖춘 다중 전략 접근법을 사용합니다:

1. **EnhancedHWPParser** (`app/services/enhanced_hwp_parser.py`) - 780% 개선된 주 파서
   - BodyTextDirectParser: BodyText 스트림에서 추출 (8,000자 이상)
   - HWP5CLIStrategy: hwp5txt 명령줄 도구 사용
   - HWP5PythonAPIStrategy: 직접 Python API 호출
   - EnhancedPrvTextStrategy: 폴백 미리보기 텍스트 추출

2. **ImprovedHWPParser** (`app/services/improved_hwp_parser.py`) - 정밀한 인코딩 수정
   - HWP 레코드 구조 파싱 (Tag ID, Level, Size)
   - UTF-16LE 디코딩 개선
   - 텍스트 정제 파이프라인

3. **HybridHWPParser** (`app/services/hybrid_hwp_parser.py`) - 두 접근법 결합
   - 포괄적인 레코드 추출
   - 한국어 보존을 위한 스마트 텍스트 디코딩
   - 지능형 노이즈 정제

### 서비스 레이어 아키텍처
- **HWPParser** (`app/services/hwp_parser.py`): 우선순위에 따라 파서를 시도하는 메인 파서 오케스트레이터
- **TextExtractor** (`app/services/text_extractor.py`): 추출 로직과 캐싱 처리
- **CachedExtractor** (`app/services/cached_extractor.py`): Redis 기반 캐싱 레이어

### API 구조
- 버전화된 API를 갖춘 FastAPI 애플리케이션 (`/api/v1`)
- `app/api/v1/endpoints/extract.py`의 주요 추출 엔드포인트
- JWT 토큰을 통한 인증 (선택사항)
- Rate limiting 및 CORS 지원

## 개발 명령어

```bash
# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행 (핫 리로드 포함)
make run
# 또는 직접 실행:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 테스트 실행
make test
# 커버리지 포함:
make coverage
# 특정 테스트:
pytest tests/test_api.py

# 린트 및 코드 포맷팅
make lint    # ruff 린터 실행
make format  # black으로 포맷팅
make type-check  # mypy로 타입 체크

# Docker 개발 환경
docker-compose -f docker-compose.dev.yml up    # 모든 서비스 시작
docker-compose -f docker-compose.dev.yml down  # 서비스 중지

# 임시 파일 정리
make clean
```

## HWP 파서 개선사항 테스트

```bash
# 향상된 파서 테스트
python test_enhanced_parser.py

# 여러 파일 테스트
python test_multiple_files.py

# 하이브리드 파서 테스트
python test_hybrid_parser.py

# 개선된 인코딩 테스트
python test_improved_encoding.py

# API 엔드포인트 테스트
python test_api.py
```

## 환경 설정

`.env.example`을 기반으로 `.env` 파일 생성:

```env
# 프로덕션 필수 설정
SECRET_KEY=your-secret-key-here
REDIS_URL=redis://localhost:6379/0

# 선택적 설정
DATABASE_URL=postgresql://user:pass@localhost/dbname
CORS_ORIGINS=http://localhost:3000,https://your-app.com
MAX_UPLOAD_SIZE=104857600  # 100MB
CACHE_TTL=3600  # 1시간
```

## API 엔드포인트

### 핵심 추출 엔드포인트
- `POST /api/v1/extract/hwp-to-json` - JSON 형식으로 추출
- `POST /api/v1/extract/hwp-to-text` - 일반 텍스트 추출
- `POST /api/v1/extract/hwp-to-markdown` - Markdown으로 추출

### 헬스 체크 및 모니터링
- `GET /health` - 헬스 체크 엔드포인트
- `GET /` - API 정보

## 배포

### Render.com 배포
API 배포 주소: https://hwp-api.onrender.com

Render 관련 설정:
- Starter 플랜: 512MB RAM, 0.5 vCPU
- 콜드 스타트 없음 (항상 활성)
- Rate limit: 분당 100 요청
- 최대 파일 크기: 10MB

### 로컬 Docker 배포
```bash
# 모든 서비스를 포함한 개발 환경
docker-compose -f docker-compose.dev.yml up

# 프로덕션 환경
docker-compose -f docker-compose.prod.yml up -d
```

## HWP 파서 기술적 세부사항

### HWP 파일 구조
- Microsoft Compound File Binary 형식 (OLE)
- BodyText 스트림에 압축된 문서 내용 포함
- Zlib 압축 (-15 window bits 사용)
- 한국어 텍스트용 UTF-16LE 인코딩

### 레코드 구조
```
4바이트 헤더:
- bits 0-9: Tag ID (HWPTAG_PARA_TEXT의 경우 0x42)
- bits 10-19: Level
- bits 20-31: Size
```

### 성능 지표
- 텍스트 추출: 995자 → 8,749자 (780% 개선)
- 한국어 텍스트 추출률: 21% 이상
- 파일 크기 지원: 최대 10MB
- 성공률: 테스트 파일 100%

## 알려진 문제점과 제한사항

1. **인코딩 노이즈**: 일부 파일에 노이즈 문자(ࡂ, ृ) 포함 가능 - 일반적으로 텍스트의 0.2-0.3%
2. **파일 크기**: 안정적인 처리를 위한 최대 10MB 제한
3. **HWP 버전**: HWP 5.0 이상에서 최상의 결과
4. **하이브리드 파서**: 추출량과 품질 사이의 균형을 위해 최적화 진행 중

## 컨텍스트를 위한 중요 파일

- `app/services/enhanced_hwp_parser.py`: 향상된 메인 파서 구현
- `app/services/hwp_parser.py`: 파서 오케스트레이터
- `app/api/v1/endpoints/extract.py`: API 엔드포인트
- `app/core/config.py`: 애플리케이션 설정
- `HWP_PARSER_IMPROVEMENTS.md`: 파서 개선사항 상세 문서
- `API_USAGE_GUIDE.md`: Render 배포 사용 가이드

## Redis 캐싱 전략

애플리케이션은 추출된 콘텐츠 캐싱을 위해 Redis를 사용합니다:
- 캐시 키 형식: `hwp:extract:{file_hash}:{format}`
- 기본 TTL: 3600초 (1시간)
- 오류 시 자동 캐시 무효화

## 오류 처리

애플리케이션은 포괄적인 오류 처리를 제공합니다:
- 애플리케이션별 오류를 위한 커스텀 `HWPAPIException`
- 요청 검증을 위한 검증 오류 핸들러
- 표준 HTTP 오류를 위한 HTTP 예외 핸들러
- 예상치 못한 오류를 위한 일반 예외 핸들러

모든 오류는 `structlog`를 통해 구조화된 로깅으로 기록됩니다.