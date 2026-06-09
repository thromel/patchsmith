def format_cents(cents: int) -> str:
    dollars = cents // 100
    remainder = cents % 100
    return f"${dollars}.{remainder}"

