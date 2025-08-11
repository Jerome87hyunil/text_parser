from pydantic import BaseModel
from typing import Optional


class ConvertResponse(BaseModel):
    file_id: str
    status: str
    message: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "completed",
                "message": "Conversion successful"
            }
        }