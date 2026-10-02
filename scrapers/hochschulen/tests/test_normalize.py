from registry.normalize import parse_postal_city, domain_key, university_name_key

def test_postal_city():
    assert parse_postal_city("52062 Aachen") == ("52062", "Aachen")

def test_domain():
    assert domain_key("https://www.rwth-aachen.de/") == "rwth-aachen.de"

def test_name_key():
    assert "rwth" in university_name_key("RWTH Aachen University")
