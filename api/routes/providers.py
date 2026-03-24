"""
api/routes/providers.py — Provider profile CRUD.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.provider_manager import (
    create_provider,
    delete_provider,
    list_providers,
    load_provider,
    save_provider,
)
from orchestrator.state import ProviderProfile

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderUpdateRequest(BaseModel):
    name: str | None = None
    specialty: str | None = None
    custom_vocabulary: list[str] | None = None
    mt_review_required: bool | None = None


class ProviderCreateRequest(BaseModel):
    provider_id: str
    name: str = ""
    specialty: str = "general"


@router.get("")
def list_providers_route():
    return [p.model_dump(mode="json") for p in list_providers()]


@router.get("/{provider_id}")
def get_provider(provider_id: str):
    p = load_provider(provider_id)
    if p is None:
        raise HTTPException(404, f"Provider '{provider_id}' not found")
    return p.model_dump(mode="json")


@router.post("", status_code=201)
def create_provider_route(req: ProviderCreateRequest):
    existing = load_provider(req.provider_id)
    if existing:
        raise HTTPException(409, f"Provider '{req.provider_id}' already exists")
    profile = create_provider(req.provider_id, req.name, req.specialty)
    return profile.model_dump(mode="json")


@router.put("/{provider_id}")
def update_provider(provider_id: str, req: ProviderUpdateRequest):
    existing = load_provider(provider_id)
    if existing is None:
        raise HTTPException(404, f"Provider '{provider_id}' not found")
    updates = req.model_dump(exclude_none=True)
    updated_data = existing.model_dump(mode="json")
    updated_data.update(updates)
    updated_profile = ProviderProfile(**updated_data)
    save_provider(updated_profile)
    return updated_profile.model_dump(mode="json")


@router.delete("/{provider_id}", status_code=204)
def delete_provider_route(provider_id: str):
    existing = load_provider(provider_id)
    if existing is None:
        raise HTTPException(404, f"Provider '{provider_id}' not found")
    delete_provider(provider_id)
