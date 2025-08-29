#!/usr/bin/env python3
"""
Test Enhanced HWP Parser with multiple files.
"""
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.enhanced_hwp_parser import EnhancedHWPParser
from app.services.hwp_parser import HWPParser


def test_file(file_path: str, enhanced_parser: EnhancedHWPParser, original_parser: HWPParser):
    """Test a single file with both parsers."""
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None
    
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path) / 1024  # KB
    
    print(f"\n{'='*80}")
    print(f"📄 Testing: {file_name}")
    print(f"📦 File size: {file_size:.2f} KB")
    print(f"{'='*80}")
    
    # Test with original parser (pyhwp)
    print("\n1️⃣ Original Parser (pyhwp):")
    print("-" * 40)
    
    try:
        original_text = original_parser.extract_text(file_path)
        print(f"✅ Text length: {len(original_text)} chars")
        
        # Preview
        if original_text:
            preview = original_text[:200].replace('\n', ' ')
            print(f"📖 Preview: {preview}...")
            
            # Check if it's truncated
            if "교육장비" in file_name and "교육장비" in original_text:
                last_words = original_text[-50:]
                if "교육장비 : 전" in last_words:
                    print("⚠️ Text appears truncated at '교육장비 : 전'")
    except Exception as e:
        print(f"❌ Error: {e}")
        original_text = ""
    
    # Test with enhanced parser
    print("\n2️⃣ Enhanced Parser:")
    print("-" * 40)
    
    try:
        result = enhanced_parser.parse(file_path)
        enhanced_text = result.get('text', '')
        parsing_method = result.get('parsing_method', 'unknown')
        
        print(f"✅ Parsing method: {parsing_method}")
        print(f"📄 Text length: {len(enhanced_text)} chars")
        print(f"📝 Paragraphs: {len(result.get('paragraphs', []))}")
        
        # Preview
        if enhanced_text:
            preview = enhanced_text[:200].replace('\n', ' ')
            print(f"📖 Preview: {preview}...")
            
            # Check last part
            last_preview = enhanced_text[-200:].replace('\n', ' ')
            print(f"📖 Last part: ...{last_preview}")
    except Exception as e:
        print(f"❌ Error: {e}")
        enhanced_text = ""
    
    # Comparison
    print("\n3️⃣ Comparison:")
    print("-" * 40)
    
    original_len = len(original_text)
    enhanced_len = len(enhanced_text)
    
    if original_len > 0:
        improvement = ((enhanced_len - original_len) / original_len * 100)
        print(f"📊 Original: {original_len:,} chars")
        print(f"📊 Enhanced: {enhanced_len:,} chars")
        print(f"📈 Improvement: {improvement:+.1f}%")
        
        if improvement > 100:
            print("🎉 Significant improvement (>100%)")
        elif improvement > 50:
            print("✅ Good improvement (>50%)")
        elif improvement > 0:
            print("✅ Some improvement")
        else:
            print("⚠️ No improvement")
    else:
        print(f"📊 Original: Failed to extract")
        print(f"📊 Enhanced: {enhanced_len:,} chars")
        if enhanced_len > 0:
            print("✅ Enhanced parser succeeded where original failed")
    
    # Content quality check
    print("\n4️⃣ Content Quality:")
    print("-" * 40)
    
    # Check for common document sections
    sections = ["신청", "지원", "자격", "제출", "문의", "기간", "대상", "방법"]
    found_sections = []
    
    for section in sections:
        if section in enhanced_text:
            found_sections.append(section)
    
    if found_sections:
        print(f"✅ Found sections: {', '.join(found_sections)}")
    
    # Check for encoding issues
    if enhanced_text:
        # Check for common encoding problems
        encoding_issues = 0
        if 'ࡂ' in enhanced_text or 'ృ' in enhanced_text or '�' in enhanced_text:
            encoding_issues += enhanced_text.count('ࡂ') + enhanced_text.count('ృ') + enhanced_text.count('�')
            print(f"⚠️ Potential encoding issues: {encoding_issues} suspicious characters")
        else:
            print("✅ No obvious encoding issues")
    
    return {
        'file': file_name,
        'size_kb': file_size,
        'original_len': original_len,
        'enhanced_len': enhanced_len,
        'improvement': improvement if original_len > 0 else None,
        'method': parsing_method if 'result' in locals() else None
    }


def main():
    """Main test function."""
    
    # Test files
    test_files = [
        "/Users/a/Downloads/공고문(2025+경영혁신+외식서비스+지원+사업).hwp",
        "/Users/a/Downloads/(공고문)+부산광역시+국제협력R&amp;D+기획+수요조사+공고.hwp",
        "/Users/a/Downloads/2025년 포천시 중소기업 노동자 기숙사 임차비 지원사업 모집 공고.hwp",
        "/Users/a/Downloads/2025년+불량분석+및+소자제조+교육생+모집공고-하반기.hwp"  # Original test file
    ]
    
    # Note: PDF file excluded as it requires different handling
    pdf_file = "/Users/a/Downloads/붙임2.+『2025년+팹리스+기업+애로기술+컨설팅+지원』+지원+대상+기업+모집+공고.pdf"
    
    print("🚀 Enhanced HWP Parser Multi-File Test")
    print("=" * 80)
    
    # Initialize parsers
    enhanced_parser = EnhancedHWPParser()
    original_parser = HWPParser()
    
    # Test each file
    results = []
    for file_path in test_files:
        result = test_file(file_path, enhanced_parser, original_parser)
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    print("\n| File | Size (KB) | Original | Enhanced | Improvement | Method |")
    print("|------|-----------|----------|----------|-------------|---------|")
    
    for r in results:
        file_name = r['file'][:30] + "..." if len(r['file']) > 30 else r['file']
        improvement = f"{r['improvement']:+.1f}%" if r['improvement'] is not None else "N/A"
        print(f"| {file_name:<30} | {r['size_kb']:>9.1f} | {r['original_len']:>8,} | {r['enhanced_len']:>8,} | {improvement:>11} | {r['method']:<15} |")
    
    # Overall statistics
    if results:
        avg_improvement = sum(r['improvement'] for r in results if r['improvement'] is not None) / len([r for r in results if r['improvement'] is not None])
        total_original = sum(r['original_len'] for r in results)
        total_enhanced = sum(r['enhanced_len'] for r in results)
        
        print(f"\n📈 Average Improvement: {avg_improvement:+.1f}%")
        print(f"📊 Total chars extracted - Original: {total_original:,}, Enhanced: {total_enhanced:,}")
        
        # Success rate
        success_enhanced = len([r for r in results if r['enhanced_len'] > 0])
        success_original = len([r for r in results if r['original_len'] > 0])
        print(f"✅ Success rate - Original: {success_original}/{len(results)}, Enhanced: {success_enhanced}/{len(results)}")
    
    # Test PDF separately
    print("\n" + "=" * 80)
    print("📄 PDF File Test (Separate handling required)")
    print("=" * 80)
    print(f"File: {os.path.basename(pdf_file)}")
    print("ℹ️ PDF files require different parsing strategy (not HWP format)")


if __name__ == "__main__":
    main()