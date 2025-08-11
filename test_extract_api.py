#!/usr/bin/env python
"""
Test script for HWP extraction API endpoints.
Tests the new JSON/Text/Markdown extraction capabilities.
"""
import httpx
import asyncio
import json
from pathlib import Path
import sys


async def test_extract_endpoints():
    """Test the extraction API endpoints."""
    
    # Configuration
    base_url = "http://localhost:8000"
    test_file = "tests/test_files/sample.hwp"
    
    # Check if test file exists
    if not Path(test_file).exists():
        print(f"Warning: Test file {test_file} not found")
        print("Please provide a test HWP file or update the path")
        test_file = input("Enter path to HWP file (or press Enter to skip): ").strip()
        if not test_file:
            print("No test file provided, exiting")
            return
    
    async with httpx.AsyncClient() as client:
        # Test 1: JSON extraction
        print("\n" + "="*50)
        print("Testing HWP to JSON extraction...")
        print("="*50)
        
        try:
            with open(test_file, "rb") as f:
                files = {"file": (Path(test_file).name, f, "application/octet-stream")}
                response = await client.post(
                    f"{base_url}/api/v1/extract/hwp-to-json",
                    files=files,
                    params={
                        "include_metadata": True,
                        "include_structure": True,
                        "include_statistics": True
                    }
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success: {result['message']}")
                print(f"📄 Filename: {result['filename']}")
                
                content = result['content']
                print(f"\n📊 Statistics:")
                if 'statistics' in content:
                    stats = content['statistics']
                    print(f"  - Characters: {stats.get('char_count', 0):,}")
                    print(f"  - Words: {stats.get('word_count', 0):,}")
                    print(f"  - Paragraphs: {stats.get('paragraph_count', 0)}")
                    print(f"  - Tables: {stats.get('table_count', 0)}")
                    print(f"  - Korean ratio: {stats.get('korean_ratio', 0):.1%}")
                
                print(f"\n📑 Metadata:")
                if 'metadata' in content:
                    for key, value in content['metadata'].items():
                        if value:
                            print(f"  - {key}: {value}")
                
                print(f"\n📝 Sample text (first 200 chars):")
                if 'text' in content:
                    print(f"  {content['text'][:200]}...")
                
                # Save JSON output
                output_file = "output/extracted_content.json"
                Path("output").mkdir(exist_ok=True)
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)
                print(f"\n💾 Full JSON saved to: {output_file}")
                
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.json())
        
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        # Test 2: Plain text extraction
        print("\n" + "="*50)
        print("Testing HWP to Text extraction...")
        print("="*50)
        
        try:
            with open(test_file, "rb") as f:
                files = {"file": (Path(test_file).name, f, "application/octet-stream")}
                response = await client.post(
                    f"{base_url}/api/v1/extract/hwp-to-text",
                    files=files,
                    params={"preserve_formatting": True}
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success: {result['message']}")
                
                text = result['content']['text']
                print(f"\n📝 Text length: {len(text):,} characters")
                print(f"📝 Sample text (first 300 chars):")
                print(f"  {text[:300]}...")
                
                # Save text output
                output_file = "output/extracted_text.txt"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"\n💾 Full text saved to: {output_file}")
                
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.json())
        
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        # Test 3: Markdown extraction
        print("\n" + "="*50)
        print("Testing HWP to Markdown extraction...")
        print("="*50)
        
        try:
            with open(test_file, "rb") as f:
                files = {"file": (Path(test_file).name, f, "application/octet-stream")}
                response = await client.post(
                    f"{base_url}/api/v1/extract/hwp-to-markdown",
                    files=files,
                    params={"include_metadata": True}
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success: {result['message']}")
                
                markdown = result['content']['markdown']
                print(f"\n📝 Markdown length: {len(markdown):,} characters")
                print(f"📝 Sample markdown (first 300 chars):")
                print(f"  {markdown[:300]}...")
                
                # Save markdown output
                output_file = "output/extracted_content.md"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(markdown)
                print(f"\n💾 Full markdown saved to: {output_file}")
                
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.json())
        
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print("\n" + "="*50)
        print("Testing complete!")
        print("="*50)


async def test_ai_integration():
    """Test AI-ready JSON format."""
    print("\n" + "="*50)
    print("Testing AI Integration Format...")
    print("="*50)
    
    # Load extracted JSON
    json_file = "output/extracted_content.json"
    if Path(json_file).exists():
        with open(json_file, "r", encoding="utf-8") as f:
            content = json.load(f)
        
        # Prepare AI-ready format
        ai_prompt = f"""
Please analyze the following document:

Title: {content.get('metadata', {}).get('title', 'Unknown')}
Author: {content.get('metadata', {}).get('author', 'Unknown')}

Document Statistics:
- Total words: {content.get('statistics', {}).get('word_count', 0)}
- Paragraphs: {content.get('statistics', {}).get('paragraph_count', 0)}
- Tables: {content.get('statistics', {}).get('table_count', 0)}

Content:
{content.get('text', '')[:1000]}...

Please provide:
1. A brief summary of the document
2. Key topics covered
3. Any important data or findings
"""
        
        print("AI-ready prompt created:")
        print("-" * 50)
        print(ai_prompt[:500] + "...")
        print("-" * 50)
        
        # Save AI prompt
        with open("output/ai_prompt.txt", "w", encoding="utf-8") as f:
            f.write(ai_prompt)
        print("\n💾 AI prompt saved to: output/ai_prompt.txt")
    else:
        print("No extracted JSON found. Run extract test first.")


if __name__ == "__main__":
    print("🚀 HWP Extraction API Test Suite")
    print("================================")
    print("This tests the new API endpoints optimized for AI analysis")
    
    # Run tests
    asyncio.run(test_extract_endpoints())
    asyncio.run(test_ai_integration())