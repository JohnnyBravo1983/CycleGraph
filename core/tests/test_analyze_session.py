import pytest
from cyclegraph_core import analyze_session

def test_analyze_session_empty_arrays():
    with pytest.raises(ValueError, match="Watt og puls må ha samme lengde.*puls-listen kan ikke være tom"):
        analyze_session([], [])