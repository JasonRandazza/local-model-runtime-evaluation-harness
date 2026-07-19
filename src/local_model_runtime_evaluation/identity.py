from __future__ import annotations

from dataclasses import dataclass

from .model_profiles import ModelProfile


class IdentityError(RuntimeError):
    code = "route_identity_failed"


@dataclass(frozen=True)
class RouteIdentityProof:
    profile_id: str
    runtime_owner: str
    direct_model_id: str
    routed_model_id: str
    same_omlx_model: bool


def prove_route_identity(
    profile: ModelProfile, direct_models: tuple[str, ...], routed_models: tuple[str, ...]
) -> RouteIdentityProof:
    if direct_models.count(profile.direct.model_id) != 1:
        raise IdentityError("approved direct model identity is missing or ambiguous")
    if routed_models.count(profile.routed.model_id) != 1:
        raise IdentityError("approved routed model identity is missing or ambiguous")
    if profile.runtime_owner != "omlx":
        raise IdentityError("Stage 1 runtime owner must be oMLX")
    return RouteIdentityProof(
        profile.profile_id, profile.runtime_owner, profile.direct.model_id,
        profile.routed.model_id, True,
    )
