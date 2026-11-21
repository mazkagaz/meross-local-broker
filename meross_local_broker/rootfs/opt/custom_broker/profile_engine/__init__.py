"""Shared, Home-Assistant-free profile engine (vendored).

Source of truth: mazkagaz/meross-local-cloud, custom_components/meross_cloud/
profiles/. Do not edit these modules here: run tools/sync_profile_engine.py
from the broker repository and keep the pinned commit in UPSTREAM.md.
"""
from .compiler import (
    ProfileCompiler,
    compile_profile,
    expand_channel_entities,
)
from .constants import ENGINE_VERSION
from .match import MatchContext, MatchResult, match_candidates, match_profile
from .models import (
    CommandSpec,
    CompiledProfile,
    EntitySpec,
    FieldSpec,
    NamespaceSpec,
    PollingSpec,
    ProfileMeta,
    StateSpec,
    SubDeviceTemplate,
)
from .paths import MISSING, get_path, parse_path, substitute
from .registry import ProfileRegistry
from .runtime import DeviceRuntime, EntityState, SubDeviceRuntime

__all__ = [
    "ENGINE_VERSION",
    "CommandSpec",
    "CompiledProfile",
    "DeviceRuntime",
    "EntitySpec",
    "EntityState",
    "FieldSpec",
    "MISSING",
    "MatchContext",
    "MatchResult",
    "NamespaceSpec",
    "PollingSpec",
    "ProfileCompiler",
    "ProfileMeta",
    "ProfileRegistry",
    "StateSpec",
    "SubDeviceRuntime",
    "SubDeviceTemplate",
    "compile_profile",
    "expand_channel_entities",
    "get_path",
    "match_candidates",
    "match_profile",
    "parse_path",
    "substitute",
]
