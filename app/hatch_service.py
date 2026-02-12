"""
Wrapper around hatch_rest_api to fetch and control Hatch Rest devices.
Uses Hatch cloud (email/password); all calls are async.
"""
from __future__ import annotations

import os
from typing import Any

import hatch_rest_api
from hatch_rest_api import AuthError, RateError


def get_credentials() -> tuple[str, str]:
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    if not email or not password:
        raise ValueError(
            "Set HATCH_EMAIL and HATCH_PASSWORD in .env or environment"
        )
    return email, password


async def get_devices() -> list[dict[str, Any]]:
    """Fetch all Hatch Rest devices for the configured account."""
    email, password = get_credentials()
    try:
        devices = await hatch_rest_api.get_rest_devices(email, password)
    except AuthError as e:
        raise ValueError(f"Hatch login failed (bad credentials): {e}") from e
    except RateError as e:
        raise ValueError(f"Hatch rate limit: {e}") from e

    out = []
    for d in devices:
        out.append(_device_to_dict(d))
    return out


def _device_to_dict(device: Any) -> dict[str, Any]:
    """Serialize a Rest device to a JSON-friendly dict."""
    base = {
        "name": getattr(device, "name", None) or getattr(device, "device_name", None) or "Unknown",
        "device_id": getattr(device, "device_id", None) or getattr(device, "thing_name", None),
        "model": type(device).__name__,
        "is_online": getattr(device, "is_online", None),
    }
    if hasattr(device, "volume"):
        base["volume"] = device.volume
    if hasattr(device, "is_playing"):
        base["is_playing"] = device.is_playing
    if hasattr(device, "audio_track"):
        base["audio_track"] = getattr(device.audio_track, "name", str(device.audio_track))
    return base


async def get_device_by_id(device_id: str) -> dict[str, Any] | None:
    """Return one device by device_id, or None if not found."""
    devices = await get_devices()
    for d in devices:
        if d.get("device_id") == device_id:
            return d
    return None


async def set_volume(device_id: str, volume: float) -> dict[str, Any] | None:
    """Set volume (0.0–1.0) for a device. Returns updated device state or None."""
    email, password = get_credentials()
    devices = await hatch_rest_api.get_rest_devices(email, password)
    for dev in devices:
        did = getattr(dev, "device_id", None) or getattr(dev, "thing_name", None)
        if did == device_id and hasattr(dev, "set_volume"):
            await dev.set_volume(volume)
            return _device_to_dict(dev)
    return None


def _resolve_audio_track(device: Any, track_name: str) -> Any | None:
    """Resolve track name (e.g. Ocean, Rain) to library enum for this device."""
    tracks = (
        getattr(device, "audio_tracks", None)
        or (hatch_rest_api.REST_MINI_AUDIO_TRACKS if isinstance(device, hatch_rest_api.RestMini) else hatch_rest_api.REST_PLUS_AUDIO_TRACKS)
    )
    name_lower = track_name.strip().lower()
    for t in tracks:
        if getattr(t, "name", str(t)).lower() == name_lower:
            return t
    return None


async def set_audio_track(device_id: str, track_name: str) -> dict[str, Any] | None:
    """Set audio track by name (e.g. Ocean, Rain). Returns updated device state or None."""
    email, password = get_credentials()
    devices = await hatch_rest_api.get_rest_devices(email, password)
    for dev in devices:
        did = getattr(dev, "device_id", None) or getattr(dev, "thing_name", None)
        if did != device_id or not hasattr(dev, "set_audio_track"):
            continue
        track = _resolve_audio_track(dev, track_name)
        if track is None:
            raise ValueError(f"Unknown audio track: {track_name!r}")
        await dev.set_audio_track(track)
        return _device_to_dict(dev)
    return None
