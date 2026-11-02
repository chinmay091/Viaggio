from django.urls import path

from .views import CheckInView, PlaceViewCreateView

urlpatterns = [
    path("check-in/", CheckInView.as_view(), name="activity-check-in"),
    path("view/", PlaceViewCreateView.as_view(), name="activity-view"),
]

