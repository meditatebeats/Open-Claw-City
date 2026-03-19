from decimal import Decimal

from sqlalchemy import select

from .db import session_scope
from .models import Listing, ListingStatus, Parcel

SEED_DISTRICTS = {
    "Civic-Core": ["C-100", "C-101", "C-102", "C-103", "C-104"],
    "Innovation-Quay": ["I-200", "I-201", "I-202", "I-203", "I-204"],
    "Academy-Hills": ["A-300", "A-301", "A-302", "A-303", "A-304"],
}


def seed() -> tuple[int, int]:
    created_parcels = 0
    created_listings = 0
    with session_scope() as session:
        for district, lots in SEED_DISTRICTS.items():
            for lot in lots:
                exists = session.scalar(select(Parcel).where(Parcel.district == district, Parcel.lot_number == lot))
                if exists:
                    parcel = exists
                else:
                    parcel = Parcel(
                        district=district,
                        lot_number=lot,
                        zoning="mixed",
                        area_sq_m=800,
                        base_price=Decimal("25000.00"),
                    )
                    session.add(parcel)
                    session.flush()
                    created_parcels += 1

                open_listing = session.scalar(
                    select(Listing).where(Listing.parcel_id == parcel.id, Listing.status == ListingStatus.open)
                )
                if open_listing:
                    continue
                session.add(
                    Listing(
                        parcel_id=parcel.id,
                        seller_agent_id=None,
                        asking_price=parcel.base_price,
                        status=ListingStatus.open,
                    )
                )
                created_listings += 1

    return created_parcels, created_listings


if __name__ == "__main__":
    parcels, listings = seed()
    print(f"Seed complete. Added {parcels} parcels and {listings} listings.")
