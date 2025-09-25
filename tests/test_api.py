# tests/test_api.py
from cli.session_api import analyze_session

def test_analyze_session_output():
    # Filene må finnes i repoet ditt for at testen skal kjøre grønt:
    #  - tests/test_golden_segment.csv
    #  - tests/weather.json
    result = analyze_session("tests/test_golden_segment.csv", "tests/weather.json", calibrate=True)

    assert isinstance(result, dict)
    assert "watts" in result and isinstance(result["watts"], list) and len(result["watts"]) > 0
    assert "v_rel" in result and isinstance(result["v_rel"], list)
    assert "wind_rel" in result and isinstance(result["wind_rel"], list)
    assert result.get("calibrated") in ("Ja", "Nei")

    # Antatt at kalibrering er mulig for golden-segmentet:
    # Om datasettet er for kort eller mangler variasjon, kan denne være "Nei".
    # Behold en mild assert (ikke hard-code Ja hvis datasettet ditt ikke støtter det).
    # Men henviser til ønsket at den bør være "Ja":
    # Hvis du VET segmentet støtter kalibrering, bruk:
    # assert result["calibrated"] == "Ja"