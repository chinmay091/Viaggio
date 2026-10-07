"""
Base provider abstractions for Viaggio ingestion framework (P2-F2).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

from django.utils import timezone

from apps.places.models import Place, PlaceSource


@dataclass(frozen=True)
class Region:
    bbox: tuple | None = None        # (west, south, east, north)
    city: str = ""                   # fallback city name
    fixture_path: str | None = None  # offline mode
    limit: int | None = None


@dataclass
class UpsertResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    fetch_errors: int = 0
    errors: list = field(default_factory=list)  # bounded to last 100 entries (P2-D5)


class PlaceProvider(ABC):
    PROVIDER: str = ""               # PlaceSource.* value
    BATCH_SIZE: int = 500
    UPDATE_FIELDS: list[str] = [
        "name", "normalized_name", "slug", "category", "subcategory",
        "description", "address", "city", "region", "country",
        "phone", "website", "opening_hours", "location",
        "h3_index_res8", "h3_index_res9", "is_active",
    ]

    @abstractmethod
    def fetch(
        self,
        region: Region,
        log: Callable = print,
        on_error: Optional[Callable[[dict], None]] = None,
    ) -> tuple[dict | list, int]:
        """
        Fetch features for a region. Returns (features, fetch_error_count).
        ``on_error``, when provided, receives one dict per isolated fetch failure:
        ``{"where": "<tile bbox or 'fixture'>", "error": "<message>"}`` so callers
        (e.g. the job task) can record them in the job's error_log.
        """
        pass

    @abstractmethod
    def apply(self, place: Place, feature: dict, city_fallback: str) -> None:
        """Map feature properties and geometry onto a Place instance."""
        pass

    def _record_error(
        self,
        result: UpsertResult,
        entry: dict,
        on_error: Optional[Callable[[dict], None]] = None,
    ) -> None:
        result.errors.append(entry)
        if len(result.errors) > 100:
            result.errors = result.errors[-100:]
        if on_error:
            on_error(entry)

    def upsert(
        self,
        region: Region,
        features: dict | list,
        log: Callable = print,
        progress_cb: Optional[Callable[[int, int, int], None]] = None,
        on_error: Optional[Callable[[dict], None]] = None,
    ) -> UpsertResult:
        """
        Provider-agnostic idempotent upsert keyed on
        PlaceSource(provider=self.PROVIDER, provider_id=feature_id):
        hit -> update UPDATE_FIELDS + last_synced_at; miss -> create Place + PlaceSource.
        Batched 500/bulk; enrichment fields never clobbered (P1 behavior).
        """
        now = timezone.now()
        result = UpsertResult()

        if isinstance(features, dict):
            feature_items = list(features.items())
        elif isinstance(features, list):
            feature_items = [
                (f.get("id") if isinstance(f, dict) else None, f)
                for f in features
            ]
        else:
            feature_items = []

        source_map = {
            source.provider_id: source
            for source in PlaceSource.objects.filter(provider=self.PROVIDER)
            .select_related("place")
        }

        created_places, created_sources = [], []
        updated_places, updated_sources = [], []
        local_slugs = set()
        batch_skipped = 0

        def reserve_slug(place: Place):
            if place.slug in local_slugs:
                base, counter = place.slug, 2
                while f"{base}-{counter}" in local_slugs:
                    counter += 1
                place.slug = f"{base}-{counter}"
            local_slugs.add(place.slug)

        def flush():
            nonlocal created_places, created_sources, updated_places, updated_sources, batch_skipped
            c_count = len(created_places)
            u_count = len(updated_places)
            s_count = batch_skipped

            if created_places:
                Place.objects.bulk_create(created_places, batch_size=self.BATCH_SIZE)
                PlaceSource.objects.bulk_create(created_sources, batch_size=self.BATCH_SIZE)
                created_places, created_sources = [], []

            if updated_places:
                Place.objects.bulk_update(updated_places, self.UPDATE_FIELDS, batch_size=self.BATCH_SIZE)
                PlaceSource.objects.bulk_update(
                    updated_sources, ["provider_data", "last_synced_at"], batch_size=self.BATCH_SIZE
                )
                updated_places, updated_sources = [], []

            if progress_cb and (c_count or u_count or s_count):
                progress_cb(c_count, u_count, s_count)
            batch_skipped = 0

        for fid, feature in feature_items:
            if region.limit is not None and result.created + result.updated >= region.limit:
                break

            if not isinstance(feature, dict) or not fid:
                result.skipped += 1
                batch_skipped += 1
                self._record_error(
                    result,
                    {"where": "upsert", "error": f"Missing or invalid feature ID: {fid}"},
                    on_error,
                )
                continue

            # Build a candidate Place to validate geometry and name
            candidate = Place()
            self.apply(candidate, feature, region.city)

            if not candidate.name or candidate.location is None:
                result.skipped += 1
                batch_skipped += 1
                self._record_error(
                    result,
                    {"where": "upsert", "error": f"Malformed feature geometry or name for id={fid}"},
                    on_error,
                )
                continue

            source = source_map.get(fid)
            if source is None or source.place is None:
                place = candidate
                place.fill_derived_fields()  # bulk_create bypasses save()
                reserve_slug(place)
                created_places.append(place)
                created_sources.append(
                    PlaceSource(
                        place=place,
                        provider=self.PROVIDER,
                        provider_id=fid,
                        provider_data=feature,
                        confidence=1.00,
                        last_synced_at=now,
                    )
                )
                result.created += 1
            else:
                place = source.place
                self.apply(place, feature, region.city)
                place.fill_derived_fields()  # keep h3 cells in sync on location change
                updated_places.append(place)
                source.provider_data = feature
                source.last_synced_at = now
                updated_sources.append(source)
                result.updated += 1

            if len(created_places) >= self.BATCH_SIZE or len(updated_places) >= self.BATCH_SIZE:
                flush()

        flush()
        log(f"fetched:  {len(feature_items)}")
        log(f"created:  {result.created}")
        log(f"updated:  {result.updated}")
        log(f"skipped:  {result.skipped}")
        return result
