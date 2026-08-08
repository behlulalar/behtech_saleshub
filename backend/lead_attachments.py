import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from config import settings
from database import LeadAttachment, User

ALLOWED_EXTENSIONS = frozenset(
    ext.strip().lower()
    for ext in settings.allowed_upload_extensions.split(",")
    if ext.strip()
)
ALLOWED_MIME_TYPES = frozenset(
    mime.strip().lower()
    for mime in settings.allowed_upload_mime_types.split(",")
    if mime.strip()
)
MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._\- ()]")


def upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root


def lead_upload_dir(org_id: int, lead_id: int) -> Path:
    path = upload_root() / str(org_id) / str(lead_id)
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def org_upload_dir(org_id: int) -> Path:
    return upload_root() / str(org_id)


def sanitize_original_filename(name: str) -> str:
    cleaned = (name or "dosya").replace("\\", "/").split("/")[-1].strip()
    cleaned = SAFE_FILENAME.sub("_", cleaned)
    return cleaned[:200] or "dosya"


def extension_for_filename(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in ALLOWED_EXTENSIONS:
        return ext
    return ""


def validate_upload(file: UploadFile, size_bytes: int) -> tuple[str, str]:
    if size_bytes <= 0:
        raise HTTPException(status_code=400, detail="Boş dosya yüklenemez")
    if size_bytes > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Dosya boyutu en fazla {settings.max_upload_size_mb} MB olabilir",
        )

    original = sanitize_original_filename(file.filename or "")
    ext = extension_for_filename(original)
    if not ext:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen dosya türü. İzin verilen uzantılar: {allowed}",
        )

    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya türü")

    return original, ext


async def read_upload_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Dosya boyutu en fazla {settings.max_upload_size_mb} MB olabilir",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def stored_file_path(attachment: LeadAttachment) -> Path:
    return lead_upload_dir(attachment.user_id, attachment.lead_id) / attachment.stored_filename


def list_attachments(
    db: Session, org_id: int, lead_id: int, status: str = "active"
) -> list[LeadAttachment]:
    query = db.query(LeadAttachment).filter(
        LeadAttachment.user_id == org_id,
        LeadAttachment.lead_id == lead_id,
    )

    if status == "active":
        query = query.filter(LeadAttachment.archived_at.is_(None))
        query = query.order_by(LeadAttachment.created_at.desc(), LeadAttachment.id.desc())
    elif status == "archived":
        query = query.filter(LeadAttachment.archived_at.isnot(None))
        query = query.order_by(LeadAttachment.archived_at.desc(), LeadAttachment.id.desc())
    else:
        query = query.order_by(
            LeadAttachment.archived_at.asc().nullsfirst(),
            LeadAttachment.created_at.desc(),
            LeadAttachment.id.desc(),
        )

    return query.all()


def get_attachment_or_404(
    db: Session, org_id: int, lead_id: int, attachment_id: int
) -> LeadAttachment:
    attachment = (
        db.query(LeadAttachment)
        .filter(
            LeadAttachment.id == attachment_id,
            LeadAttachment.user_id == org_id,
            LeadAttachment.lead_id == lead_id,
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    return attachment


def attachment_response(
    attachment: LeadAttachment,
    uploader: User | None,
    archiver: User | None = None,
) -> dict:
    return {
        "id": attachment.id,
        "lead_id": attachment.lead_id,
        "label": attachment.label or attachment.original_filename,
        "original_filename": attachment.original_filename,
        "mime_type": attachment.mime_type,
        "size_bytes": attachment.size_bytes,
        "version_number": attachment.version_number or 1,
        "replaces_attachment_id": attachment.replaces_attachment_id,
        "is_archived": attachment.archived_at is not None,
        "archived_at": attachment.archived_at,
        "archived_by_username": archiver.username if archiver else None,
        "uploaded_by_username": uploader.username if uploader else None,
        "created_at": attachment.created_at,
    }


def archive_attachment(attachment: LeadAttachment, user: User) -> None:
    if attachment.archived_at is not None:
        raise HTTPException(status_code=400, detail="Dosya zaten arşivde")
    attachment.archived_at = datetime.utcnow()
    attachment.archived_by = user.id


def prepare_replacement(
    db: Session,
    org_id: int,
    lead_id: int,
    replace_attachment_id: int | None,
    user: User,
) -> tuple[int, int | None, str | None]:
    if not replace_attachment_id:
        return 1, None, None

    previous = get_attachment_or_404(db, org_id, lead_id, replace_attachment_id)
    if previous.archived_at is not None:
        raise HTTPException(status_code=400, detail="Arşivlenmiş dosya yenilenemez")
    archive_attachment(previous, user)
    return (previous.version_number or 1) + 1, previous.id, previous.label


def delete_attachment_file(attachment: LeadAttachment) -> None:
    path = stored_file_path(attachment)
    if path.is_file():
        path.unlink()


def delete_attachment_record(db: Session, attachment: LeadAttachment) -> None:
    delete_attachment_file(attachment)
    db.delete(attachment)


def delete_attachments_for_lead(db: Session, org_id: int, lead_id: int) -> None:
    attachments = list_attachments(db, org_id, lead_id, status="all")
    for attachment in attachments:
        delete_attachment_file(attachment)
        db.delete(attachment)


def delete_attachments_for_org(org_id: int) -> None:
    org_dir = org_upload_dir(org_id)
    if org_dir.is_dir():
        for path in sorted(org_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        org_dir.rmdir()


def save_attachment_file(org_id: int, lead_id: int, ext: str, content: bytes) -> str:
    stored = f"{uuid.uuid4().hex}{ext}"
    path = lead_upload_dir(org_id, lead_id) / stored
    path.write_bytes(content)
    os.chmod(path, 0o600)
    return stored


def user_map(db: Session, user_ids: set[int]) -> dict[int, User]:
    if not user_ids:
        return {}
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    return {user.id: user for user in users}


def uploader_map(db: Session, attachments: list[LeadAttachment]) -> dict[int, User]:
    ids = {attachment.uploaded_by for attachment in attachments if attachment.uploaded_by}
    ids.update(attachment.archived_by for attachment in attachments if attachment.archived_by)
    return user_map(db, ids)
