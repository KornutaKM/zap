def parse_operator_user_ids(raw: str | None) -> frozenset[int]:
    if not raw or not raw.strip():
        return frozenset()

    result: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            user_id = int(value)
        except ValueError as exc:
            raise ValueError(
                "OPERATOR_USER_IDS must contain only integer Telegram user IDs"
            ) from exc
        if user_id <= 0:
            raise ValueError("OPERATOR_USER_IDS must contain positive IDs")
        result.add(user_id)
    return frozenset(result)


def is_operator(user_id: int, operator_ids: frozenset[int]) -> bool:
    return user_id in operator_ids
