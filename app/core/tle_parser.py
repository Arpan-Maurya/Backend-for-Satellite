"""
TLE (Two-Line Element) parser and validator.

Validates TLE format, checksums, and extracts satellite identifiers.
Does NOT fabricate TLE data.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.core.exceptions import TLEValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedTLE:
    """Structured TLE data extracted from two-line element set."""

    norad_id: str
    name: Optional[str]
    line1: str
    line2: str
    # Line 1 fields
    classification: str
    intl_designator: str
    epoch_year: int
    epoch_day: float
    # Line 2 fields
    inclination: float        # degrees
    raan: float               # degrees (Right Ascension of Ascending Node)
    eccentricity: float       # dimensionless
    arg_perigee: float        # degrees
    mean_anomaly: float       # degrees
    mean_motion: float        # revs/day
    rev_number: int


def _compute_checksum(line: str) -> int:
    """
    Compute TLE checksum (mod-10) for a line.
    Digits count as their value, '-' counts as 1, all else as 0.
    The last character (the checksum digit) is excluded from computation.
    """
    total = 0
    for ch in line[:-1]:
        if ch.isdigit():
            total += int(ch)
        elif ch == '-':
            total += 1
    return total % 10


def validate_tle_line(line: str, expected_line_number: int) -> None:
    """
    Validate a single TLE line.

    Checks:
    - Non-empty
    - Length is 69 characters
    - Starts with expected line number
    - Checksum matches
    """
    if not line or not line.strip():
        raise TLEValidationError(f"TLE line {expected_line_number} is empty")

    line = line.strip()

    if len(line) != 69:
        raise TLEValidationError(
            f"TLE line {expected_line_number} has invalid length {len(line)} (expected 69)"
        )

    if line[0] != str(expected_line_number):
        raise TLEValidationError(
            f"TLE line does not start with expected line number {expected_line_number}"
        )

    # Validate checksum
    expected_checksum = int(line[-1])
    computed_checksum = _compute_checksum(line)
    if computed_checksum != expected_checksum:
        raise TLEValidationError(
            f"TLE line {expected_line_number} checksum mismatch: "
            f"computed {computed_checksum}, expected {expected_checksum}"
        )


def validate_tle(line1: str, line2: str) -> None:
    """Validate a complete TLE set (both lines)."""
    validate_tle_line(line1.strip(), 1)
    validate_tle_line(line2.strip(), 2)

    # Cross-validate NORAD IDs match between lines
    norad_1 = line1.strip()[2:7].strip()
    norad_2 = line2.strip()[2:7].strip()
    if norad_1 != norad_2:
        raise TLEValidationError(
            f"NORAD ID mismatch between lines: '{norad_1}' vs '{norad_2}'"
        )


def parse_tle(line1: str, line2: str, name: Optional[str] = None) -> ParsedTLE:
    """
    Parse and validate a Two-Line Element set into structured data.

    Args:
        line1: TLE line 1
        line2: TLE line 2
        name: Optional satellite name (line 0)

    Returns:
        ParsedTLE with all extracted orbital elements.

    Raises:
        TLEValidationError: If TLE format is invalid.
    """
    line1 = line1.strip()
    line2 = line2.strip()

    # Validate first
    validate_tle(line1, line2)

    try:
        # --- Line 1 parsing ---
        norad_id = line1[2:7].strip()
        classification = line1[7:8].strip()
        intl_designator = line1[9:17].strip()
        epoch_year_str = line1[18:20].strip()
        epoch_day_str = line1[20:32].strip()

        # Convert 2-digit year
        epoch_year_2d = int(epoch_year_str)
        epoch_year = 2000 + epoch_year_2d if epoch_year_2d < 57 else 1900 + epoch_year_2d
        epoch_day = float(epoch_day_str)

        # --- Line 2 parsing ---
        inclination = float(line2[8:16].strip())
        raan = float(line2[17:25].strip())

        # Eccentricity: implied leading decimal point
        ecc_str = line2[26:33].strip()
        eccentricity = float(f"0.{ecc_str}")

        arg_perigee = float(line2[34:42].strip())
        mean_anomaly = float(line2[43:51].strip())
        mean_motion = float(line2[52:63].strip())

        rev_str = line2[63:68].strip()
        rev_number = int(rev_str) if rev_str else 0

    except (ValueError, IndexError) as e:
        raise TLEValidationError(f"Failed to parse TLE fields: {e}")

    # Validate ranges
    if not (0.0 <= inclination <= 180.0):
        raise TLEValidationError(f"Inclination out of range: {inclination}")
    if not (0.0 <= raan <= 360.0):
        raise TLEValidationError(f"RAAN out of range: {raan}")
    if not (0.0 <= eccentricity < 1.0):
        raise TLEValidationError(f"Eccentricity out of range: {eccentricity}")
    if not (0.0 <= arg_perigee <= 360.0):
        raise TLEValidationError(f"Argument of perigee out of range: {arg_perigee}")
    if not (0.0 <= mean_anomaly <= 360.0):
        raise TLEValidationError(f"Mean anomaly out of range: {mean_anomaly}")
    if mean_motion <= 0:
        raise TLEValidationError(f"Mean motion must be positive: {mean_motion}")

    parsed = ParsedTLE(
        norad_id=norad_id,
        name=name,
        line1=line1,
        line2=line2,
        classification=classification,
        intl_designator=intl_designator,
        epoch_year=epoch_year,
        epoch_day=epoch_day,
        inclination=inclination,
        raan=raan,
        eccentricity=eccentricity,
        arg_perigee=arg_perigee,
        mean_anomaly=mean_anomaly,
        mean_motion=mean_motion,
        rev_number=rev_number,
    )

    logger.debug("Parsed TLE for NORAD %s: inc=%.2f, ecc=%.6f, mm=%.8f",
                 norad_id, inclination, eccentricity, mean_motion)

    return parsed


def extract_norad_id(line1: str) -> str:
    """Extract NORAD catalog ID from TLE line 1."""
    line1 = line1.strip()
    if len(line1) < 7:
        raise TLEValidationError("TLE line 1 too short to extract NORAD ID")
    return line1[2:7].strip()


def parse_tle_batch(tle_text: str):
    """
    Parse a batch of TLEs from 3-line format (name, line1, line2).

    Args:
        tle_text: Multi-line string with TLE sets in 3-line format.

    Yields:
        ParsedTLE for each valid TLE set. Logs and skips invalid entries.
    """
    lines = [l.strip() for l in tle_text.strip().splitlines() if l.strip()]

    i = 0
    while i < len(lines):
        # Detect format: if line starts with '1 ' it's a 2-line set, else 3-line
        if lines[i].startswith("1 ") and i + 1 < len(lines) and lines[i + 1].startswith("2 "):
            try:
                yield parse_tle(lines[i], lines[i + 1])
            except TLEValidationError as e:
                logger.warning("Skipping invalid TLE at line %d: %s", i, e)
            i += 2
        elif i + 2 < len(lines) and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            name = lines[i]
            try:
                yield parse_tle(lines[i + 1], lines[i + 2], name=name)
            except TLEValidationError as e:
                logger.warning("Skipping invalid TLE '%s' at line %d: %s", name, i, e)
            i += 3
        else:
            logger.warning("Skipping unrecognized line at position %d: %s", i, lines[i][:40])
            i += 1
