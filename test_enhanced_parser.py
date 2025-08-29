#!/usr/bin/env python3
"""
Test script for Enhanced HWP Parser.
Tests various parsing strategies and fallback mechanisms.
"""
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.enhanced_hwp_parser import EnhancedHWPParser
from app.services.hwp_parser import HWPParser


def test_enhanced_parser():
    """Test the enhanced parser with the sample file."""
    test_file = "/Users/a/Downloads/2025년+불량분석+및+소자제조+교육생+모집공고-하반기.hwp"
    
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return
    
    print("=" * 60)
    print("🧪 Testing Enhanced HWP Parser")
    print("=" * 60)
    
    # Test Enhanced Parser directly
    print("\n1️⃣ Testing EnhancedHWPParser directly:")
    print("-" * 40)
    
    enhanced = EnhancedHWPParser()
    result = enhanced.parse(test_file)
    
    print(f"✅ Parsing method: {result.get('parsing_method', 'unknown')}")
    print(f"📄 Text length: {len(result.get('text', ''))}")
    print(f"📝 Paragraphs: {len(result.get('paragraphs', []))}")
    print(f"📊 Tables: {len(result.get('tables', []))}")
    
    if result.get('metadata'):
        print(f"📋 Metadata: {result['metadata']}")
    
    if result.get('errors'):
        print(f"⚠️ Errors: {result['errors']}")
    
    # Show text preview
    text = result.get('text', '')
    if text:
        print(f"\n📖 Text preview (first 500 chars):")
        print("-" * 40)
        print(text[:500])
        print("\n📖 Text preview (last 500 chars):")
        print("-" * 40)
        print(text[-500:])
    
    # Test through main HWPParser
    print("\n\n2️⃣ Testing through main HWPParser:")
    print("-" * 40)
    
    parser = HWPParser()
    text2 = parser.extract_text(test_file)
    
    print(f"📄 Text length: {len(text2)}")
    
    # Compare results
    print("\n\n3️⃣ Comparison:")
    print("-" * 40)
    
    original_length = 995  # Previously extracted length
    enhanced_length = len(text)
    improvement = ((enhanced_length - original_length) / original_length * 100) if original_length > 0 else 0
    
    print(f"📊 Original parser: {original_length} chars")
    print(f"📊 Enhanced parser: {enhanced_length} chars")
    print(f"📈 Improvement: {improvement:.1f}%")
    
    if enhanced_length > original_length * 2:
        print("✅ Significant improvement achieved!")
    elif enhanced_length > original_length:
        print("✅ Some improvement achieved")
    else:
        print("⚠️ No improvement detected")
    
    # Check for specific content that was missing
    missing_content_indicators = [
        "교육장비",
        "신청방법",
        "제출서류",
        "문의처"
    ]
    
    print("\n4️⃣ Content completeness check:")
    print("-" * 40)
    
    for indicator in missing_content_indicators:
        if indicator in text:
            print(f"✅ Found: {indicator}")
        else:
            print(f"❌ Missing: {indicator}")
    
    return result


def test_specific_strategies():
    """Test each strategy individually."""
    test_file = "/Users/a/Downloads/2025년+불량분석+및+소자제조+교육생+모집공고-하반기.hwp"
    
    if not os.path.exists(test_file):
        return
    
    print("\n" + "=" * 60)
    print("🔬 Testing Individual Strategies")
    print("=" * 60)
    
    from app.services.enhanced_hwp_parser import (
        HWP5PythonAPIStrategy,
        HWP5CLIStrategy,
        BodyTextDirectParser,
        EnhancedPrvTextStrategy
    )
    
    strategies = [
        HWP5PythonAPIStrategy(),
        HWP5CLIStrategy(),
        BodyTextDirectParser(),
        EnhancedPrvTextStrategy()
    ]
    
    for strategy in strategies:
        print(f"\n📌 Testing {strategy.__class__.__name__}:")
        print("-" * 40)
        
        if strategy.can_parse(test_file):
            print("✅ Can parse: Yes")
            try:
                result = strategy.parse(test_file)
                if result:
                    text_len = len(result.get('text', ''))
                    print(f"📄 Text extracted: {text_len} chars")
                else:
                    print("❌ No result returned")
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print("❌ Can parse: No")


if __name__ == "__main__":
    try:
        # Run main test
        result = test_enhanced_parser()
        
        # Run individual strategy tests
        test_specific_strategies()
        
        print("\n" + "=" * 60)
        print("✅ Test completed")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()