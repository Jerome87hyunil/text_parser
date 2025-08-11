"""
PDF generator tests.
"""
import pytest
import tempfile
import os
from pathlib import Path

from app.services.pdf_generator import PDFGenerator


@pytest.mark.asyncio
async def test_pdf_generator_initialization():
    """Test PDF generator initialization."""
    generator = PDFGenerator()
    assert generator is not None
    # Should find a font on most systems
    assert generator.default_font_path is None or os.path.exists(generator.default_font_path)


@pytest.mark.asyncio
async def test_generate_pdf_with_reportlab(sample_hwp_content):
    """Test PDF generation with ReportLab."""
    generator = PDFGenerator()
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        output_path = tmp.name
    
    try:
        # Generate PDF
        success = await generator._generate_with_reportlab(sample_hwp_content, output_path)
        assert success is True
        
        # Check file exists and has content
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
        
        # Check it's a valid PDF
        with open(output_path, 'rb') as f:
            header = f.read(5)
            assert header == b'%PDF-'
            
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


@pytest.mark.asyncio
async def test_generate_pdf_with_empty_content():
    """Test PDF generation with empty content."""
    generator = PDFGenerator()
    empty_content = {
        "metadata": {},
        "paragraphs": [],
        "tables": [],
        "text": ""
    }
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        output_path = tmp.name
    
    try:
        # Should handle empty content gracefully
        success = await generator.generate_from_hwp_content(empty_content, output_path)
        assert success is True
        
        # Check file exists
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
        
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


@pytest.mark.asyncio
async def test_generate_pdf_with_korean_text():
    """Test PDF generation with Korean text."""
    generator = PDFGenerator()
    korean_content = {
        "metadata": {
            "title": "한글 문서",
            "author": "홍길동"
        },
        "paragraphs": [
            {"text": "안녕하세요. 이것은 한글 테스트입니다."},
            {"text": "한글 폰트가 제대로 표시되는지 확인합니다."},
            {"text": "다양한 한글 문자: 가나다라마바사아자차카타파하"}
        ],
        "text": "안녕하세요. 이것은 한글 테스트입니다."
    }
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        output_path = tmp.name
    
    try:
        # Generate PDF with Korean content
        success = await generator.generate_from_hwp_content(korean_content, output_path)
        assert success is True
        
        # Check file exists and has reasonable size
        assert os.path.exists(output_path)
        file_size = os.path.getsize(output_path)
        assert file_size > 1000  # Should have some content
        
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_escape_text_for_reportlab():
    """Test text escaping for ReportLab."""
    generator = PDFGenerator()
    
    # Test escaping special characters
    test_cases = [
        ("Hello & World", "Hello &amp; World"),
        ("<tag>", "&lt;tag&gt;"),
        ("A > B & C < D", "A &gt; B &amp; C &lt; D"),
        ("Normal text", "Normal text")
    ]
    
    for input_text, expected in test_cases:
        result = generator._escape_text_for_reportlab(input_text)
        assert result == expected