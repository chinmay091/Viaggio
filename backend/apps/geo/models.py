from django.db import models

from apps.common.models import AuditModel


class WeatherData(models.Model):
    """
    High-volume weather time-series data, one row per H3 cell (resolution 7)
    per observation/forecast timestamp.

    P1-F2: schema-only in Phase 1 — populated from Open-Meteo by the City Pulse
    pipeline in Phase 3.

    Documented exception to the AuditModel/UUID rule: time-series ingestion
    writes millions of rows per city, so a plain BigAutoField primary key
    (dense, 8 bytes, index-friendly) is used instead of a 16-byte UUID.
    """

    id = models.BigAutoField(
        primary_key=True,
        help_text="Dense integer primary key (time-series volume; see model docstring)",
    )
    h3_index = models.CharField(
        max_length=16,
        help_text="H3 cell index at resolution 7 (coarser than Place's res8/9 — weather grid)",
    )
    timestamp = models.DateTimeField(
        help_text="Observation or forecast time (UTC) this row describes",
    )
    temperature_c = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Temperature in degrees Celsius",
    )
    precipitation_probability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Probability of precipitation, 0-100 (percent)",
    )
    precipitation_mm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Total precipitation in millimetres",
    )
    wind_speed_kmh = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Wind speed in kilometres per hour",
    )
    humidity_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Relative humidity, 0-100 (percent)",
    )
    weather_code = models.IntegerField(
        help_text="WMO weather interpretation code (0=clear, 1-3=partly cloudy, 45/48=fog, 51+=rain, 61+=drizzle/snow…)",
    )
    is_forecast = models.BooleanField(
        default=False,
        help_text="True if this row is a forecast, False if an observation",
    )
    source = models.CharField(
        max_length=50,
        default="open_meteo",
        help_text="Upstream weather provider identifier",
    )
    fetched_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the provider response was fetched and stored",
    )

    class Meta:
        db_table = "geo_weatherdata"
        indexes = [
            # Primary access pattern: "latest weather for cell X" (Phase 3)
            models.Index(
                fields=["h3_index", "timestamp"],
                name="idx_geoweather_h3_ts",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["h3_index", "timestamp", "source", "is_forecast"],
                name="uniq_geo_weather_h3_ts_src_fc",
            ),
        ]

    def __str__(self):
        kind = "forecast" if self.is_forecast else "observation"
        return f"WeatherData({self.h3_index}, {self.timestamp:%Y-%m-%d %H:%M}, {kind})"


class AreaContext(AuditModel):
    """
    Precomputed, LLM-enriched area intelligence for one H3 cell per time bucket.
    Consumed by City Pulse / Discovery to answer "what's happening here right
    now?" without recomputing activity + weather + LLM per request.

    P1-F2: schema-only in Phase 1 — produced by the Phase 3 pipeline.
    """

    h3_index = models.CharField(
        max_length=16,
        help_text="H3 cell index this context describes",
    )
    time_bucket = models.DateTimeField(
        help_text="Start of the time bucket this context was computed for (e.g. top of hour)",
    )
    activity_summary = models.JSONField(
        default=dict,
        blank=True,
        help_text="Aggregated activity metrics for the bucket (check-ins, saves, searches, …)",
    )
    top_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="Currently popular categories in this cell (ranked list of {category, score})",
    )
    top_places = models.JSONField(
        default=list,
        blank=True,
        help_text="Top places in this cell (ranked list of {place_id, name, score})",
    )
    weather_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot of the current/expected weather for the cell (from WeatherData)",
    )
    llm_summary = models.TextField(
        blank=True,
        help_text="LLM-generated natural-language description of the area for this bucket",
    )
    llm_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="LLM provider/model that produced llm_summary",
    )
    expires_at = models.DateTimeField(
        help_text="TTL — context is stale and must be regenerated after this time",
    )

    class Meta:
        db_table = "geo_areacontext"
        constraints = [
            models.UniqueConstraint(
                fields=["h3_index", "time_bucket"],
                name="uniq_geoacontext_h3_bucket",
            ),
        ]

    def __str__(self):
        return f"AreaContext({self.h3_index}, {self.time_bucket:%Y-%m-%d %H:%M})"


class AirQualityData(models.Model):
    """
    High-volume air-quality time-series data, one row per H3 cell (resolution 7)
    per hourly timestamp. Sourced from the Open-Meteo Air Quality API (keyless).

    Same documented exception to the AuditModel/UUID rule as WeatherData:
    plain BigAutoField primary key for dense, index-friendly writes.
    """

    id = models.BigAutoField(
        primary_key=True,
        help_text="Dense integer primary key (time-series volume; see model docstring)",
    )
    h3_index = models.CharField(
        max_length=16,
        help_text="H3 cell index at resolution 7 (weather/AQ grid)",
    )
    timestamp = models.DateTimeField(
        help_text="Observation or forecast time (UTC) this row describes",
    )
    us_aqi = models.IntegerField(
        null=True,
        blank=True,
        help_text="US Air Quality Index (0-500; null when the cell is outside coverage)",
    )
    pm2_5 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Fine particulate matter ≤2.5µm, µg/m³",
    )
    pm10 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Particulate matter ≤10µm, µg/m³",
    )
    ozone = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Ground-level ozone O3, µg/m³",
    )
    nitrogen_dioxide = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Nitrogen dioxide NO2, µg/m³",
    )
    carbon_monoxide = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Carbon monoxide CO, mg/m³",
    )
    source = models.CharField(
        max_length=50,
        default="open_meteo_aq",
        help_text="Upstream air-quality provider identifier",
    )
    fetched_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the provider response was fetched and stored",
    )

    class Meta:
        db_table = "geo_airqualitydata"
        indexes = [
            models.Index(
                fields=["h3_index", "timestamp"],
                name="idx_geoaq_h3_ts",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["h3_index", "timestamp", "source"],
                name="uniq_geo_aq_h3_ts_src",
            ),
        ]

    def __str__(self):
        return f"AirQualityData({self.h3_index}, {self.timestamp:%Y-%m-%d %H:%M}, AQI={self.us_aqi})"
