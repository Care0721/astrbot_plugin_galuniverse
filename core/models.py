"""Heroine and pilgrimage spot models. Stdlib only, easy to test standalone."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

# matches "古河渚 (CLANNAD)" / "古河渚（CLANNAD）" / "古河渚 - CLANNAD"
_WORK_PAREN = re.compile(r"^(?P<name>.+?)\s*[\(（](?P<work>[^()（）]+)[\)）]\s*$")
_WORK_DASH = re.compile(r"^(?P<name>.+?)\s+[-—–]\s+(?P<work>.+)$")

MAX_NAME_LEN = 60
MAX_WORK_LEN = 60
MAX_LINK_LEN = 500


def make_id(prefix: str, key: str) -> str:
    """Stable id derived from the content, so re-imports do not create dupes."""
    return prefix + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def split_name_work(raw: str) -> tuple[str, str]:
    """Split "古河渚 (CLANNAD)" into name and work."""
    text = raw.strip()
    for pattern in (_WORK_PAREN, _WORK_DASH):
        m = pattern.match(text)
        if m:
            return m.group("name").strip(), m.group("work").strip()
    return text, ""


@dataclass(slots=True)
class Heroine:
    name: str
    work: str = ""
    id: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = self.name.strip()[:MAX_NAME_LEN]
        self.work = self.work.strip()[:MAX_WORK_LEN]
        self.tags = [str(t).strip() for t in self.tags if str(t).strip()][:10]
        if not self.id:
            self.id = make_id("h_", f"{self.name}|{self.work}".lower())

    @property
    def display(self) -> str:
        return f"{self.name} ({self.work})" if self.work else self.name

    @property
    def label(self) -> str:
        """Compact form used on cards: 古河渚 · CLANNAD."""
        return f"{self.name} · {self.work}" if self.work else self.name

    @property
    def key(self) -> str:
        return f"{self.name}|{self.work}".lower()

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "work": self.work, "tags": self.tags}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Heroine":
        return cls(
            name=str(data.get("name", "")),
            work=str(data.get("work", "")),
            id=str(data.get("id", "")),
            tags=list(data.get("tags") or []),
        )


@dataclass(slots=True)
class Spot:
    work: str
    name: str
    id: str = ""
    region: str = ""
    link: str = ""
    lat: float | None = None
    lng: float | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.work = self.work.strip()[:MAX_WORK_LEN]
        self.name = self.name.strip()[:MAX_NAME_LEN]
        self.region = self.region.strip()[:MAX_NAME_LEN]
        self.link = self.link.strip()[:MAX_LINK_LEN]
        self.tags = [str(t).strip() for t in self.tags if str(t).strip()][:10]
        if not self.id:
            self.id = make_id("s_", f"{self.work}|{self.name}|{self.link}".lower())

    @property
    def key(self) -> str:
        return f"{self.work}|{self.name}|{self.link}".lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "work": self.work,
            "name": self.name,
            "region": self.region,
            "link": self.link,
            "lat": self.lat,
            "lng": self.lng,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Spot":
        lat, lng = data.get("lat"), data.get("lng")
        return cls(
            work=str(data.get("work", "")),
            name=str(data.get("name", "")),
            id=str(data.get("id", "")),
            region=str(data.get("region", "")),
            link=str(data.get("link", "")),
            lat=float(lat) if isinstance(lat, (int, float)) else None,
            lng=float(lng) if isinstance(lng, (int, float)) else None,
            tags=list(data.get("tags") or []),
        )
