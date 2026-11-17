from django.urls import path

from drive import views

urlpatterns = [
    path("api/session", views.session),
    path("api/folders", views.folders),
    path("api/files", views.files),
    path("api/files/<uuid:file_id>", views.file_detail),
    path("api/files/<uuid:file_id>/content", views.download),
    path("api/uploads", views.uploads),
    path("api/uploads/active", views.active_upload),
    path("api/uploads/<uuid:upload_id>", views.upload_status),
    path("api/uploads/<uuid:upload_id>/content", views.upload_content),
    path("api/health", views.health),
    path("", views.frontend),
    path("assets/<path:asset>", views.frontend_asset),
]
handler404 = "drive.views.not_found"
handler500 = "drive.views.server_error"
handler400 = "drive.views.bad_request"
