#!/usr/bin/env python
"""
PDF 분석 도구 - 깨진 PDF와 정상 PDF 비교
"""
import sys
import fitz  # PyMuPDF
from pathlib import Path

def analyze_pdf(pdf_path):
    """PDF 파일 분석"""
    print(f"\n분석 중: {pdf_path}")
    print("=" * 60)
    
    try:
        doc = fitz.open(pdf_path)
        
        print(f"페이지 수: {len(doc)}")
        print(f"파일 크기: {Path(pdf_path).stat().st_size / 1024:.1f}KB")
        
        # 메타데이터 확인
        metadata = doc.metadata
        if metadata:
            print("\n메타데이터:")
            for key, value in metadata.items():
                if value:
                    print(f"  {key}: {value}")
        
        # 폰트 정보 확인
        fonts = set()
        for page_num in range(len(doc)):
            page = doc[page_num]
            for font in page.get_fonts():
                fonts.add(font[3])  # font name
        
        if fonts:
            print(f"\n사용된 폰트: {', '.join(fonts)}")
        else:
            print("\n폰트 정보 없음 (문제의 원인일 가능성)")
        
        # 텍스트 추출 시도
        print("\n텍스트 추출 결과:")
        for page_num in range(min(1, len(doc))):  # 첫 페이지만
            page = doc[page_num]
            text = page.get_text()
            
            # 깨진 문자 비율 확인
            if text:
                total_chars = len(text.strip())
                broken_chars = text.count('■') + text.count('□')
                if total_chars > 0:
                    broken_ratio = broken_chars / total_chars * 100
                    print(f"  깨진 문자 비율: {broken_ratio:.1f}%")
                
                # 샘플 텍스트 출력
                sample = text[:200].replace('\n', ' ')
                print(f"  샘플: {sample}...")
            else:
                print("  텍스트 없음")
        
        # 인코딩 정보 확인
        print("\n추가 정보:")
        for page_num in range(len(doc)):
            page = doc[page_num]
            # 페이지의 딕셔너리 정보 확인
            text_dict = page.get_text("dict")
            if "blocks" in text_dict:
                for block in text_dict["blocks"][:1]:  # 첫 블록만
                    if block.get("type") == 0:  # text block
                        for line in block.get("lines", [])[:1]:
                            for span in line.get("spans", [])[:1]:
                                print(f"  폰트: {span.get('font', 'Unknown')}")
                                print(f"  크기: {span.get('size', 'Unknown')}")
                                print(f"  플래그: {span.get('flags', 'Unknown')}")
                                break
        
        doc.close()
        
    except Exception as e:
        print(f"오류 발생: {e}")


def compare_pdfs(pdf1_path, pdf2_path):
    """두 PDF 파일 비교"""
    print("\n" + "="*60)
    print("PDF 비교 분석")
    print("="*60)
    
    analyze_pdf(pdf1_path)
    analyze_pdf(pdf2_path)
    
    print("\n" + "="*60)
    print("결론:")
    print("- 깨진 PDF는 폰트 임베딩이 누락되어 한글이 표시되지 않습니다.")
    print("- 원본 HWP 파일에서 다시 변환하거나, 한컴오피스에서 '폰트 포함' 옵션으로 저장하세요.")
    print("- 또는 우리 API를 사용하여 HWP를 PDF로 변환하세요.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python analyze_pdf.py <pdf_file> [pdf_file2]")
        sys.exit(1)
    
    pdf1 = sys.argv[1]
    
    if len(sys.argv) > 2:
        pdf2 = sys.argv[2]
        compare_pdfs(pdf1, pdf2)
    else:
        analyze_pdf(pdf1)