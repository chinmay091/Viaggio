from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

api_v1_patterns = [
    path("health/", include("apps.common.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("places/", include("apps.places.urls")),
    path("discovery/", include("apps.discovery.urls")),
    path("activity/", include("apps.activity.urls")),
    path("recommendations/", include("apps.recommendations.urls")),
    path("bookings/", include("apps.bookings.urls")),
    path("restaurants/", include("apps.restaurants.urls")),
    path("hotels/", include("apps.hotels.urls")),
    path("trips/", include("apps.trips.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "api-v1"))),
    # OpenAPI 3 Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
