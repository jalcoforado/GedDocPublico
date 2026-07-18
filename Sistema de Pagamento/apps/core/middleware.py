import threading

_local = threading.local()


class CurrentUserMiddleware:
    """
    Stashes the current request's user and IP in thread-local storage so
    that model signals (apps.auditoria) can attribute changes to a user
    and origin (RF26, RF59) without needing the request object threaded
    through every service function.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.user = getattr(request, 'user', None)
        _local.ip = _get_client_ip(request)
        try:
            response = self.get_response(request)
        finally:
            _local.user = None
            _local.ip = None
        return response


def _get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_current_user():
    user = getattr(_local, 'user', None)
    if user is not None and not getattr(user, 'is_authenticated', False):
        return None
    return user


def get_current_ip():
    return getattr(_local, 'ip', None)
