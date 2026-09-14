"""Airports and FBOs (shared reference catalog)."""

from __future__ import annotations

import math
import uuid
from typing import Optional

from sqlalchemy import func, or_

from app.models import FBO, Airport

from .base import SharedCatalogRepository

__all__ = ["AirportRepository", "FBORepository", "haversine_nm"]


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles -- the authoritative distance (DATA_MODEL 1.6)."""
    r = 3440.065
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class AirportRepository(SharedCatalogRepository[Airport]):
    model = Airport

    async def by_code(self, code: str) -> Optional[Airport]:
        """ICAO (KTEB) or IATA (TEB), case-insensitive."""
        c = code.strip().upper()
        stmt = self._base_query().where(or_(Airport.icao_code == c, Airport.iata_code == c)).order_by(Airport.client_id.nulls_last())
        return (await self.session.execute(stmt)).scalars().first()

    async def nearby(self, lat: float, lon: float, radius_nm: float, limit: int = 20) -> list[tuple[Airport, float]]:
        """Airports within a radius, nearest first, with the distance in nm.

        Two stages, as DATA_MODEL 1.6 prescribes: a cheap planar bounding-box
        prefilter in SQL on the lat/lon columns, then exact haversine in Python
        for the ranking and the cutoff. Nothing planar is ever returned.
        """
        dlat = radius_nm / 60.0
        dlon = radius_nm / (60.0 * max(math.cos(math.radians(lat)), 0.01))
        stmt = self._base_query().where(
            Airport.is_active.is_(True),
            Airport.latitude.between(lat - dlat, lat + dlat),
            Airport.longitude.between(lon - dlon, lon + dlon),
        )
        candidates = (await self.session.execute(stmt)).scalars().all()
        ranked = sorted(
            ((a, haversine_nm(lat, lon, float(a.latitude), float(a.longitude))) for a in candidates),
            key=lambda t: t[1],
        )
        return [(a, d) for a, d in ranked if d <= radius_nm][:limit]

    async def search(self, term: str, limit: int = 10) -> list[Airport]:
        stmt = (
            self._base_query()
            .where(Airport.search_tsv.op("@@")(func.plainto_tsquery("english", term)))
            .order_by(Airport.name)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class FBORepository(SharedCatalogRepository[FBO]):
    model = FBO

    async def at_airport(self, airport_id: uuid.UUID) -> list[FBO]:
        return await self.list(airport_id=airport_id, order_by=(FBO.is_preferred.desc(), FBO.name))
