from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass
class Location:
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    street: Optional[str] = None
    location_type: str = "main"
    location_status: str = "confirmed"
    source_url: Optional[str] = None
    source_authority: Optional[str] = None

@dataclass
class SourceInfo:
    authority: str
    source_url: str
    retrieved_at: str
    source_category: Optional[str] = None

@dataclass
class University:
    name: str
    country: str = "DE"
    state: Optional[str] = None
    institution_type: str = "unknown"
    ownership: str = "unknown"
    recognition_status: str = "unknown"
    official_url: Optional[str] = None
    locations: list[Location] = field(default_factory=list)
    source: Optional[SourceInfo] = None

    def to_dict(self):
        return asdict(self)
