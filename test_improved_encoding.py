#!/usr/bin/env python3
"""
Test improved HWP parser encoding handling.
"""
import os
import sys
import re
from pathlib import Path
from typing import Dict, Any

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.improved_hwp_parser import ImprovedHWPParser
from app.services.enhanced_hwp_parser import EnhancedHWPParser


def count_noise_characters(text: str) -> Dict[str, int]:
    """Count noise/problematic characters in text."""
    noise_counts = {
        'control_chars': len(re.findall(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', text)),
        'special_chars': text.count('ࡂ') + text.count('ृ'),
        'unicode_specials': len(re.findall(r'[\uFFF0-\uFFFF]', text)),
        'replacement_char': text.count('�'),
        'zero_width': text.count('\u200B') + text.count('\u200C') + text.count('\u200D') + text.count('\uFEFF'),
    }
    return noise_counts


def analyze_text_quality(text: str) -> Dict[str, Any]:
    """Analyze text quality metrics."""
    if not text:
        return {'quality_score': 0}
    
    # Count different types of content
    korean_chars = len(re.findall(r'[가-힣]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    numbers = len(re.findall(r'\d', text))
    spaces = text.count(' ')
    newlines = text.count('\n')
    
    # Count noise
    noise = count_noise_characters(text)
    total_noise = sum(noise.values())
    
    # Calculate quality score
    total_chars = len(text)
    readable_chars = korean_chars + english_chars + numbers + spaces + newlines
    quality_score = (readable_chars / total_chars * 100) if total_chars > 0 else 0
    
    return {
        'total_chars': total_chars,
        'korean_chars': korean_chars,
        'english_chars': english_chars,
        'numbers': numbers,
        'spaces': spaces,
        'newlines': newlines,
        'noise_counts': noise,
        'total_noise': total_noise,
        'quality_score': quality_score,
        'korean_ratio': (korean_chars / total_chars * 100) if total_chars > 0 else 0,
        'noise_ratio': (total_noise / total_chars * 100) if total_chars > 0 else 0
    }


def test_file_encoding(file_path: str):
    """Test encoding improvements on a single file."""
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    file_name = os.path.basename(file_path)
    print(f"\n{'='*80}")
    print(f"📄 Testing: {file_name}")
    print(f"{'='*80}")
    
    # Test with enhanced parser (original)
    print("\n1️⃣ Enhanced Parser (Original):")
    print("-" * 40)
    
    enhanced_parser = EnhancedHWPParser()
    enhanced_result = enhanced_parser.parse(file_path)
    enhanced_text = enhanced_result.get('text', '')
    enhanced_quality = analyze_text_quality(enhanced_text)
    
    print(f"📄 Text length: {enhanced_quality['total_chars']:,} chars")
    print(f"🇰🇷 Korean ratio: {enhanced_quality['korean_ratio']:.1f}%")
    print(f"⚠️ Noise ratio: {enhanced_quality['noise_ratio']:.1f}%")
    print(f"🎯 Quality score: {enhanced_quality['quality_score']:.1f}%")
    if enhanced_quality['total_noise'] > 0:
        print(f"🔍 Noise details: {enhanced_quality['noise_counts']}")
    
    # Show sample
    if enhanced_text:
        sample = enhanced_text[:200]
        print(f"📖 Sample: {sample}")
    
    # Test with improved parser
    print("\n2️⃣ Improved Parser (New):")
    print("-" * 40)
    
    improved_parser = ImprovedHWPParser()
    improved_result = improved_parser.parse(file_path)
    improved_text = improved_result.get('text', '')
    improved_quality = analyze_text_quality(improved_text)
    
    print(f"📄 Text length: {improved_quality['total_chars']:,} chars")
    print(f"🇰🇷 Korean ratio: {improved_quality['korean_ratio']:.1f}%")
    print(f"⚠️ Noise ratio: {improved_quality['noise_ratio']:.1f}%")
    print(f"🎯 Quality score: {improved_quality['quality_score']:.1f}%")
    if improved_quality['total_noise'] > 0:
        print(f"🔍 Noise details: {improved_quality['noise_counts']}")
    
    # Show sample
    if improved_text:
        sample = improved_text[:200]
        print(f"📖 Sample: {sample}")
    
    # Comparison
    print("\n3️⃣ Comparison:")
    print("-" * 40)
    
    # Length comparison
    length_diff = improved_quality['total_chars'] - enhanced_quality['total_chars']
    length_pct = (length_diff / enhanced_quality['total_chars'] * 100) if enhanced_quality['total_chars'] > 0 else 0
    
    print(f"📊 Text length: {length_diff:+,} chars ({length_pct:+.1f}%)")
    
    # Quality comparison
    quality_diff = improved_quality['quality_score'] - enhanced_quality['quality_score']
    noise_diff = improved_quality['noise_ratio'] - enhanced_quality['noise_ratio']
    
    print(f"🎯 Quality score: {quality_diff:+.1f}%")
    print(f"⚠️ Noise ratio: {noise_diff:+.1f}%")
    
    # Verdict
    if quality_diff > 10:
        print("✅ Significant quality improvement!")
    elif quality_diff > 0:
        print("✅ Quality improved")
    elif quality_diff == 0:
        print("➖ No quality change")
    else:
        print("⚠️ Quality decreased")
    
    return {
        'file': file_name,
        'enhanced': enhanced_quality,
        'improved': improved_quality,
        'quality_diff': quality_diff,
        'noise_diff': noise_diff
    }


def main():
    """Main test function."""
    
    test_files = [
        "/Users/a/Downloads/공고문(2025+경영혁신+외식서비스+지원+사업).hwp",
        "/Users/a/Downloads/(공고문)+부산광역시+국제협력R&amp;D+기획+수요조사+공고.hwp",
        "/Users/a/Downloads/2025년 포천시 중소기업 노동자 기숙사 임차비 지원사업 모집 공고.hwp",
        "/Users/a/Downloads/2025년+불량분석+및+소자제조+교육생+모집공고-하반기.hwp"
    ]
    
    print("🚀 Improved HWP Parser Encoding Test")
    print("=" * 80)
    
    results = []
    for file_path in test_files:
        if os.path.exists(file_path):
            result = test_file_encoding(file_path)
            if result:
                results.append(result)
    
    # Summary
    if results:
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        
        avg_quality_improvement = sum(r['quality_diff'] for r in results) / len(results)
        avg_noise_reduction = sum(r['noise_diff'] for r in results) / len(results)
        
        print(f"\n📈 Average quality improvement: {avg_quality_improvement:+.1f}%")
        print(f"📉 Average noise reduction: {avg_noise_reduction:+.1f}%")
        
        # Success count
        improved_count = sum(1 for r in results if r['quality_diff'] > 0)
        print(f"✅ Files improved: {improved_count}/{len(results)}")
        
        # Show individual results
        print("\n| File | Enhanced Quality | Improved Quality | Improvement |")
        print("|------|-----------------|------------------|-------------|")
        for r in results:
            file_name = r['file'][:25] + "..." if len(r['file']) > 25 else r['file']
            print(f"| {file_name:<25} | {r['enhanced']['quality_score']:>15.1f}% | {r['improved']['quality_score']:>15.1f}% | {r['quality_diff']:>+10.1f}% |")


if __name__ == "__main__":
    main()