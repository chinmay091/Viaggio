"""
Provider registry for Viaggio ingestion framework (P2-F2).
"""

from apps.ingestion.providers.overture import OvertureProvider

PROVIDERS = {
    "OVERTURE": OvertureProvider,
}
