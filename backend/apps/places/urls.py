from django.urls import path

from .views import PlaceDetailView, PlaceNearbyView, PlacesNearView

# Note: `<str:pk>` (not `<uuid:pk>`) so that malformed UUIDs reach the views and
# return the standard JSON 404 error envelope instead of a framework HTML 404.
urlpatterns = [
    path("near/", PlacesNearView.as_view(), name="places_near"),
    path("<str:pk>/", PlaceDetailView.as_view(), name="places_detail"),
    path("<str:pk>/nearby/", PlaceNearbyView.as_view(), name="places_nearby"),
]
