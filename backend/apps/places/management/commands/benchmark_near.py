"""
Benchmark GET /api/v1/places/near/ against synthetic data (P1-F6).

Placement
---------
``--n`` places (default 50 000; ``--fast`` = 5 000) are laid out on 200
concentric rings (50 m .. 10 km) around the Mumbai anchor (18.94 / 72.835).
The RNG is seeded with a fixed constant, so every run at a given ``--n`` is
byte-for-byte reproducible.

Measurement
-----------
200 ``near/`` queries (random centers within +/-5 km, radii 500 m..10 km) are
executed through the DRF test client with a real (throwaway) user, timed with
``time.perf_counter``. Reports p50 / p95 / max.

Target (soft): p95 < 150 ms at 100k places. This command *reports* against
the target but never fails the build — slower hardware is allowed to miss it.

Safety
------
Synthetic rows are tagged with the slug prefix ``bench-`` and are deleted
again at the end (pass ``--keep`` to inspect them). Run against the dev DB:

    docker compose exec backend python manage.py benchmark_near --fast
    docker compose exec backend python manage.py benchmark_near --n 100000
"""

import math
import random
import time

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from rest_framework.test import APIClient

from apps.places.models import Place

SEED = 42
CENTER_LAT = 18.9400
CENTER_LNG = 72.8350
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LNG = 111_320.0 * math.cos(math.radians(CENTER_LAT))

N_RINGS = 200
RING_SPAN_M = 10_000.0
BENCH_SLUG_PREFIX = "bench-"
CATEGORIES = ("cafe", "restaurant", "hotel", "attraction", "shopping")

QUERY_RADII_M = (500, 1000, 2500, 5000, 10_000)
P95_TARGET_MS = 150.0


def percentile(sorted_values, pct):
    """Linear-interpolated percentile of a pre-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lo = int(math.floor(rank))
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = rank - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


class Command(BaseCommand):
    help = (
        "Benchmark the near/ spatial endpoint against deterministic synthetic "
        "ring-placed data. Reports p50/p95/max (soft target: p95 < 150 ms @ 100k)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--n", type=int, default=50_000, help="Number of synthetic places (default 50000)")
        parser.add_argument("--fast", action="store_true", help="Smoke run with 5000 places")
        parser.add_argument("--queries", type=int, default=200, help="Number of timed near/ queries (default 200)")
        parser.add_argument("--keep", action="store_true", help="Do not delete the synthetic data afterwards")

    def handle(self, *args, **options):
        n = 5_000 if options["fast"] else options["n"]
        queries = options["queries"]

        self.stdout.write(f"benchmark_near: n={n:,} queries={queries} seed={SEED}")
        self.stdout.write("NOTE: runs against the DEV database; synthetic rows are cleaned up unless --keep.")

        self._seed_synthetic_data(n)
        counts = self._report_counts()

        timings_ms = self._run_queries(queries)
        self._report(timings_ms, n, counts)

        if not options["keep"]:
            deleted, _ = Place.objects.filter(slug__startswith=BENCH_SLUG_PREFIX).delete()
            self.stdout.write(f"Cleaned up {deleted:,} synthetic places.")

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _seed_synthetic_data(self, n):
        """Place n places on N_RINGS concentric rings, deterministically."""
        rng = random.Random(SEED)
        per_ring, _ = divmod(n, N_RINGS)
        objects = []

        def add_at(i, radius_m, theta):
            lat = CENTER_LAT + radius_m * math.cos(theta) / M_PER_DEG_LAT
            lng = CENTER_LNG + radius_m * math.sin(theta) / M_PER_DEG_LNG
            place = Place(
                name=f"Bench Place {i:07d}",
                slug=f"{BENCH_SLUG_PREFIX}{i:07d}",  # pre-set: skips per-row slug lookup
                category=CATEGORIES[i % len(CATEGORIES)],
                city="Mumbai",
                is_active=True,
                location=Point(lng, lat, srid=4326),
            )
            place.fill_derived_fields()  # bulk_create bypasses save(); derive manually
            objects.append(place)

        i = 0
        for ring in range(N_RINGS):
            radius_m = (ring + 1) * RING_SPAN_M / N_RINGS
            for _ in range(per_ring + (1 if ring == N_RINGS - 1 else 0)):
                add_at(i, radius_m, rng.uniform(0.0, 2.0 * math.pi))
                i += 1

        started = time.perf_counter()
        with transaction.atomic():
            Place.objects.bulk_create(objects, batch_size=500)
        self.stdout.write(
            f"Seeded {len(objects):,} places in {time.perf_counter() - started:.1f}s "
            f"(bulk_create batch=500, GiST index live)"
        )

    def _report_counts(self):
        total = Place.objects.count()
        bench = Place.objects.filter(slug__startswith=BENCH_SLUG_PREFIX).count()
        return total, bench

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------
    def _run_queries(self, count):
        """Run ``count`` near/ queries through the DRF test client; return ms timings."""
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            email=f"benchmark.{SEED}@example.com",
            username=f"bench_{SEED}",
            password="bench-password-not-used",
        )
        try:
            client = APIClient()
            client.force_authenticate(user=user)

            rng = random.Random(SEED)
            timings_ms = []
            for _ in range(count):
                lat = CENTER_LAT + rng.uniform(-0.045, 0.045)  # ~ +/-5 km
                lng = CENTER_LNG + rng.uniform(-0.045, 0.045)
                radius = rng.choice(QUERY_RADII_M)
                started = time.perf_counter()
                response = client.get(
                    "/api/v1/places/near/",
                    {"lat": f"{lat:.6f}", "lng": f"{lng:.6f}", "radius_m": radius},
                )
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                if response.status_code != 200:
                    raise RuntimeError(f"near/ returned {response.status_code}: {response.content[:200]!r}")
                timings_ms.append(elapsed_ms)
            return timings_ms
        finally:
            user.delete()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def _report(self, timings_ms, n, counts):
        total, bench = counts
        ordered = sorted(timings_ms)
        p50 = percentile(ordered, 50)
        p95 = percentile(ordered, 95)
        max_ms = ordered[-1]

        self.stdout.write(self.style.MIGRATE_HEADING("near/ benchmark results"))
        self.stdout.write(f"  places in DB:      {total:,} ({bench:,} synthetic)")
        self.stdout.write(f"  queries:           {len(ordered)}")
        self.stdout.write(f"  p50:               {p50:8.1f} ms")
        self.stdout.write(f"  p95:               {p95:8.1f} ms")
        self.stdout.write(f"  max:               {max_ms:8.1f} ms")

        target_met = p95 < P95_TARGET_MS
        verdict = "MET" if target_met else "NOT MET (soft target - not a failure)"
        self.stdout.write(f"  target p95 < {P95_TARGET_MS:.0f} ms @ 100k: {verdict}")
        if n < 100_000:
            self.stdout.write("  [note: this run had fewer than 100k places]")
