#!/usr/bin/env python3
"""
Test Hybrid HWP Parser - Comprehensive testing of the new hybrid approach.
"""
import os
import sys
import re
from pathlib import Path
from typing import Dict, Any

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.hybrid_hwp_parser import HybridHWPParser
from app.services.enhanced_hwp_parser import EnhancedHWPParser
from app.services.improved_hwp_parser import ImprovedHWPParser


def analyze_text_quality(text: str) -> Dict[str, Any]:
    """Analyze text quality with detailed metrics."""
    if not text:
        return {'quality_score': 0}
    
    # Character counting
    korean_chars = sum(1 for c in text if 0xAC00 <= ord(c) <= 0xD7AF)
    english_chars = sum(1 for c in text if c.isalpha() and ord(c) < 128)
    numbers = sum(1 for c in text if c.isdigit())
    spaces = text.count(' ')
    newlines = text.count('\n')
    
    # Noise detection
    noise_chars = {
        'ࡂ': text.count('ࡂ'),
        'ृ': text.count('ृ'),
        '�': text.count('�'),
        'control': sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t'),
    }
    total_noise = sum(noise_chars.values())
    
    # Quality metrics
    total_chars = len(text)
    readable_chars = korean_chars + english_chars + numbers + spaces + newlines
    quality_score = (readable_chars / total_chars * 100) if total_chars > 0 else 0
    
    # Extract sample Korean words (if any)
    korean_words = re.findall(r'[가-힣]+', text)[:10]  # First 10 Korean words
    
    return {
        'total_chars': total_chars,
        'korean_chars': korean_chars,
        'english_chars': english_chars,
        'numbers': numbers,
        'korean_ratio': (korean_chars / total_chars * 100) if total_chars > 0 else 0,
        'noise_ratio': (total_noise / total_chars * 100) if total_chars > 0 else 0,
        'quality_score': quality_score,
        'noise_breakdown': noise_chars,
        'sample_korean_words': korean_words
    }


def test_parser_comparison(file_path: str):
    """Compare all three parsers on a single file."""
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None
    
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path) / 1024  # KB
    
    print(f"\n{'='*80}")
    print(f"📄 Testing: {file_name}")
    print(f"📦 File size: {file_size:.2f} KB")
    print(f"{'='*80}")
    
    results = {}
    
    # Test Enhanced Parser
    print("\n1️⃣ Enhanced Parser (Original):")
    print("-" * 40)
    try:
        enhanced_parser = EnhancedHWPParser()
        enhanced_result = enhanced_parser.parse(file_path)
        enhanced_text = enhanced_result.get('text', '')
        enhanced_quality = analyze_text_quality(enhanced_text)
        
        print(f"📄 Text length: {enhanced_quality['total_chars']:,} chars")
        print(f"🇰🇷 Korean ratio: {enhanced_quality['korean_ratio']:.1f}%")
        print(f"⚠️ Noise ratio: {enhanced_quality['noise_ratio']:.2f}%")
        print(f"🎯 Quality score: {enhanced_quality['quality_score']:.1f}%")
        if enhanced_quality['noise_breakdown']['ࡂ'] > 0 or enhanced_quality['noise_breakdown']['ृ'] > 0:
            print(f"🔍 Noise: ࡂ={enhanced_quality['noise_breakdown']['ࡂ']}, ृ={enhanced_quality['noise_breakdown']['ृ']}")
        if enhanced_quality['sample_korean_words']:
            print(f"📝 Korean words found: {', '.join(enhanced_quality['sample_korean_words'][:5])}")
        
        results['enhanced'] = enhanced_quality
    except Exception as e:
        print(f"❌ Error: {e}")
        results['enhanced'] = {'total_chars': 0, 'quality_score': 0}
    
    # Test Improved Parser
    print("\n2️⃣ Improved Parser (Strict):")
    print("-" * 40)
    try:
        improved_parser = ImprovedHWPParser()
        improved_result = improved_parser.parse(file_path)
        improved_text = improved_result.get('text', '')
        improved_quality = analyze_text_quality(improved_text)
        
        print(f"📄 Text length: {improved_quality['total_chars']:,} chars")
        print(f"🇰🇷 Korean ratio: {improved_quality['korean_ratio']:.1f}%")
        print(f"⚠️ Noise ratio: {improved_quality['noise_ratio']:.2f}%")
        print(f"🎯 Quality score: {improved_quality['quality_score']:.1f}%")
        if improved_quality['sample_korean_words']:
            print(f"📝 Korean words found: {', '.join(improved_quality['sample_korean_words'][:5])}")
        
        results['improved'] = improved_quality
    except Exception as e:
        print(f"❌ Error: {e}")
        results['improved'] = {'total_chars': 0, 'quality_score': 0}
    
    # Test Hybrid Parser
    print("\n3️⃣ Hybrid Parser (New):")
    print("-" * 40)
    try:
        hybrid_parser = HybridHWPParser()
        hybrid_result = hybrid_parser.parse(file_path)
        hybrid_text = hybrid_result.get('text', '')
        hybrid_quality = analyze_text_quality(hybrid_text)
        
        print(f"📄 Text length: {hybrid_quality['total_chars']:,} chars")
        print(f"🇰🇷 Korean ratio: {hybrid_quality['korean_ratio']:.1f}%")
        print(f"⚠️ Noise ratio: {hybrid_quality['noise_ratio']:.2f}%")
        print(f"🎯 Quality score: {hybrid_quality['quality_score']:.1f}%")
        if hybrid_quality['noise_breakdown']['ࡂ'] > 0 or hybrid_quality['noise_breakdown']['ृ'] > 0:
            print(f"🔍 Noise: ࡂ={hybrid_quality['noise_breakdown']['ࡂ']}, ृ={hybrid_quality['noise_breakdown']['ृ']}")
        if hybrid_quality['sample_korean_words']:
            print(f"📝 Korean words found: {', '.join(hybrid_quality['sample_korean_words'][:5])}")
        
        # Show sample text
        if hybrid_text:
            print(f"\n📖 Sample (first 200 chars):")
            print(hybrid_text[:200])
        
        results['hybrid'] = hybrid_quality
    except Exception as e:
        print(f"❌ Error: {e}")
        results['hybrid'] = {'total_chars': 0, 'quality_score': 0}
    
    # Comparison
    print("\n4️⃣ Comparison:")
    print("-" * 40)
    
    print(f"📊 Text Length:")
    print(f"  Enhanced: {results['enhanced']['total_chars']:,} chars")
    print(f"  Improved: {results['improved']['total_chars']:,} chars")
    print(f"  Hybrid:   {results['hybrid']['total_chars']:,} chars")
    
    print(f"\n🇰🇷 Korean Content:")
    print(f"  Enhanced: {results['enhanced'].get('korean_ratio', 0):.1f}%")
    print(f"  Improved: {results['improved'].get('korean_ratio', 0):.1f}%")
    print(f"  Hybrid:   {results['hybrid'].get('korean_ratio', 0):.1f}%")
    
    print(f"\n🎯 Quality Score:")
    print(f"  Enhanced: {results['enhanced']['quality_score']:.1f}%")
    print(f"  Improved: {results['improved']['quality_score']:.1f}%")
    print(f"  Hybrid:   {results['hybrid']['quality_score']:.1f}%")
    
    # Verdict
    if results['hybrid']['total_chars'] > results['improved']['total_chars'] * 2:
        if results['hybrid'].get('noise_ratio', 100) < 1:
            print("\n✅ EXCELLENT: Hybrid achieves high extraction with low noise!")
        else:
            print("\n✅ GOOD: Hybrid extracts more text, but check noise levels")
    elif results['hybrid']['total_chars'] > results['improved']['total_chars']:
        print("\n✅ IMPROVED: Hybrid extracts more than Improved parser")
    else:
        print("\n⚠️ CHECK: Hybrid may need tuning")
    
    return results


def main():
    """Main test function."""
    
    test_files = [
        "/Users/a/Downloads/2025년+불량분석+및+소자제조+교육생+모집공고-하반기.hwp",
        "/Users/a/Downloads/공고문(2025+경영혁신+외식서비스+지원+사업).hwp",
        "/Users/a/Downloads/(공고문)+부산광역시+국제협력R&amp;D+기획+수요조사+공고.hwp",
        "/Users/a/Downloads/2025년 포천시 중소기업 노동자 기숙사 임차비 지원사업 모집 공고.hwp"
    ]
    
    print("🚀 Hybrid HWP Parser Comprehensive Test")
    print("=" * 80)
    print("Testing new hybrid approach that combines:")
    print("• Comprehensive extraction from EnhancedHWPParser")
    print("• Clean output from ImprovedHWPParser")
    print("• Korean text preservation")
    
    all_results = []
    
    for file_path in test_files:
        if os.path.exists(file_path):
            results = test_parser_comparison(file_path)
            if results:
                all_results.append({
                    'file': os.path.basename(file_path),
                    'results': results
                })
    
    # Summary
    if all_results:
        print("\n" + "=" * 80)
        print("📊 OVERALL SUMMARY")
        print("=" * 80)
        
        # Calculate averages
        avg_enhanced_chars = sum(r['results']['enhanced']['total_chars'] for r in all_results) / len(all_results)
        avg_improved_chars = sum(r['results']['improved']['total_chars'] for r in all_results) / len(all_results)
        avg_hybrid_chars = sum(r['results']['hybrid']['total_chars'] for r in all_results) / len(all_results)
        
        avg_enhanced_korean = sum(r['results']['enhanced'].get('korean_ratio', 0) for r in all_results) / len(all_results)
        avg_improved_korean = sum(r['results']['improved'].get('korean_ratio', 0) for r in all_results) / len(all_results)
        avg_hybrid_korean = sum(r['results']['hybrid'].get('korean_ratio', 0) for r in all_results) / len(all_results)
        
        avg_enhanced_quality = sum(r['results']['enhanced']['quality_score'] for r in all_results) / len(all_results)
        avg_improved_quality = sum(r['results']['improved']['quality_score'] for r in all_results) / len(all_results)
        avg_hybrid_quality = sum(r['results']['hybrid']['quality_score'] for r in all_results) / len(all_results)
        
        print(f"\n📈 Average Performance:")
        print(f"┌{'─'*20}┬{'─'*15}┬{'─'*15}┬{'─'*15}┐")
        print(f"│ {'Parser':<18} │ {'Text (chars)':>13} │ {'Korean (%)':>13} │ {'Quality (%)':>13} │")
        print(f"├{'─'*20}┼{'─'*15}┼{'─'*15}┼{'─'*15}┤")
        print(f"│ {'Enhanced':<18} │ {avg_enhanced_chars:>13,.0f} │ {avg_enhanced_korean:>13.1f} │ {avg_enhanced_quality:>13.1f} │")
        print(f"│ {'Improved':<18} │ {avg_improved_chars:>13,.0f} │ {avg_improved_korean:>13.1f} │ {avg_improved_quality:>13.1f} │")
        print(f"│ {'Hybrid':<18} │ {avg_hybrid_chars:>13,.0f} │ {avg_hybrid_korean:>13.1f} │ {avg_hybrid_quality:>13.1f} │")
        print(f"└{'─'*20}┴{'─'*15}┴{'─'*15}┴{'─'*15}┘")
        
        # Final verdict
        print("\n🎯 Final Assessment:")
        if avg_hybrid_chars > avg_improved_chars * 2 and avg_hybrid_korean > 10:
            print("✅ SUCCESS: Hybrid parser achieves optimal balance!")
            print(f"   • Extracts {avg_hybrid_chars/avg_improved_chars:.1f}x more text than Improved")
            print(f"   • Preserves {avg_hybrid_korean:.1f}% Korean content")
            print(f"   • Quality score: {avg_hybrid_quality:.1f}%")
        elif avg_hybrid_chars > avg_improved_chars:
            print("⚠️ PARTIAL SUCCESS: Hybrid improves extraction but needs refinement")
        else:
            print("❌ NEEDS WORK: Hybrid parser requires further optimization")


if __name__ == "__main__":
    main()