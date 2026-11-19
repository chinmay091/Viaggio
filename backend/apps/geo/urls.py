from django.urls import path

from .views import ReverseGeocodeView, WeatherForecastView, WeatherNowView

urlpatterns = [
    path("weather/now/", WeatherNowView.as_view(), name="geo-weather-now"),
    path("weather/forecast/", WeatherForecastView.as_view(), name="geo-weather-forecast"),
    path("reverse-geocode/", ReverseGeocodeView.as_view(), name="geo-reverse-geocode"),
]
