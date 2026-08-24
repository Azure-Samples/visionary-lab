"""HTTP contract for durable asynchronous image-generation jobs."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)

from backend.jobs.manager import (
    ImageJobConflictError,
    ImageJobManager,
    ImageJobNotFoundError,
)
from backend.models.image_jobs import (
    ImageJob,
    ImageJobCreateRequest,
    ImageJobListResponse,
    ImageJobStatus,
)

router = APIRouter()


def get_image_job_manager(request: Request) -> ImageJobManager:
    manager = getattr(request.app.state, "image_job_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image job service is not initialized",
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
            detail="A trusted image-job owner identity is required",
        )
    if not owner_id or len(owner_id) > 256:
        raise HTTPException(
            status_code=400, detail="Invalid image job owner identifier"
        )
    return owner_id


def _not_found(exc: ImageJobNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Image job {exc} was not found")


@router.post(
    "/jobs",
    response_model=ImageJob,
    status_code=status.HTTP_202_ACCEPTED,
    name="create_image_job",
)
async def create_image_job(
    payload: ImageJobCreateRequest,
    request: Request,
    response: Response,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> ImageJob:
    manager = get_image_job_manager(request)
    owner_id = get_owner_id(principal_id, browser_owner_id)
    try:
        job = await manager.submit(payload, owner_id=owner_id)
    except ImageJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    response.headers["Location"] = str(request.url_for("get_image_job", job_id=job.id))
    response.headers["Retry-After"] = "2"
    return job


@router.get("/jobs", response_model=ImageJobListResponse, name="list_image_jobs")
async def list_image_jobs(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    status_filter: Annotated[list[ImageJobStatus] | None, Query(alias="status")] = None,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> ImageJobListResponse:
    manager = get_image_job_manager(request)
    owner_id = get_owner_id(principal_id, browser_owner_id)
    jobs, total = await manager.list_jobs(
        owner_id=owner_id,
        limit=limit,
        statuses=set(status_filter) if status_filter else None,
    )
    return ImageJobListResponse(jobs=jobs, total=total)


@router.get("/jobs/{job_id}", response_model=ImageJob, name="get_image_job")
async def get_image_job(
    job_id: str,
    request: Request,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> ImageJob:
    try:
        return await get_image_job_manager(request).get(
            job_id,
            owner_id=get_owner_id(principal_id, browser_owner_id),
        )
    except ImageJobNotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete(
    "/jobs/{job_id}",
    response_model=ImageJob,
    status_code=status.HTTP_202_ACCEPTED,
    name="cancel_image_job",
)
async def cancel_image_job(
    job_id: str,
    request: Request,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> ImageJob:
    try:
        return await get_image_job_manager(request).cancel(
            job_id,
            owner_id=get_owner_id(principal_id, browser_owner_id),
        )
    except ImageJobNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/jobs/{job_id}/retry",
    response_model=ImageJob,
    status_code=status.HTTP_202_ACCEPTED,
    name="retry_image_job",
)
async def retry_image_job(
    job_id: str,
    request: Request,
    response: Response,
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    browser_owner_id: Annotated[str | None, Header(alias="X-Image-Job-Owner")] = None,
) -> ImageJob:
    try:
        job = await get_image_job_manager(request).retry(
            job_id,
            owner_id=get_owner_id(principal_id, browser_owner_id),
        )
    except ImageJobNotFoundError as exc:
        raise _not_found(exc) from exc
    except ImageJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    response.headers["Location"] = str(request.url_for("get_image_job", job_id=job.id))
    response.headers["Retry-After"] = "2"
    return job
