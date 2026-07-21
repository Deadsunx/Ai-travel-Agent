"""Tests for city-to-airport resolution.

These guard against the class of bug this module replaced: a fallback that
took the first three letters of a city name and produced a real airport in
the wrong city — or the wrong country — instead of failing.
"""

from app.tools.airports import resolve_airport


def test_major_cities():
    assert resolve_airport("Mumbai") == "BOM"
    assert resolve_airport("delhi") == "DEL"
    assert resolve_airport("Goa") == "GOI"


def test_aliases_and_old_names():
    assert resolve_airport("Bombay") == "BOM"
    assert resolve_airport("Calcutta") == "CCU"
    assert resolve_airport("Bengaluru") == "BLR"


def test_the_wrong_city_regressions():
    # Each of these previously resolved to a real but wrong airport.
    assert resolve_airport("Jaisalmer") == "JSA"      # was JAI (Jaipur)
    assert resolve_airport("Udaipur") == "UDR"        # was UDA (nothing)
    assert resolve_airport("Manali") == "KUU"         # was MAN (Manchester)
    assert resolve_airport("Darjeeling") == "IXB"     # was DAR (Dar es Salaam)
    assert resolve_airport("Kashmir") == "SXR"        # was KAS (nothing)

    # The two must not collide.
    assert resolve_airport("Jaisalmer") != resolve_airport("Jaipur")


def test_destinations_without_an_airport_use_the_nearest():
    assert resolve_airport("Munnar") == "COK"
    assert resolve_airport("Ooty") == "CJB"
    assert resolve_airport("Rishikesh") == "DED"
    assert resolve_airport("Pushkar") == "JAI"


def test_country_qualifier_is_stripped():
    assert resolve_airport("Goa, India") == "GOI"
    assert resolve_airport("Udaipur, Rajasthan") == "UDR"


def test_accepts_iata_codes_directly():
    assert resolve_airport("BOM") == "BOM"
    assert resolve_airport("del") == "DEL"


def test_unknown_places_return_none_rather_than_guessing():
    # The whole point: no answer beats a confidently wrong one.
    assert resolve_airport("Atlantis") is None
    assert resolve_airport("Springfield") is None
    assert resolve_airport("ZZZ") is None
    assert resolve_airport("") is None
    assert resolve_airport(None) is None
