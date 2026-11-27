from orchestrator.stub_mcp import find_symbol


def test_find_symbol_returns_fixed_answer() -> None:
    assert find_symbol("Target") == (
        "STUB: symbol 'Target' is defined in <stub>.py at line 1"
    )
