"""HTTP persistence contract for multi-image storylines."""

from typing import Annotated

import io
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from PIL import Image, UnidentifiedImageError

from backend.core.azure_storage import AzureBlobStorageService
from backend.core.config import settings

from backend.models.storylines import (
    Storyline,
    StorylineCreateRequest,
    StorylineFrameActionRequest,
    StorylineListResponse,
    StorylineMutationRequest,
    StorylinePlanUpdateRequest,
    StorylineStatus,
    StorylineReference,
)
from backend.storylines.manager import (
    StorylineConflictError,
    StorylineManager,
    StorylineNotFoundError,
)
from backend.storylines.orchestrator import StorylineOrchestrator
from backend.storylines.references import storyline_reference_prefix

router = APIRouter()


async def get_storyline_storage():
    service = AzureBlobStorageService()
    try:
        yield service
    finally:
        await service.close()


def get_storyline_manager(request: Request) -> StorylineManager | StorylineOrchestrator:
    manager = getattr(request.app.state, "storyline_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storyline service is not initialized",
        )
    return manager


def get_owner_id(
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> str:
    owner_id = (principal_id or browser_owner_id or "").strip()
    if not owner_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A trusted storyline owner identity is required",
        )
    if len(owner_id) > 256:
        raise HTTPException(status_code=400, detail="Invalid storyline owner identifier")
    return owner_id


def _not_found(exc: StorylineNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Storyline resource {exc} was not found")


def _conflict(exc: StorylineConflictError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.post("", response_model=Storyline, status_code=status.HTTP_201_CREATED)
async def create_storyline(
    payload: StorylineCreateRequest,
    request: Request,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> Storyline:
    try:
        return await get_storyline_manager(request).create(
            payload,
            owner_id=get_owner_id(principal_id, browser_owner_id),
        )
    except StorylineConflictError as exc:
        raise _conflict(exc) from exc


@router.get("", response_model=StorylineListResponse)
async def list_storylines(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[
        list[StorylineStatus] | None, Query(alias="status")
    ] = None,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> StorylineListResponse:
    items, total = await get_storyline_manager(request).list_storylines(
        owner_id=get_owner_id(principal_id, browser_owner_id),
        limit=limit,
        offset=offset,
        statuses=set(status_filter) if status_filter else None,
    )
    return StorylineListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/capabilities")
async def get_storyline_capabilities(request: Request) -> dict[str, object]:
    manager = get_storyline_manager(request)
    capabilities = getattr(manager, "capabilities", None)
    if capabilities is None:
        return {"models": []}
    return {"models": list(capabilities())}


@router.post(
    "/references",
    response_model=StorylineReference,
    status_code=status.HTTP_201_CREATED,
)
async def upload_storyline_reference(
    file: UploadFile = File(...),
    order: int = Form(..., ge=1, le=10),
    storage: AzureBlobStorageService = Depends(get_storyline_storage),
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> StorylineReference:
    owner_id = get_owner_id(principal_id, browser_owner_id)
    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(
            status_code=400,
            detail="Storyline references must be JPEG, PNG, or WebP images",
        )

    contents = await file.read()
    max_bytes = settings.GPT_IMAGE_MAX_FILE_SIZE_MB * 1024 * 1024
    if len(contents) >= max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                "Storyline references must be smaller than "
                f"{settings.GPT_IMAGE_MAX_FILE_SIZE_MB} MB"
            ),
        )
    try:
        with Image.open(io.BytesIO(contents)) as image:
            detected_format = (image.format or "").lower()
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid image",
        ) from exc
    expected_formats = {
        ".jpg": "jpeg",
        ".jpeg": "jpeg",
        ".png": "png",
        ".webp": "webp",
    }
    if detected_format != expected_formats[suffix]:
        raise HTTPException(
            status_code=400,
            detail="The image contents do not match the filename extension",
        )
    await file.seek(0)

    original_filename = filename
    file.filename = f"{uuid.uuid4()}{suffix}"
    uploaded = await storage.upload_asset(
        file,
        folder_path=storyline_reference_prefix(owner_id),
    )
    return StorylineReference(
        reference_id=str(uploaded["file_id"]),
        blob_name=str(uploaded["blob_name"]),
        url=str(uploaded["url"]),
        container=str(uploaded["container"]),
        content_type=str(uploaded["content_type"]),
        original_filename=original_filename,
        order=order,
    )


@router.get("/{storyline_id}", response_model=Storyline)
async def get_storyline(
    storyline_id: str,
    request: Request,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> Storyline:
    try:
        return await get_storyline_manager(request).get(
            storyline_id,
            owner_id=get_owner_id(principal_id, browser_owner_id),
        )
    except StorylineNotFoundError as exc:
        raise _not_found(exc) from exc


@router.put("/{storyline_id}/plan", response_model=Storyline)
async def update_storyline_plan(
    storyline_id: str,
    payload: StorylinePlanUpdateRequest,
    request: Request,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> Storyline:
    try:
        return await get_storyline_manager(request).update_plan(
            storyline_id,
            payload.plan,
            owner_id=get_owner_id(principal_id, browser_owner_id),
            expected_revision=payload.expected_revision,
            expected_etag=payload.expected_etag,
        )
    except StorylineNotFoundError as exc:
        raise _not_found(exc) from exc
    except StorylineConflictError as exc:
        raise _conflict(exc) from exc


@router.post(
    "/{storyline_id}/start",
    response_model=Storyline,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_storyline(
    storyline_id: str,
    request: Request,
    payload: Annotated[StorylineMutationRequest | None, Body()] = None,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> Storyline:
    payload = payload or StorylineMutationRequest()
    manager = get_storyline_manager(request)
    start_generation = getattr(manager, "start_generation", None)
    if start_generation is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storyline generation service is not initialized",
        )
    try:
        return await start_generation(
            storyline_id,
            owner_id=get_owner_id(principal_id, browser_owner_id),
            expected_revision=payload.expected_revision,
            expected_etag=payload.expected_etag,
        )
    except StorylineNotFoundError as exc:
        raise _not_found(exc) from exc
    except StorylineConflictError as exc:
        raise _conflict(exc) from exc


@router.post(
    "/{storyline_id}/planning/retry",
    response_model=Storyline,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_storyline_planning(
    storyline_id: str,
    request: Request,
    payload: Annotated[StorylineMutationRequest | None, Body()] = None,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> Storyline:
    payload = payload or StorylineMutationRequest()
    manager = get_storyline_manager(request)
    retry_planning = getattr(manager, "retry_planning", None)
    if retry_planning is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storyline planning service is not initialized",
        )
    try:
        return await retry_planning(
            storyline_id,
            owner_id=get_owner_id(principal_id, browser_owner_id),
            expected_revision=payload.expected_revision,
            expected_etag=payload.expected_etag,
        )
    except StorylineNotFoundError as exc:
        raise _not_found(exc) from exc
    except StorylineConflictError as exc:
        raise _conflict(exc) from exc


@router.post(
    "/{storyline_id}/cancel",
    response_model=Storyline,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_storyline(
    storyline_id: str,
    request: Request,
    payload: Annotated[StorylineMutationRequest | None, Body()] = None,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> Storyline:
    payload = payload or StorylineMutationRequest()
    try:
        return await get_storyline_manager(request).cancel(
            storyline_id,
            owner_id=get_owner_id(principal_id, browser_owner_id),
            expected_revision=payload.expected_revision,
            expected_etag=payload.expected_etag,
        )
    except StorylineNotFoundError as exc:
        raise _not_found(exc) from exc
    except StorylineConflictError as exc:
        raise _conflict(exc) from exc


@router.post(
    "/{storyline_id}/frames/{frame_id}/retry",
    response_model=Storyline,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_storyline_frame(
    storyline_id: str,
    frame_id: str,
    request: Request,
    payload: Annotated[StorylineFrameActionRequest | None, Body()] = None,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> Storyline:
    payload = payload or StorylineFrameActionRequest()
    try:
        return await get_storyline_manager(request).retry_frame(
            storyline_id,
            frame_id,
            owner_id=get_owner_id(principal_id, browser_owner_id),
            expected_revision=payload.expected_revision,
            expected_etag=payload.expected_etag,
            prompt=payload.prompt,
            copy_text=payload.copy_text,
        )
    except StorylineNotFoundError as exc:
        raise _not_found(exc) from exc
    except StorylineConflictError as exc:
        raise _conflict(exc) from exc


@router.post(
    "/{storyline_id}/frames/{frame_id}/regenerate",
    response_model=Storyline,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_storyline_frame(
    storyline_id: str,
    frame_id: str,
    request: Request,
    payload: Annotated[StorylineFrameActionRequest | None, Body()] = None,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> Storyline:
    payload = payload or StorylineFrameActionRequest()
    try:
        return await get_storyline_manager(request).regenerate_frame(
            storyline_id,
            frame_id,
            owner_id=get_owner_id(principal_id, browser_owner_id),
            expected_revision=payload.expected_revision,
            expected_etag=payload.expected_etag,
            prompt=payload.prompt,
            copy_text=payload.copy_text,
        )
    except StorylineNotFoundError as exc:
        raise _not_found(exc) from exc
    except StorylineConflictError as exc:
        raise _conflict(exc) from exc
