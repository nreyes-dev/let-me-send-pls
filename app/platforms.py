from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_ASSETS = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "assets"


@dataclass(frozen=True)
class PlatformTier:
    platform: str
    tier: str
    max_size_mb: int

    @property
    def display_name(self) -> str:
        return f"{self.tier} ({self.max_size_mb} MB)"


PLATFORM_TIERS: list[PlatformTier] = [
    PlatformTier("Discord", "Free", 10),
    PlatformTier("Discord", "Nitro Basic", 50),
    PlatformTier("Discord", "Nitro", 500),
    PlatformTier("Slack", "All plans", 1000),
    PlatformTier("WhatsApp", "Standard", 180),
]

PLATFORM_NAMES: list[str] = list(dict.fromkeys(p.platform for p in PLATFORM_TIERS))

PLATFORM_ICONS: dict[str, Path] = {
    "Discord": _ASSETS / "discord.svg",
    "Slack": _ASSETS / "slack.svg",
    "WhatsApp": _ASSETS / "whatsapp.svg",
}


def tiers_for_platform(name: str) -> list[PlatformTier]:
    return [p for p in PLATFORM_TIERS if p.platform == name]
