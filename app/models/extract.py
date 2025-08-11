"""
Pydantic models for extraction endpoints.
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime


class ExtractFormat(str, Enum):
    """Supported extraction formats."""
    JSON = "json"
    TEXT = "text"
    MARKDOWN = "markdown"


class ExtractRequest(BaseModel):
    """Request model for extraction."""
    include_metadata: bool = Field(
        default=True,
        description="Include document metadata in response"
    )
    include_structure: bool = Field(
        default=True,
        description="Preserve document structure (headings, lists, tables)"
    )
    include_statistics: bool = Field(
        default=True,
        description="Include text statistics for analysis"
    )
    format: ExtractFormat = Field(
        default=ExtractFormat.JSON,
        description="Output format for extracted content"
    )


class DocumentMetadata(BaseModel):
    """Document metadata model."""
    title: Optional[str] = Field(None, description="Document title")
    author: Optional[str] = Field(None, description="Document author")
    subject: Optional[str] = Field(None, description="Document subject")
    keywords: Optional[str] = Field(None, description="Document keywords")
    created_date: Optional[str] = Field(None, description="Creation date")
    modified_date: Optional[str] = Field(None, description="Last modified date")
    creator: Optional[str] = Field(None, description="Creator application")
    language: Optional[str] = Field(None, description="Document language")
    page_count: Optional[int] = Field(None, description="Number of pages")


class TextStatistics(BaseModel):
    """Text statistics model."""
    char_count: int = Field(..., description="Total character count")
    char_count_no_spaces: int = Field(..., description="Character count without spaces")
    word_count: int = Field(..., description="Total word count")
    line_count: int = Field(..., description="Number of lines")
    paragraph_count: int = Field(..., description="Number of paragraphs")
    table_count: int = Field(..., description="Number of tables")
    list_count: int = Field(..., description="Number of lists")
    heading_count: int = Field(..., description="Number of headings")
    sentence_count: int = Field(..., description="Number of sentences")
    avg_sentence_length: float = Field(..., description="Average sentence length in words")
    avg_paragraph_length: Optional[float] = Field(None, description="Average paragraph length")
    korean_ratio: float = Field(..., description="Ratio of Korean characters")
    english_ratio: float = Field(..., description="Ratio of English characters")


class ParagraphInfo(BaseModel):
    """Paragraph information model."""
    index: int = Field(..., description="Paragraph index")
    text: str = Field(..., description="Paragraph text")
    type: str = Field(..., description="Paragraph type (normal, heading, list_item)")
    char_count: int = Field(..., description="Character count")
    word_count: int = Field(..., description="Word count")
    tags: List[str] = Field(default_factory=list, description="Semantic tags")


class TableInfo(BaseModel):
    """Table information model."""
    index: int = Field(..., description="Table index")
    rows: List[List[str]] = Field(..., description="Table rows")
    row_count: int = Field(..., description="Number of rows")
    col_count: int = Field(..., description="Number of columns")
    summary: str = Field(..., description="Table summary")


class ListInfo(BaseModel):
    """List information model."""
    type: str = Field(..., description="List type (ordered, unordered)")
    items: List[Dict[str, Any]] = Field(..., description="List items")
    start_index: int = Field(..., description="Start paragraph index")
    end_index: int = Field(..., description="End paragraph index")


class HeadingInfo(BaseModel):
    """Heading information model."""
    text: str = Field(..., description="Heading text")
    level: int = Field(..., description="Heading level (1-6)")
    index: int = Field(..., description="Paragraph index")
    type: str = Field(..., description="Heading type classification")


class ExtractResponse(BaseModel):
    """Response model for extraction."""
    success: bool = Field(..., description="Whether extraction was successful")
    filename: str = Field(..., description="Original filename")
    format: ExtractFormat = Field(..., description="Output format")
    content: Dict[str, Any] = Field(..., description="Extracted content")
    message: str = Field(..., description="Response message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "filename": "document.hwp",
                "format": "json",
                "content": {
                    "version": "1.0",
                    "extracted_at": "2024-01-01T00:00:00Z",
                    "metadata": {
                        "title": "Sample Document",
                        "author": "John Doe",
                        "language": "ko"
                    },
                    "text": "Document text content...",
                    "paragraphs": [
                        {
                            "index": 0,
                            "text": "First paragraph",
                            "type": "normal",
                            "char_count": 15,
                            "word_count": 2,
                            "tags": ["short"]
                        }
                    ],
                    "statistics": {
                        "char_count": 1000,
                        "word_count": 150,
                        "korean_ratio": 0.8
                    }
                },
                "message": "HWP content extracted successfully"
            }
        }