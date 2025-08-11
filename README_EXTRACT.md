# HWP Text Extraction API

AI 분석을 위해 최적화된 HWP 파일 텍스트 추출 API입니다.

## 주요 변경사항

PDF 변환 대신 **AI 분석을 위한 구조화된 텍스트 추출**에 초점을 맞췄습니다.

## 새로운 API 엔드포인트

### 1. HWP to JSON (`/api/v1/extract/hwp-to-json`)
AI 분석에 최적화된 구조화된 JSON 형식으로 추출합니다.

**요청:**
```bash
curl -X POST "http://localhost:8000/api/v1/extract/hwp-to-json" \
  -F "file=@document.hwp" \
  -F "include_metadata=true" \
  -F "include_structure=true" \
  -F "include_statistics=true"
```

**응답 예시:**
```json
{
  "success": true,
  "filename": "document.hwp",
  "format": "json",
  "content": {
    "version": "1.0",
    "extracted_at": "2024-01-01T00:00:00Z",
    "metadata": {
      "title": "문서 제목",
      "author": "작성자",
      "created_date": "2024-01-01",
      "language": "ko"
    },
    "text": "전체 텍스트 내용...",
    "paragraphs": [
      {
        "index": 0,
        "text": "단락 내용",
        "type": "normal",
        "char_count": 100,
        "word_count": 20,
        "tags": ["short", "date"]
      }
    ],
    "tables": [
      {
        "index": 0,
        "rows": [["헤더1", "헤더2"], ["데이터1", "데이터2"]],
        "row_count": 2,
        "col_count": 2,
        "summary": "Table with 2 rows and 2 columns"
      }
    ],
    "statistics": {
      "char_count": 5000,
      "word_count": 800,
      "paragraph_count": 15,
      "table_count": 2,
      "korean_ratio": 0.85,
      "english_ratio": 0.15,
      "avg_sentence_length": 12.5
    }
  },
  "message": "HWP content extracted successfully"
}
```

### 2. HWP to Text (`/api/v1/extract/hwp-to-text`)
단순 텍스트 추출 (간단한 분석용)

**요청:**
```bash
curl -X POST "http://localhost:8000/api/v1/extract/hwp-to-text" \
  -F "file=@document.hwp" \
  -F "preserve_formatting=true"
```

### 3. HWP to Markdown (`/api/v1/extract/hwp-to-markdown`)
마크다운 형식으로 추출 (구조 보존)

**요청:**
```bash
curl -X POST "http://localhost:8000/api/v1/extract/hwp-to-markdown" \
  -F "file=@document.hwp" \
  -F "include_metadata=true"
```

## 서버 실행

```bash
# 방법 1: 직접 실행
python3 run_server.py

# 방법 2: uvicorn 사용
python3 -m uvicorn app.main:app --reload --port 8000
```

## 테스트

```bash
# 테스트 스크립트 실행
python3 test_extract_api.py
```

## AI 통합 예시

```python
import httpx
import json

# HWP 파일을 JSON으로 추출
async with httpx.AsyncClient() as client:
    with open("document.hwp", "rb") as f:
        response = await client.post(
            "http://localhost:8000/api/v1/extract/hwp-to-json",
            files={"file": f}
        )
    
    data = response.json()
    content = data["content"]
    
    # GPT API에 전달할 프롬프트 생성
    prompt = f"""
    다음 문서를 분석해주세요:
    
    제목: {content['metadata']['title']}
    작성자: {content['metadata']['author']}
    
    통계:
    - 총 단어 수: {content['statistics']['word_count']}
    - 단락 수: {content['statistics']['paragraph_count']}
    - 표 개수: {content['statistics']['table_count']}
    
    내용:
    {content['text']}
    
    주요 내용을 요약하고 핵심 인사이트를 제공해주세요.
    """
    
    # GPT API 호출 (예시)
    # response = openai.ChatCompletion.create(
    #     model="gpt-4",
    #     messages=[{"role": "user", "content": prompt}]
    # )
```

## 주요 특징

1. **구조화된 데이터 추출**
   - 단락, 표, 리스트, 제목 구조 보존
   - 메타데이터 포함 (제목, 작성자, 날짜 등)
   - 텍스트 통계 제공

2. **AI 최적화**
   - JSON 형식으로 쉽게 파싱 가능
   - 의미 있는 태그 추가 (날짜, 이메일, URL 등)
   - 한국어/영어 비율 분석

3. **유연한 출력 형식**
   - JSON: 완전한 구조화 데이터
   - Text: 단순 텍스트
   - Markdown: 가독성 있는 형식

## 다중 파서 지원

시스템은 다음 파서들을 순차적으로 시도합니다:
1. hwp5 파서
2. pyhwp 파서  
3. olefile 기반 파서 (폴백)

## 에러 처리

- 지원하지 않는 파일 형식: 400 Bad Request
- 파일 크기 초과: 413 Payload Too Large
- 파싱 실패: 500 Internal Server Error (상세 에러 메시지 포함)