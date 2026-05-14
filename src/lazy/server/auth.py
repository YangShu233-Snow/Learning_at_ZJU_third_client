import uuid


def generate_token() -> str:
    return uuid.uuid4().hex
