from profile_rules import normalize_display_name as gateway_subject


def test_gateway_contract() -> None:
    assert gateway_subject("  Ada Lovelace  ") == "ada lovelace"
