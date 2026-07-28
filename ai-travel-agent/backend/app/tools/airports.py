"""City to airport (IATA) resolution for Indian travel.

The previous implementation fell back to the first three letters of the city
name, which silently produced wrong answers rather than errors:

    Jaisalmer -> JAI  (Jaipur, ~500 km away)
    Manali    -> MAN  (Manchester, UK)
    Darjeeling-> DAR  (Dar es Salaam, Tanzania)
    Udaipur   -> UDA  (not an airport at all)

A guess that resolves to a real airport in the wrong country is worse than no
answer, so unknown places now return None and the caller reports estimated
data instead of searching for a route nobody asked for.

Many popular destinations have no airport of their own; those map to the
airport travellers actually fly into, which is what a booking site would do.
"""

from typing import Optional

# Cities with their own airport.
AIRPORTS = {
    "delhi": "DEL", "new delhi": "DEL",
    "mumbai": "BOM", "bombay": "BOM",
    "bangalore": "BLR", "bengaluru": "BLR",
    "chennai": "MAA", "madras": "MAA",
    "kolkata": "CCU", "calcutta": "CCU",
    "hyderabad": "HYD",
    "goa": "GOI", "panaji": "GOI", "panjim": "GOI",
    "pune": "PNQ",
    "ahmedabad": "AMD",
    "jaipur": "JAI",
    "kochi": "COK", "cochin": "COK", "ernakulam": "COK",
    "lucknow": "LKO",
    "guwahati": "GAU",
    "thiruvananthapuram": "TRV", "trivandrum": "TRV",
    "srinagar": "SXR",
    "varanasi": "VNS", "benares": "VNS", "kashi": "VNS",
    "amritsar": "ATQ",
    "udaipur": "UDR",
    "jodhpur": "JDH",
    "jaisalmer": "JSA",
    "agra": "AGR",
    "chandigarh": "IXC",
    "bhopal": "BHO",
    "indore": "IDR",
    "patna": "PAT",
    "ranchi": "IXR",
    "raipur": "RPR",
    "nagpur": "NAG",
    "coimbatore": "CJB",
    "mangalore": "IXE", "mangaluru": "IXE",
    "madurai": "IXM",
    "visakhapatnam": "VTZ", "vizag": "VTZ", "vishakhapatnam": "VTZ",
    "bhubaneswar": "BBI",
    "imphal": "IMF",
    "port blair": "IXZ",
    "leh": "IXL",
    "bagdogra": "IXB",
    "dehradun": "DED",
    "dharamshala": "DHM", "dharamsala": "DHM",
    "jammu": "IXJ",
    "kullu": "KUU",
    "khajuraho": "HJR",
    "bhuj": "BHJ",
    "mysore": "MYQ", "mysuru": "MYQ",
    "puducherry": "PNY", "pondicherry": "PNY",
    "tirupati": "TIR",
    "vijayawada": "VGA",
    "aurangabad": "IXU",
    "surat": "STV",
    "vadodara": "BDQ", "baroda": "BDQ",
    "rajkot": "RAJ",
    "nashik": "ISK",
    "hubli": "HBX", "hubballi": "HBX",
    "kozhikode": "CCJ", "calicut": "CCJ",
    "kannur": "CNN",
    "tiruchirappalli": "TRZ", "trichy": "TRZ",
    "shillong": "SHL",
    "agartala": "IXA",
    "dibrugarh": "DIB",
    "silchar": "IXS",
    "aizawl": "AJL",
    "dimapur": "DMU",
    "gaya": "GAY", "bodhgaya": "GAY", "bodh gaya": "GAY",
    "prayagraj": "IXD", "allahabad": "IXD",
    "gorakhpur": "GOP",
    "bikaner": "BKB",
    "diu": "DIU",
    "belgaum": "IXG", "belagavi": "IXG",
}

# Places without an airport, mapped to the one travellers actually use.
NEAREST_AIRPORT = {
    "manali": "KUU", "kullu manali": "KUU", "solang": "KUU",
    "shimla": "IXC", "kasauli": "IXC", "kufri": "IXC",
    "mcleodganj": "DHM", "mcleod ganj": "DHM", "kangra": "DHM", "palampur": "DHM",
    "rishikesh": "DED", "haridwar": "DED", "mussoorie": "DED", "nainital": "DED",
    "auli": "DED", "kedarnath": "DED", "badrinath": "DED",
    "darjeeling": "IXB", "gangtok": "IXB", "kalimpong": "IXB", "sikkim": "IXB",
    "kashmir": "SXR", "gulmarg": "SXR", "pahalgam": "SXR", "sonmarg": "SXR",
    "ladakh": "IXL", "nubra": "IXL", "pangong": "IXL",
    "munnar": "COK", "alleppey": "COK", "alappuzha": "COK", "kumarakom": "COK",
    "thekkady": "COK", "wayanad": "CCJ", "kerala": "COK",
    "kovalam": "TRV", "varkala": "TRV", "kanyakumari": "TRV",
    "ooty": "CJB", "udhagamandalam": "CJB", "coonoor": "CJB", "kodaikanal": "CJB",
    "rameswaram": "IXM",
    "pushkar": "JAI", "ajmer": "JAI", "ranthambore": "JAI", "sawai madhopur": "JAI",
    "mount abu": "UDR", "kumbhalgarh": "UDR", "chittorgarh": "UDR",
    "rann of kutch": "BHJ", "kutch": "BHJ",
    "hampi": "HBX", "badami": "HBX",
    "coorg": "IXE", "madikeri": "IXE", "gokarna": "IXE", "udupi": "IXE",
    "lonavala": "PNQ", "mahabaleshwar": "PNQ", "khandala": "PNQ",
    "matheran": "BOM", "alibaug": "BOM", "shirdi": "ISK", "nashik wine": "ISK",
    "andaman": "IXZ", "havelock": "IXZ", "neil island": "IXZ",
    "rishabh": "DED",
    "sundarbans": "CCU", "digha": "CCU",
    "puri": "BBI", "konark": "BBI",
    "tawang": "IXB",
    "spiti": "KUU", "kaza": "KUU",
    "jim corbett": "DED", "corbett": "DED",
    "khajjiar": "DHM", "dalhousie": "DHM", "chamba": "DHM",
}


def resolve_airport(place: str) -> Optional[str]:
    """Return the IATA code for a place, or None if it cannot be resolved.

    Accepts a city name, a nearby-destination name, or an IATA code itself.
    Returns None rather than guessing — a wrong code books the wrong city.
    """
    if not place or not isinstance(place, str):
        return None

    cleaned = place.strip().lower()
    # Drop a trailing country/state qualifier: "Goa, India" -> "goa".
    if "," in cleaned:
        cleaned = cleaned.split(",")[0].strip()

    if cleaned in AIRPORTS:
        return AIRPORTS[cleaned]
    if cleaned in NEAREST_AIRPORT:
        return NEAREST_AIRPORT[cleaned]

    # Already an IATA code, e.g. "BOM" or "bom".
    if len(cleaned) == 3 and cleaned.isalpha():
        upper = cleaned.upper()
        if upper in set(AIRPORTS.values()) | set(NEAREST_AIRPORT.values()):
            return upper

    return None
