import uuid

from django.core.exceptions import DisallowedHost
from django.http import JsonResponse


class RequestMetadataMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        try:
            # Validate even safe requests; get_host is not otherwise guaranteed
            # to run when CommonMiddleware is deliberately absent.
            request.get_host()
        except DisallowedHost:
            response = JsonResponse({"error": {"code": "invalid_host", "message": "Use the local application address.", "request_id": request.request_id}}, status=400)
        else:
            response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        response["X-Frame-Options"] = "DENY"
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
        return response
