# 🌊 DigitalOcean 배포 완벽 가이드 (초보자용)

> 💡 **이 가이드는 코딩을 처음 시작하신 분들도 따라할 수 있도록 모든 단계를 상세히 설명합니다.**
> 
> 예상 소요 시간: 30-45분  
> 비용: 월 $6부터 시작 (첫 2개월 $200 크레딧 제공)

## 📋 목차

1. [준비사항](#-준비사항)
2. [DigitalOcean 계정 만들기](#-step-1-digitalocean-계정-만들기)
3. [Droplet(서버) 생성하기](#-step-2-droplet서버-생성하기)
4. [서버에 접속하기](#-step-3-서버에-접속하기)
5. [서버 환경 설정하기](#-step-4-서버-환경-설정하기)
6. [프로젝트 배포하기](#-step-5-프로젝트-배포하기)
7. [도메인 연결하기 (선택)](#-step-6-도메인-연결하기-선택사항)
8. [문제 해결](#-문제-해결-가이드)

---

## 📌 준비사항

배포를 시작하기 전에 다음 사항을 준비해주세요:

- ✅ 이메일 주소 (DigitalOcean 계정용)
- ✅ 신용카드 또는 PayPal 계정 (결제 수단 등록용)
- ✅ GitHub 계정 (코드 저장용)
- ✅ 컴퓨터에 설치된 터미널 프로그램
  - **Windows**: PowerShell 또는 [Git Bash](https://git-scm.com/downloads)
  - **Mac**: Terminal (기본 설치됨)
  - **Linux**: Terminal (기본 설치됨)

---

## 🚀 Step 1: DigitalOcean 계정 만들기

### 1.1 회원가입

1. **웹브라우저를 열고** [https://www.digitalocean.com](https://www.digitalocean.com) 접속
2. 우측 상단의 **"Sign up"** 버튼 클릭
3. 다음 중 하나를 선택하여 가입:
   - 📧 **이메일로 가입** (추천)
   - 🔗 Google 계정으로 가입
   - 🔗 GitHub 계정으로 가입

### 1.2 이메일 인증

1. 가입 시 입력한 이메일 확인
2. DigitalOcean에서 온 **인증 메일** 열기
3. **"Verify Email"** 버튼 클릭

### 1.3 결제 수단 등록

> 💳 **참고**: 실제로 요금이 청구되지 않습니다. $200 무료 크레딧이 제공됩니다!

1. 신용카드 정보 입력 또는 PayPal 연결
2. **"Enable Account"** 클릭

### 1.4 프로모션 크레딧 확인

계정 생성 후 대시보드에서:
- **Billing** → **Credits** 에서 $200 크레딧 확인
- 60일 동안 사용 가능

---

## 🖥️ Step 2: Droplet(서버) 생성하기

> **Droplet이란?** DigitalOcean에서 제공하는 가상 서버입니다. 여러분의 애플리케이션이 실행될 컴퓨터라고 생각하면 됩니다.

### 2.1 Droplet 생성 시작

1. DigitalOcean 대시보드 상단의 **"Create"** 버튼 클릭
2. 드롭다운 메뉴에서 **"Droplets"** 선택

### 2.2 서버 이미지 선택

**"Choose an image"** 섹션에서:

1. **"Marketplace"** 탭 클릭
2. 검색창에 **"Docker"** 입력
3. **"Docker on Ubuntu 22.04"** 선택
   
   > 🐳 **왜 Docker?** 우리 프로젝트가 Docker를 사용하기 때문입니다. Docker가 이미 설치된 서버를 선택하면 설정이 쉬워집니다.

### 2.3 서버 사양 선택

**"Choose a plan"** 섹션에서:

1. **"Basic"** 플랜 선택 (일반적인 용도)
2. **CPU options**: "Regular" 선택
3. 가격 옵션에서 **"$6/mo"** 선택
   - 1 GB RAM / 1 CPU / 25 GB SSD
   - 초기 테스트용으로 충분합니다
   
   > 💰 **팁**: 나중에 필요하면 언제든지 업그레이드 가능합니다!

### 2.4 데이터센터 위치 선택

**"Choose a datacenter region"** 섹션에서:

1. **Singapore** 선택 (한국에서 가장 가까움)
   - 또는 **San Francisco** (미국 서부)
   
   > 🌏 **팁**: 사용자와 가까운 지역을 선택하면 속도가 빨라집니다.

### 2.5 인증 방법 설정

**"Authentication"** 섹션에서:

#### 옵션 1: 비밀번호 방식 (초보자 추천) ✅

1. **"Password"** 선택
2. 강력한 비밀번호 입력
   - 최소 8자 이상
   - 대문자, 소문자, 숫자, 특수문자 포함
   - 예: `MyStr0ng!Pass#2024`
3. **비밀번호를 안전한 곳에 저장하세요!** (매우 중요)

#### 옵션 2: SSH Key 방식 (보안 강화)

SSH Key가 없다면 비밀번호 방식을 사용하세요.

### 2.6 추가 옵션

다음 옵션들을 체크하세요:

- ✅ **Enable IPv6** (체크)
- ✅ **User data** (비워두기)
- ✅ **Monitoring** (체크 - 무료)

### 2.7 Droplet 이름 지정

**"Finalize and create"** 섹션에서:

1. **Hostname**: `hwp-api-server` 입력 (원하는 이름으로 변경 가능)
2. **Tags**: `production`, `hwp-api` 추가 (선택사항)

### 2.8 Droplet 생성

1. 화면 하단의 **"Create Droplet"** 버튼 클릭
2. 1-2분 정도 기다리면 서버 생성 완료!
3. 생성된 서버의 **IP 주소**를 복사해두세요
   - 예: `167.172.85.123`

---

## 🔗 Step 3: 서버에 접속하기

### 3.1 터미널 열기

- **Windows**: 
  - 시작 메뉴에서 "PowerShell" 검색하여 실행
  - 또는 Git Bash 실행
- **Mac**: 
  - Spotlight 검색(Cmd + Space)에서 "Terminal" 입력
- **Linux**: 
  - Ctrl + Alt + T

### 3.2 SSH로 서버 접속

터미널에 다음 명령어 입력:

```bash
ssh root@your-server-ip
```

**실제 예시:**
```bash
ssh root@167.172.85.123
```

### 3.3 최초 접속 시

1. 다음과 같은 메시지가 나타나면:
   ```
   The authenticity of host '167.172.85.123' can't be established.
   Are you sure you want to continue connecting (yes/no)?
   ```
   
2. **`yes`** 입력 후 Enter

3. 비밀번호 입력 프롬프트가 나타나면:
   ```
   root@167.172.85.123's password:
   ```
   
4. **Droplet 생성 시 설정한 비밀번호** 입력
   - ⚠️ **주의**: 비밀번호 입력 시 화면에 아무것도 표시되지 않습니다. 정상입니다!

5. 접속 성공! 다음과 같은 화면이 나타납니다:
   ```
   root@hwp-api-server:~#
   ```

---

## ⚙️ Step 4: 서버 환경 설정하기

> 🎯 **이제부터 모든 명령어는 서버에 접속한 터미널에서 실행합니다!**

### 4.1 시스템 업데이트

```bash
# 패키지 목록 업데이트
apt update

# 시스템 패키지 업그레이드
apt upgrade -y
```

> 💡 **설명**: 
> - `apt update`: 설치 가능한 프로그램 목록을 최신으로 업데이트
> - `apt upgrade -y`: 설치된 프로그램들을 최신 버전으로 업그레이드 (-y는 자동으로 "예" 선택)

### 4.2 Docker Compose 설치 확인

```bash
# Docker 버전 확인
docker --version

# Docker Compose 버전 확인
docker compose version
```

정상적으로 버전이 표시되면 OK!

### 4.3 Git 설치

```bash
# Git 설치
apt install git -y

# Git 버전 확인
git --version
```

### 4.4 방화벽 설정

```bash
# 방화벽 활성화 및 포트 열기
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
ufw --force enable

# 방화벽 상태 확인
ufw status
```

> 🔒 **설명**: 
> - `OpenSSH`: SSH 접속용 (22번 포트)
> - `80`: HTTP 웹 서비스
> - `443`: HTTPS 보안 웹 서비스
> - `8000`: API 서버

---

## 🚀 Step 5: 프로젝트 배포하기

### 5.1 프로젝트 코드 가져오기

```bash
# 홈 디렉토리로 이동
cd ~

# GitHub에서 프로젝트 클론
git clone https://github.com/your-username/hwp_api.git

# 프로젝트 디렉토리로 이동
cd hwp_api
```

> ⚠️ **주의**: `your-username`을 실제 GitHub 사용자명으로 변경하세요!

### 5.2 환경 변수 설정

#### 프로덕션 환경 파일 생성:

```bash
# nano 에디터로 환경 파일 생성
nano .env.production
```

#### 다음 내용을 복사하여 붙여넣기:

```env
# 보안 설정 (반드시 변경하세요!)
SECRET_KEY=your-very-strong-secret-key-change-this-123456789
POSTGRES_PASSWORD=strong-database-password-change-this
FLOWER_PASSWORD=flower-monitoring-password-change
GRAFANA_PASSWORD=grafana-dashboard-password-change

# 데이터베이스 설정
POSTGRES_USER=hwp_api
POSTGRES_DB=hwp_api
DATABASE_URL=postgresql://hwp_api:strong-database-password-change-this@postgres:5432/hwp_api

# Redis 설정
REDIS_URL=redis://redis:6379/0

# 서버 설정
ENVIRONMENT=production
LOG_LEVEL=INFO
WORKERS=2
MAX_UPLOAD_SIZE=104857600
CACHE_ENABLED=true
CACHE_TTL=3600

# CORS 설정 (도메인이 있다면 변경)
CORS_ORIGINS=*

# API 보안
API_KEY_REQUIRED=false
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# 모니터링 계정
FLOWER_USER=admin
GRAFANA_USER=admin
```

#### 파일 저장:
1. `Ctrl + X` 누르기
2. `Y` 입력 (저장 확인)
3. `Enter` 누르기

> 🔐 **중요**: 비밀번호들을 반드시 변경하세요!

### 5.3 Docker 이미지 빌드 및 실행

```bash
# Docker Compose로 서비스 시작 (백그라운드 실행)
docker compose -f docker-compose.prod.yml up -d --build
```

> ⏱️ **참고**: 첫 실행 시 10-15분 정도 소요될 수 있습니다. 커피 한 잔 하고 오세요! ☕

### 5.4 서비스 상태 확인

```bash
# 실행 중인 컨테이너 확인
docker compose -f docker-compose.prod.yml ps

# 로그 확인
docker compose -f docker-compose.prod.yml logs -f api
```

> 💡 **팁**: 로그 보기를 중단하려면 `Ctrl + C` 누르세요.

### 5.5 서비스 접속 테스트

웹 브라우저를 열고 다음 주소로 접속:

```
http://your-server-ip:8000/docs
```

**실제 예시:**
```
http://167.172.85.123:8000/docs
```

Swagger API 문서가 표시되면 성공! 🎉

---

## 🌐 Step 6: 도메인 연결하기 (선택사항)

> 💡 IP 주소 대신 `api.mysite.com` 같은 도메인을 사용하고 싶다면 이 단계를 따르세요.

### 6.1 도메인 구매

다음 서비스 중 하나에서 도메인 구매:
- [Namecheap](https://www.namecheap.com) (저렴함)
- [Google Domains](https://domains.google) (간편함)
- [Cloudflare](https://www.cloudflare.com/products/registrar/) (보안 강화)

### 6.2 DNS 설정

도메인 관리 페이지에서:

1. **DNS 설정** 또는 **네임서버** 메뉴 찾기
2. **A 레코드** 추가:
   - Type: `A`
   - Name: `@` (또는 `api`)
   - Value: `your-server-ip` (예: 167.172.85.123)
   - TTL: `3600`

3. 저장 후 5-30분 대기 (DNS 전파 시간)

### 6.3 Nginx 설정 (도메인용)

서버에서 다음 명령 실행:

```bash
# Nginx 설정 파일 생성
nano nginx/conf.d/api.conf
```

다음 내용 입력:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 실제 도메인으로 변경

    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

저장 후 Nginx 재시작:

```bash
docker compose -f docker-compose.prod.yml restart nginx
```

---

## 🔧 유용한 명령어 모음

### 서비스 관리

```bash
# 서비스 시작
docker compose -f docker-compose.prod.yml up -d

# 서비스 중지
docker compose -f docker-compose.prod.yml down

# 서비스 재시작
docker compose -f docker-compose.prod.yml restart

# 특정 서비스만 재시작
docker compose -f docker-compose.prod.yml restart api
```

### 로그 확인

```bash
# 전체 로그 보기
docker compose -f docker-compose.prod.yml logs

# 특정 서비스 로그 보기
docker compose -f docker-compose.prod.yml logs api

# 실시간 로그 보기
docker compose -f docker-compose.prod.yml logs -f

# 최근 100줄만 보기
docker compose -f docker-compose.prod.yml logs --tail=100
```

### 문제 해결

```bash
# 컨테이너 상태 확인
docker ps -a

# 디스크 사용량 확인
df -h

# 메모리 사용량 확인
free -h

# Docker 정리 (주의: 모든 미사용 리소스 삭제)
docker system prune -a
```

---

## 🚨 문제 해결 가이드

### 문제 1: "Connection refused" 오류

**증상**: API에 접속이 안 됨

**해결 방법**:
```bash
# 컨테이너 상태 확인
docker compose -f docker-compose.prod.yml ps

# 모든 서비스 재시작
docker compose -f docker-compose.prod.yml restart
```

### 문제 2: "502 Bad Gateway" 오류

**증상**: Nginx는 동작하지만 API 연결 실패

**해결 방법**:
```bash
# API 로그 확인
docker compose -f docker-compose.prod.yml logs api

# API 컨테이너 재시작
docker compose -f docker-compose.prod.yml restart api
```

### 문제 3: 디스크 공간 부족

**증상**: "No space left on device" 오류

**해결 방법**:
```bash
# Docker 정리
docker system prune -a --volumes

# 오래된 로그 삭제
docker compose -f docker-compose.prod.yml logs --tail=0
```

### 문제 4: 메모리 부족

**증상**: 서비스가 자주 재시작됨

**해결 방법**:
1. DigitalOcean 대시보드에서 Droplet 업그레이드
2. 또는 불필요한 서비스 중지:
```bash
# Grafana, Prometheus 중지 (모니터링 불필요시)
docker compose -f docker-compose.prod.yml stop grafana prometheus
```

---

## 📊 모니터링 접속

배포가 완료되면 다음 서비스들에 접속 가능:

| 서비스 | URL | 용도 | 계정 |
|--------|-----|------|------|
| API 문서 | `http://your-ip:8000/docs` | API 테스트 | 없음 |
| Flower | `http://your-ip:5555` | Celery 모니터링 | admin / 설정한비밀번호 |
| Grafana | `http://your-ip:3000` | 시스템 모니터링 | admin / 설정한비밀번호 |
| Prometheus | `http://your-ip:9090` | 메트릭 수집 | 없음 |

---

## 🎯 다음 단계

### 1. API Key 시스템 활성화

`.env.production` 파일에서:
```env
API_KEY_REQUIRED=true
```

### 2. HTTPS 설정 (SSL 인증서)

Let's Encrypt 무료 SSL 인증서 설치:
```bash
# Certbot 설치
apt install certbot python3-certbot-nginx -y

# SSL 인증서 발급
certbot --nginx -d your-domain.com
```

### 3. 백업 설정

```bash
# 백업 스크립트 생성
nano backup.sh
```

```bash
#!/bin/bash
# 데이터베이스 백업
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U hwp_api hwp_api > backup_$(date +%Y%m%d).sql

# S3나 다른 저장소로 업로드 (선택사항)
```

### 4. 자동 업데이트 설정

```bash
# GitHub에서 최신 코드 가져오기
git pull origin main

# 서비스 재배포
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 💰 비용 관리

### DigitalOcean 비용 절약 팁:

1. **개발/테스트 시**: 사용하지 않을 때 Droplet 중지
   - 대시보드 → Droplet → Power → Power Off
   
2. **스냅샷 활용**: 
   - 설정 완료 후 스냅샷 생성
   - 필요시 스냅샷에서 복원

3. **리소스 모니터링**:
   - 대시보드에서 사용량 확인
   - 필요시 다운그레이드

---

## 🆘 도움이 필요하신가요?

### 지원 채널:

1. **DigitalOcean 커뮤니티**: https://www.digitalocean.com/community
2. **GitHub Issues**: 프로젝트 저장소에 이슈 등록
3. **Stack Overflow**: `digitalocean` 태그 사용

### 유용한 리소스:

- [DigitalOcean 공식 문서](https://docs.digitalocean.com)
- [Docker 공식 문서](https://docs.docker.com)
- [Ubuntu 명령어 가이드](https://ubuntu.com/tutorials/command-line-for-beginners)

---

## ✅ 체크리스트

배포 완료 확인:

- [ ] DigitalOcean 계정 생성 완료
- [ ] Droplet 생성 완료
- [ ] SSH로 서버 접속 성공
- [ ] Git과 Docker 설치 확인
- [ ] 프로젝트 코드 클론 완료
- [ ] 환경 변수 설정 완료
- [ ] Docker Compose 실행 성공
- [ ] API 문서 페이지 접속 확인
- [ ] 테스트 API 호출 성공

---

## 🎉 축하합니다!

HWP API를 성공적으로 DigitalOcean에 배포하셨습니다! 🚀

이제 다음을 할 수 있습니다:
- API를 사용하여 HWP 파일 처리
- 모니터링 도구로 서버 상태 확인
- API Key를 발급하여 보안 강화
- 도메인을 연결하여 전문적인 서비스 구축

**문제가 발생하면 당황하지 마세요!** 위의 문제 해결 가이드를 참고하거나 커뮤니티에 도움을 요청하세요.

---

*마지막 업데이트: 2024년 1월*