# HWP API 사용 가이드 (Render Starter 플랜)

## 📌 API 엔드포인트

- **Base URL**: `https://hwp-api.onrender.com`
- **API 문서**: https://hwp-api.onrender.com/docs

### 주요 엔드포인트
- `/api/v1/extract/hwp-to-json` - JSON 형식 추출
- `/api/v1/extract/hwp-to-text` - 텍스트 추출
- `/api/v1/extract/hwp-to-markdown` - Markdown 형식 추출

### HWP 파서 개선 사항 (2025.08.29 업데이트)
- **Enhanced Parser**: 평균 8,000자 이상 추출 가능 (기존 995자 → 8,749자, 780% 향상)
- **다중 파싱 전략**: BodyText, HWP5 CLI, Python API, PrvText 순차 시도
- **한글 문서 지원 개선**: 한국어 문자 추출률 21% 이상
- **대용량 파일 지원**: 최대 10MB HWP 파일 처리 가능

## ✅ Render Starter 플랜 사양

### 서버 리소스
- **CPU**: 0.5 vCPU (무료 대비 5배 성능)
- **메모리**: 512MB RAM
- **자동 슬립**: 없음 (24/7 운영)
- **콜드 스타트**: 없음 (항상 활성 상태)

### API 제한
- **Rate Limiting**: 분당 100개 요청 (안정적 처리 가능)
- **파일 크기**: 최대 10MB
- **처리 시간**: 최대 5분 타임아웃
- **동시 처리**: 3-5개 요청 동시 처리 가능

## 💡 사용 가이드

### 1. 안정적인 요청 처리
Starter 플랜은 콜드 스타트가 없어 즉시 응답이 가능합니다.
```python
# 일반적인 타임아웃 설정
timeout = 30  # 30초면 충분
retry_count = 2  # 2회 재시도
```

### 2. Rate Limiting 활용
분당 100개까지 안정적으로 처리 가능합니다.
```python
# 병렬 처리 가능
# 안전하게 분당 80개 정도 유지
time.sleep(0.75)  # 분당 약 80개 요청
```

### 3. 파일 크기 가이드
10MB까지 안정적으로 처리 가능합니다.
```python
# 파일 크기 체크
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
if file_size > MAX_FILE_SIZE:
    # 파일 분할 필요
    pass
```

### 4. 동시 요청 활용
CPU 성능이 향상되어 병렬 처리가 가능합니다.
```python
# 동시 요청 3-5개 가능
async with asyncio.Semaphore(3):  # 동시 3개
    await process_file()
```

## 💻 구현 예시 코드

### Python 클라이언트 (Starter 플랜 최적화)
```python
import requests
import time
import os
import asyncio
import aiohttp
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor

class HWPAPIClient:
    def __init__(self):
        self.base_url = "https://hwp-api.onrender.com"
        self.max_retries = 2  # 재시도 횟수 감소 (안정적)
        self.timeout = 30  # 타임아웃 감소 (콜드 스타트 없음)
        self.request_delay = 0.75  # 요청 간 대기 시간 감소
        self.max_concurrent = 3  # 동시 처리 가능
        
    def convert_file(self, file_path: str, output_format: str = "json") -> Optional[dict]:
        """
        HWP 파일을 지정된 형식으로 변환
        
        Args:
            file_path: HWP 파일 경로
            output_format: 출력 형식 (json, text, markdown)
            
        Returns:
            변환 결과 또는 None
        """
        
        # 1. 파일 크기 체크
        file_size = os.path.getsize(file_path)
        if file_size > 10 * 1024 * 1024:
            print(f"❌ 파일이 10MB를 초과합니다: {file_size / 1024 / 1024:.2f}MB")
            return None
        
        # 2. 엔드포인트 설정
        endpoint = f"{self.base_url}/api/v1/extract/hwp-to-{output_format}"
        
        # 3. 재시도 로직
        for attempt in range(self.max_retries):
            try:
                print(f"🔄 시도 {attempt + 1}/{self.max_retries}")
                
                with open(file_path, 'rb') as f:
                    response = requests.post(
                        endpoint,
                        files={'file': f},
                        timeout=self.timeout
                    )
                
                # Rate limit 처리
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    print(f"⏳ Rate limit 도달. {retry_after}초 대기...")
                    time.sleep(retry_after)
                    continue
                
                # 성공
                if response.status_code == 200:
                    print("✅ 변환 성공!")
                    return response.json()
                
                # 기타 오류
                print(f"❌ 오류 발생: {response.status_code} - {response.text}")
                    
            except requests.Timeout:
                print("⏳ 타임아웃 발생. 재시도 중...")
                time.sleep(2)
                continue
                
            except Exception as e:
                print(f"❌ 예외 발생: {e}")
                
            # 재시도 전 대기
            if attempt < self.max_retries - 1:
                time.sleep(2)
        
        return None

    def batch_process(self, files: list, output_format: str = "json") -> list:
        """
        여러 파일을 병렬로 처리 (Starter 플랜 최적화)
        
        Args:
            files: 파일 경로 리스트
            output_format: 출력 형식
            
        Returns:
            변환 결과 리스트
        """
        # 병렬 처리를 위한 ThreadPoolExecutor 사용
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = []
            for i, file_path in enumerate(files):
                # Rate limiting을 위한 대기
                if i > 0:
                    time.sleep(self.request_delay)
                
                future = executor.submit(self.convert_file, file_path, output_format)
                futures.append((file_path, future))
            
            # 결과 수집
            results = []
            for file_path, future in futures:
                try:
                    result = future.result(timeout=60)
                    results.append({
                        'file': file_path,
                        'success': result is not None,
                        'result': result
                    })
                except Exception as e:
                    results.append({
                        'file': file_path,
                        'success': False,
                        'error': str(e)
                    })
        
        # 결과 요약
        success_count = sum(1 for r in results if r['success'])
        print(f"\n📊 처리 완료: {success_count}/{len(files)} 성공")
        
        return results

    def health_check(self) -> bool:
        """
        서버 상태 확인 (Starter 플랜은 항상 활성)
        """
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5  # 빠른 응답
            )
            return response.status_code == 200
        except:
            return False


# 사용 예시
if __name__ == "__main__":
    client = HWPAPIClient()
    
    # 서버 상태 확인 (Starter 플랜은 항상 활성)
    if client.health_check():
        print("✅ 서버가 정상 작동 중입니다.")
    
    # 단일 파일 변환
    result = client.convert_file("document.hwp", "json")
    if result:
        print(f"변환 결과: {result}")
    
    # 여러 파일 병렬 처리 (Starter 플랜 장점)
    files = ["doc1.hwp", "doc2.hwp", "doc3.hwp", "doc4.hwp", "doc5.hwp"]
    results = client.batch_process(files, "text")  # 3개씩 동시 처리
```

### JavaScript/Node.js 클라이언트 (Starter 플랜 최적화)
```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const pLimit = require('p-limit'); // npm install p-limit

class HWPAPIClient {
    constructor() {
        this.baseURL = 'https://hwp-api.onrender.com';
        this.maxRetries = 2;  // 안정적이므로 재시도 감소
        this.timeout = 30000; // 30초
        this.requestDelay = 750; // 0.75초
        this.concurrencyLimit = pLimit(3); // 동시 3개 처리
    }

    async sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async convertFile(filePath, outputFormat = 'json') {
        const fileSize = fs.statSync(filePath).size;
        
        // 파일 크기 체크
        if (fileSize > 10 * 1024 * 1024) {
            console.error(`❌ 파일이 10MB를 초과합니다: ${(fileSize / 1024 / 1024).toFixed(2)}MB`);
            return null;
        }

        const endpoint = `${this.baseURL}/api/v1/extract/hwp-to-${outputFormat}`;
        
        for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
            try {
                console.log(`🔄 시도 ${attempt}/${this.maxRetries}`);
                
                const formData = new FormData();
                formData.append('file', fs.createReadStream(filePath));
                
                const response = await axios.post(endpoint, formData, {
                    headers: formData.getHeaders(),
                    timeout: this.timeout
                });
                
                if (response.status === 200) {
                    console.log('✅ 변환 성공!');
                    return response.data;
                }
                
            } catch (error) {
                if (error.response?.status === 429) {
                    const retryAfter = error.response.headers['retry-after'] || 60;
                    console.log(`⏳ Rate limit 도달. ${retryAfter}초 대기...`);
                    await this.sleep(retryAfter * 1000);
                    continue;
                }
                
                if (error.code === 'ECONNABORTED') {
                    console.log('⏳ 타임아웃 발생. 재시도 중...');
                    await this.sleep(2000);
                    continue;
                }
                
                console.error(`❌ 오류 발생: ${error.message}`);
            }
            
            if (attempt < this.maxRetries) {
                await this.sleep(2000);
            }
        }
        
        return null;
    }

    async batchProcess(files, outputFormat = 'json') {
        // 병렬 처리 (Starter 플랜 최적화)
        const promises = files.map((file, index) => 
            this.concurrencyLimit(async () => {
                // Rate limiting을 위한 지연
                if (index > 0) {
                    await this.sleep(this.requestDelay * index);
                }
                return this.convertFile(file, outputFormat);
            })
        );
        
        const results = await Promise.all(promises);
        const successCount = results.filter(r => r !== null).length;
        console.log(`📊 처리 완료: ${successCount}/${files.length} 성공`);
        
        return results;
    }
}

// 사용 예시
const client = new HWPAPIClient();

// 병렬 처리 활용
const files = ['doc1.hwp', 'doc2.hwp', 'doc3.hwp'];
const results = await client.batchProcess(files, 'json');
```

## ⚠️ 주의사항

1. **10MB 이상 파일** - 처리 불가능
2. **분당 100개 이상 요청** - Rate limit 차단
3. **동시 요청 5개 초과** - 서버 부하 증가

## ✅ Starter 플랜 권장 사항

1. **병렬 처리 활용** - 3개까지 동시 처리로 속도 향상
2. **적절한 타임아웃** - 30초 설정 (콜드 스타트 없음)
3. **간소한 재시도** - 1-2회 재시도면 충분
4. **Rate limit 여유** - 분당 80개 정도 유지
5. **요청 간 대기** - 0.75초 정도 (무료 플랜 대비 단축)
6. **파일 크기** - 10MB까지 안정적 처리

## 🔧 문제 해결

### 서버가 응답하지 않을 때 (Starter 플랜은 거의 발생하지 않음)
1. `/health` 엔드포인트로 서버 상태 확인
2. 네트워크 연결 확인
3. 2-3초 후 재시도

### Rate Limit 에러 (429)
1. `Retry-After` 헤더 확인
2. 지정된 시간만큼 대기
3. 요청 간격을 늘려서 재시도

### 파일 처리 실패
1. 파일 크기 확인 (10MB 이하 지원)
2. 파일 형식 확인 (.hwp, .hwpx, .pdf)
3. 파일이 손상되지 않았는지 확인
4. HWP 파일 인코딩 문제 시 다른 파싱 전략 자동 시도

## 📞 지원

- **API 문서**: https://hwp-api.onrender.com/docs
- **상태 확인**: https://hwp-api.onrender.com/health
- **문제 발생 시**: GitHub Issues에 보고

## 🎯 Starter 플랜 성능 최적화 팁

### 최대 성능 활용
1. **병렬 처리**: 3개 파일 동시 처리로 3배 빠른 속도
2. **캐싱 활용**: 반복 요청 시 결과 캐싱 고려
3. **배치 처리**: 한 번에 여러 파일 처리로 효율성 증대
4. **오프피크 시간**: 트래픽이 적은 시간대 활용

### 모니터링
- **일일 처리량**: 약 100,000개 요청 가능 (분당 80개 × 1440분)
- **동시 사용자**: 약 10-20명 동시 사용 가능
- **평균 응답 시간**: 2-5초 (파일 크기에 따라)

## 📈 추가 업그레이드 고려 시점

다음 상황에서는 더 높은 플랜을 고려하세요:
- **Standard ($19/월)**: 분당 500개 이상 요청, 동시 10개 이상 처리
- **Pro ($85/월)**: 엔터프라이즈급 트래픽, 자동 스케일링 필요