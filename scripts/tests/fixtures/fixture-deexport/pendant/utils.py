def format_name(name: str) -> str:
    return name.strip().title()


def parse_address(raw: str) -> tuple[str, int]:
    host, port = raw.rsplit(":", 1)
    return host, int(port)
