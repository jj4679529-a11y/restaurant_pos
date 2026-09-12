class ServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def not_found(resource: str) -> ServiceError:
    return ServiceError(404, "not_found", f"{resource} not found")


def conflict(message: str) -> ServiceError:
    return ServiceError(409, "conflict", message)
