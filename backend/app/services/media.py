"""Service layer for secure report photographic evidence storage, processing, and retrieval."""

import hashlib
import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.iam import User
from app.models.reporting import Report, ReportMedia

ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


def upload_report_media(
    db: Session,
    report_id: uuid.UUID,
    file: UploadFile,
    current_user: User,
) -> ReportMedia:
    """Validate, sanitize (strip EXIF), persist to storage, and record photographic evidence.

    Args:
        db: Active SQLAlchemy database session.
        report_id: Target report UUID.
        file: Uploaded image file from multipart form data.
        current_user: Authenticated caller (reporter, verifier, or admin).

    Returns:
        ReportMedia: Persisted media record.
    """
    settings = get_settings()

    # 1. Verify report existence and caller authorization
    report = db.execute(select(Report).where(Report.id == report_id)).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found.",
        )

    user_roles = [r.name for r in current_user.roles]
    is_staff = any(r in ("admin", "verifier") for r in user_roles)
    if not is_staff and report.reporter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to upload media for this report.",
        )

    # 2. Validate MIME type
    content_type = file.content_type.lower() if file.content_type else ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported media type '{content_type}'. "
                "Only image/jpeg, image/png, and image/webp are accepted."
            ),
        )

    # 3. Read raw file contents and validate file size
    raw_content = file.file.read()
    if len(raw_content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(raw_content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES} bytes (15 MB)."
            ),
        )

    # 4. Validate image integrity and strip EXIF metadata using Pillow
    try:
        # Verify valid image structure
        test_img = Image.open(io.BytesIO(raw_content))
        test_img.verify()

        # Reopen image to access pixels and dimensions
        img = Image.open(io.BytesIO(raw_content))
        width, height = img.size
        if width <= 0 or height <= 0:
            raise ValueError("Image dimensions must be positive.")

        # Re-encode image to clean buffer to strip sensitive EXIF / GPS tags
        clean_buf = io.BytesIO()
        ext = ALLOWED_MIME_TYPES[content_type]
        pil_format = "JPEG" if ext == "jpg" else ("PNG" if ext == "png" else "WEBP")

        # Convert RGBA to RGB for JPEG if necessary
        if pil_format == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.save(clean_buf, format=pil_format, exif=b"")
        clean_bytes = clean_buf.getvalue()
        file_size = len(clean_bytes)
        checksum = hashlib.sha256(clean_bytes).hexdigest()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupted or invalid image data: {e}",
        ) from e

    # 5. Check duplicate image checksum constraint
    existing = db.execute(
        select(ReportMedia).where(
            ReportMedia.report_id == report_id,
            ReportMedia.checksum_sha256 == checksum,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This exact image has already been uploaded for this report.",
        )

    # 6. Generate safe storage identifier (preventing path traversal)
    media_uuid = uuid.uuid4()
    storage_key = f"{report_id}/{media_uuid}.{ext}"

    # 7. Persist to storage backend (Local storage with configurable root)
    base_storage_dir = Path(settings.MEDIA_STORAGE_PATH).resolve()
    target_path = (base_storage_dir / storage_key).resolve()

    if not target_path.is_relative_to(base_storage_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid storage path traversal attempt.",
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(clean_bytes)

    # 8. Record metadata in PostgreSQL
    media = ReportMedia(
        id=media_uuid,
        report_id=report_id,
        storage_provider=settings.MEDIA_STORAGE_PROVIDER,
        storage_bucket=settings.MEDIA_STORAGE_BUCKET,
        storage_key=storage_key,
        mime_type=content_type,
        file_size_bytes=file_size,
        checksum_sha256=checksum,
        width=width,
        height=height,
        technical_metadata={
            "format": pil_format,
            "color_mode": img.mode,
            "stripped_exif": True,
        },
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    return media


def get_report_media_file(
    db: Session,
    report_id: uuid.UUID,
    media_id: uuid.UUID,
    current_user: User | None = None,
) -> tuple[Path, str]:
    """Retrieve absolute file path and MIME type for stored report photographic media.

    Enforces authorization: report owners, verifiers, admins, or public for verified reports.

    Args:
        db: Active SQLAlchemy database session.
        report_id: Associated report UUID.
        media_id: Unique media record UUID.
        current_user: Authenticated user, or None if public access.

    Returns:
        tuple[Path, str]: (absolute file path on disk, MIME type).
    """
    settings = get_settings()

    report = db.execute(select(Report).where(Report.id == report_id)).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    if current_user is not None:
        user_roles = [r.name for r in current_user.roles]
        is_staff = any(r in ("admin", "verifier") for r in user_roles)
        if not is_staff and report.reporter_id != current_user.id and report.status != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access media for this report.",
            )
    else:
        # Unauthenticated: only verified reports are public
        if report.status != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view non-verified report media.",
            )

    media = db.execute(
        select(ReportMedia).where(
            ReportMedia.id == media_id,
            ReportMedia.report_id == report_id,
        )
    ).scalar_one_or_none()
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media record not found.",
        )

    base_storage_dir = Path(settings.MEDIA_STORAGE_PATH).resolve()
    target_path = (base_storage_dir / media.storage_key).resolve()

    if not target_path.is_relative_to(base_storage_dir) or not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file does not exist on storage.",
        )

    return target_path, media.mime_type
