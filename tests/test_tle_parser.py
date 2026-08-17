"""
Tests for TLE parser and validator.
"""

import pytest
from app.core.tle_parser import (
    parse_tle,
    validate_tle,
    validate_tle_line,
    extract_norad_id,
    _compute_checksum,
    ParsedTLE,
)
from app.core.exceptions import TLEValidationError
from tests.conftest import SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2


class TestTLEChecksum:
    def test_valid_checksum_line1(self):
        """Checksum should match the last digit of the line."""
        expected = int(SAMPLE_TLE_1_LINE1[-1])
        assert _compute_checksum(SAMPLE_TLE_1_LINE1) == expected

    def test_valid_checksum_line2(self):
        expected = int(SAMPLE_TLE_1_LINE2[-1])
        assert _compute_checksum(SAMPLE_TLE_1_LINE2) == expected


class TestTLEValidation:
    def test_valid_tle(self):
        """Valid TLE should not raise."""
        validate_tle(SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2)

    def test_empty_line1(self):
        with pytest.raises(TLEValidationError, match="empty"):
            validate_tle("", SAMPLE_TLE_1_LINE2)

    def test_empty_line2(self):
        with pytest.raises(TLEValidationError, match="empty"):
            validate_tle(SAMPLE_TLE_1_LINE1, "")

    def test_wrong_length(self):
        with pytest.raises(TLEValidationError, match="invalid length"):
            validate_tle("1 25544U 98067A   24001.5", SAMPLE_TLE_1_LINE2)

    def test_wrong_line_number(self):
        # line2 in place of line1
        with pytest.raises(TLEValidationError, match="line number"):
            validate_tle(SAMPLE_TLE_1_LINE2, SAMPLE_TLE_1_LINE2)

    def test_bad_checksum(self):
        # Corrupt last digit
        bad_line = SAMPLE_TLE_1_LINE1[:-1] + ("0" if SAMPLE_TLE_1_LINE1[-1] != "0" else "1")
        with pytest.raises(TLEValidationError, match="checksum"):
            validate_tle_line(bad_line, 1)


class TestTLEParsing:
    def test_parse_valid_tle(self):
        parsed = parse_tle(SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2, name="ISS")
        assert isinstance(parsed, ParsedTLE)
        assert parsed.norad_id == "25544"
        assert parsed.name == "ISS"
        assert 0 <= parsed.inclination <= 180
        assert 0 <= parsed.eccentricity < 1
        assert parsed.mean_motion > 0

    def test_extract_norad_id(self):
        assert extract_norad_id(SAMPLE_TLE_1_LINE1) == "25544"

    def test_parsed_orbital_ranges(self):
        parsed = parse_tle(SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2)
        assert 0 <= parsed.raan <= 360
        assert 0 <= parsed.arg_perigee <= 360
        assert 0 <= parsed.mean_anomaly <= 360
        assert parsed.eccentricity >= 0

    def test_epoch_year_conversion(self):
        parsed = parse_tle(SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2)
        assert parsed.epoch_year == 2024  # "24" -> 2024

    def test_parse_with_none_name(self):
        parsed = parse_tle(SAMPLE_TLE_1_LINE1, SAMPLE_TLE_1_LINE2)
        assert parsed.name is None
