from datetime import datetime


def ahora_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
