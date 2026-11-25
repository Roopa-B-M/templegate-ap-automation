"""Thread-local request provider so audit signals can attribute changes
to the requesting user without passing request objects through layers."""
import threading

_state = threading.local()


def get_current_request():
    return getattr(_state, 'request', None)


def get_current_user():
    request = get_current_request()
    if request is None:
        return None
    user = getattr(request, 'user', None)
    return user if getattr(user, 'is_authenticated', False) else None


class RequestProviderMiddleware:
    """Stores the current HttpRequest in thread-local storage."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _state.request = request
        try:
            return self.get_response(request)
        finally:
            _state.request = None
