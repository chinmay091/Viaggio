from django.urls import path

from .views import SavedPlaceDeleteView, SavedPlaceListCreateView

# Note: `<str:place_id>` (not `<uuid:place_id>`) so that malformed UUIDs reach
# the view and return the standard JSON 404 error envelope.
urlpatterns = [
    path("saved/", SavedPlaceListCreateView.as_view(), name="discovery-saved"),
    path("saved/<str:place_id>/", SavedPlaceDeleteView.as_view(), name="discovery-saved-detail"),
]
