"""One error type for the whole /api/x API, so every error has the same JSON shape."""


class ApiError(Exception):
    """Raise this anywhere inside a route. The blueprint turns it into JSON."""

    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def to_dict(self):
        return {"error": {"code": self.code, "message": self.message}}


class HookError(ApiError):
    """Raise this inside a role module (replay, containment ...) to send a clean error to the client."""
