VALID_STATUSES = {429, 500, 502, 503}


def parse_simulate_header(value: str | None, enabled: bool) -> dict[str, int] | None:
    """Parse X-Simulate-Failure header into {key_id_or_wildcard: status_code}."""
    if not enabled or not value:
        return None

    out: dict[str, int] = {}
    for pair in value.split(","):
        if "=" not in pair:
            continue
        k, v = (p.strip() for p in pair.split("=", 1))
        if k and v.isdigit() and int(v) in VALID_STATUSES:
            out[k] = int(v)
    return out or None
