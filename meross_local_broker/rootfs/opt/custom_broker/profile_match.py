# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
"""Device-to-profile matching shared by the admin and tuning APIs."""
from __future__ import annotations

import json
from typing import Any, Dict, FrozenSet, List, Optional

import profile_engine
from profiles import ProfileCatalog


def profile_meta(catalog: ProfileCatalog,
                 profile_id: str) -> profile_engine.ProfileMeta:
    data = catalog.profiles[profile_id]
    return profile_engine.ProfileMeta(
        id=profile_id,
        version=data["profile"].get("version"),
        source=catalog.sources.get(profile_id, "bundled"),
        digest=catalog.profile_hashes()[profile_id],
        requires_engine=data["profile"].get("requires_engine"),
        data=data,
    )


def parse_abilities(row: Any) -> FrozenSet[str]:
    if row is None or not getattr(row, "ability_json", None):
        return frozenset()
    try:
        payload = json.loads(row.ability_json)
    except (TypeError, ValueError):
        return frozenset()
    if not isinstance(payload, dict):
        return frozenset()
    return frozenset(payload)


def match_devices(catalog: ProfileCatalog, devices: List[Any],
                  ability_getter) -> Dict[str, Optional[Dict[str, Any]]]:
    """Return one profile descriptor (or None) per device UUID."""
    metas = [profile_meta(catalog, profile_id)
             for profile_id in catalog.profiles]
    matches: Dict[str, Optional[Dict[str, Any]]] = {}
    for device in devices:
        context = profile_engine.MatchContext(
            type=device.device_type or "",
            sub_type=device.sub_type,
            mac=getattr(device, "mac", None),
            abilities=parse_abilities(ability_getter(device.uuid)),
            is_hub=bool(getattr(device, "child_subdevices", None))
            or (device.device_type or "").startswith("msh"),
        )
        result = profile_engine.match_candidates(metas, context)
        if result.profile is None:
            matches[device.uuid] = None
            continue
        profile_id = result.profile.id
        matches[device.uuid] = {
            "id": profile_id,
            "version": result.profile.version,
            "source": catalog.sources.get(profile_id, "bundled"),
            "hash": result.profile.digest,
            "requires_engine": result.profile.requires_engine,
        }
    return matches
