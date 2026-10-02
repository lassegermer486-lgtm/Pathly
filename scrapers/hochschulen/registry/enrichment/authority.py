from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AuthorityEvidence:
    """
    Evidence about the legal/recognition status of an institution.

    This is deliberately separate from discovery:
    a university may have a campus in one state while its legal
    seat or recognition authority belongs to another state.
    """

    institution_state: Optional[str] = None
    recognition_state: Optional[str] = None
    legal_seat: Optional[str] = None

    authority: Optional[str] = None
    source_url: Optional[str] = None

    confidence: str = "unknown"


@dataclass
class EnrichmentResult:
    name: str
    classification: str

    institution_state: Optional[str] = None
    recognition_state: Optional[str] = None
    legal_seat: Optional[str] = None

    authority: Optional[str] = None
    source_url: Optional[str] = None

    confidence: str = "unknown"
    reason: Optional[str] = None


def classify_candidate(
    candidate: dict,
    target_state: str,
    evidence: AuthorityEvidence | None = None,
) -> EnrichmentResult:
    """
    Classify a discovered university candidate relative to a
    target federal state.

    Possible classifications:

        institution
        external_institution
        campus_or_branch
        review
    """

    name = candidate.get("name") or ""

    # ---------------------------------------------------------
    # Explicit discovery-level campus evidence
    # ---------------------------------------------------------

    signals = set(
        candidate.get("signals") or []
    )

    if "explicit_hamburg_campus" in signals:
        return EnrichmentResult(
            name=name,
            classification="campus_or_branch",
            confidence="high",
            reason="explicit_campus_signal",
        )

    # ---------------------------------------------------------
    # No authority evidence yet
    # ---------------------------------------------------------

    if evidence is None:
        return EnrichmentResult(
            name=name,
            classification="review",
            confidence="unknown",
            reason="missing_authority_evidence",
        )

    # ---------------------------------------------------------
    # Determine authoritative home state
    # ---------------------------------------------------------

    home_state = (
        evidence.institution_state
        or evidence.recognition_state
    )

    if not home_state:
        return EnrichmentResult(
            name=name,
            classification="review",
            legal_seat=evidence.legal_seat,
            authority=evidence.authority,
            source_url=evidence.source_url,
            confidence=evidence.confidence,
            reason="authority_state_unknown",
        )

    # ---------------------------------------------------------
    # Institution belongs to target state
    # ---------------------------------------------------------

    if home_state == target_state:
        return EnrichmentResult(
            name=name,
            classification="institution",
            institution_state=evidence.institution_state,
            recognition_state=evidence.recognition_state,
            legal_seat=evidence.legal_seat,
            authority=evidence.authority,
            source_url=evidence.source_url,
            confidence=evidence.confidence,
            reason="authority_confirms_target_state",
        )

    # ---------------------------------------------------------
    # Institution belongs to another state
    # ---------------------------------------------------------

    return EnrichmentResult(
        name=name,
        classification="external_institution",
        institution_state=evidence.institution_state,
        recognition_state=evidence.recognition_state,
        legal_seat=evidence.legal_seat,
        authority=evidence.authority,
        source_url=evidence.source_url,
        confidence=evidence.confidence,
        reason="authority_confirms_other_state",
    )
