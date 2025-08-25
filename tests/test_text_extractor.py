"""
Test cases for TextExtractor service
"""
import pytest
from app.services.text_extractor import TextExtractor


class TestTextExtractor:
    """Test cases for TextExtractor class"""
    
    @pytest.fixture
    def extractor(self):
        """Create TextExtractor instance"""
        return TextExtractor()
    
    def test_extract_structured_basic(self, extractor, sample_hwp_content):
        """Test basic structured extraction"""
        result = extractor.extract_structured(sample_hwp_content)
        
        assert "text" in result
        assert "metadata" in result
        assert "paragraphs" in result
        assert "tables" in result
        assert "statistics" in result
        
        # Check statistics
        stats = result["statistics"]
        assert stats["char_count"] > 0
        assert stats["word_count"] > 0
        assert stats["paragraph_count"] == 3
        assert stats["table_count"] == 1
    
    def test_extract_structured_without_metadata(self, extractor, sample_hwp_content):
        """Test structured extraction without metadata"""
        result = extractor.extract_structured(
            sample_hwp_content,
            include_metadata=False
        )
        
        assert "metadata" not in result
        assert "text" in result
        assert "paragraphs" in result
    
    def test_extract_structured_without_structure(self, extractor, sample_hwp_content):
        """Test structured extraction without structure"""
        result = extractor.extract_structured(
            sample_hwp_content,
            include_structure=False
        )
        
        assert "paragraphs" not in result
        assert "tables" not in result
        assert "lists" not in result
        assert "text" in result
    
    def test_extract_structured_without_statistics(self, extractor, sample_hwp_content):
        """Test structured extraction without statistics"""
        result = extractor.extract_structured(
            sample_hwp_content,
            include_statistics=False
        )
        
        assert "statistics" not in result
        assert "text" in result
    
    def test_to_markdown_basic(self, extractor, sample_hwp_content):
        """Test basic markdown conversion"""
        result = extractor.to_markdown(sample_hwp_content)
        
        assert isinstance(result, str)
        # Title is in YAML frontmatter, not as header
        assert "title: Test Document" in result
        assert "This is the first paragraph" in result
        assert "| Header 1 | Header 2 |" in result  # Table markdown
    
    def test_to_markdown_without_metadata(self, extractor, sample_hwp_content):
        """Test markdown conversion without metadata"""
        result = extractor.to_markdown(
            sample_hwp_content,
            include_metadata=False
        )
        
        # Check that YAML frontmatter is not present
        lines = result.split('\n')
        assert lines[0] != "---"  # No YAML frontmatter
        assert "title:" not in result
        assert "author:" not in result
        
    def test_empty_content_handling(self, extractor):
        """Test handling of empty content"""
        empty_content = {
            "text": "",
            "paragraphs": [],
            "tables": []
        }
        
        result = extractor.extract_structured(empty_content)
        assert result["text"] == ""
        assert result["statistics"]["char_count"] == 0
        assert result["statistics"]["word_count"] == 0
        
    def test_korean_text_processing(self, extractor):
        """Test Korean text processing"""
        korean_content = {
            "text": "안녕하세요. 한글 테스트입니다.",
            "paragraphs": [
                {"text": "안녕하세요."},
                {"text": "한글 테스트입니다."}
            ]
        }
        
        result = extractor.extract_structured(korean_content)
        assert "안녕하세요" in result["text"]
        assert result["statistics"]["word_count"] > 0