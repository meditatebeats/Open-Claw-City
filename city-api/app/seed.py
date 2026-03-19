from decimal import Decimal

from sqlalchemy import select

from .db import session_scope
from .models import Parcel

SEED_DISTRICTS = {
    "Civic-Core": ["C-100", "C-101", "C-102", "C-103", "C-104"],
    "Innovation-Quay": ["I-200", "I-201", "I-202", "I-203", "I-204"],
    "Academy-Hills": ["A-300", "A-301", "A-302", "A-303", "A-304"],
}


def seed() -> int:
    created = 0
    with session_scope() as session:
        for district, lots in SEED_DISTRICTS.items():
            for lot in lots:
                exists = session.scalar(select(Parcel).where(Parcel.district == district, Parcel.lot_number == lot))
                if exists:
                    continue
                parcel = Parcel(
                    district=district,
                    lot_number=lot,
                    zoning="mixed",
                    area_sq_m=800,
                    base_price=Decimal("25000.00"),
                )
                session.add(parcel)
                created += 1
    return created


if __name__ == "__main__":
    total = seed()
    print(f"Seed complete. Added {total} parcels.")
