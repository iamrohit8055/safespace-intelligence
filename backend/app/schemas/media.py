"""Schemas for report photographic media evidence."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportMediaResponse(BaseModel):
    """Sanitized public-facing representation of uploaded report photographic media."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Unique media identifier")
    report_id: uuid.UUID = Field(description="Associated report UUID")
    mime_type: str = Field(description="Validated MIME type (image/jpeg, image/png, image/webp)")
    file_size_bytes: int = Field(description="Size of image file in bytes")
    checksum_sha256: str = Field(description="SHA-256 cryptographic digest of image file")
    width: int | None = Field(default=None, description="Image pixel width")
    height: int | None = Field(default=None, description="Image pixel height")
    technical_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Sanitized technical metadata"
    )
    created_at: datetime = Field(description="Upload timestamp")
    download_url: str | None = Field(default=None, description="Endpoint to download media file")
