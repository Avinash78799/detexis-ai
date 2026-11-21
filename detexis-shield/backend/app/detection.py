"""Owner-visible inventory of the detection release actually installed."""
import os
from fastapi import APIRouter, Depends, Request
from .accounts import owner
from .rule_manifest import manifest

router = APIRouter()


@router.get("/app/api/detection")
def detection_manifest(user=Depends(owner)):
    return manifest()


@router.get("/app/detection")
def detection_page(request: Request, user=Depends(owner)):
    from .dashboard import templates
    return templates.TemplateResponse(request=request, name="detection.html", context={
        "release":manifest(), "model_configured":bool(os.getenv("SHIELD_MODEL_DIR"))})
