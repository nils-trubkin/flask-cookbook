import re
import os
from pathlib import Path
from dotenv import load_dotenv
import pymupdf
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "recipes.db")

load_dotenv()
RECEIPTS_DIR = os.getenv("RECEIPTS_DIR")

Base = declarative_base()


class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True)
    store = Column(String, nullable=False)
    date = Column(String, nullable=False)
    time = Column(String, nullable=False)
    number = Column(String, nullable=False)
    discount = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    card = Column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "store",
            "date",
            "time",
            "number",
            "discount",
            "total",
            "card",
            name="_receipt_uc",
        ),
    )

    items = relationship(
        "StoreItem", back_populates="receipt", cascade="all, delete-orphan"
    )


class StoreItem(Base):
    __tablename__ = "store_items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    barcode = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    total = Column(Float, nullable=False)
    discount_name = Column(String)
    discount_value = Column(Float)
    receipt_id = Column(
        Integer, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )

    receipt = relationship("Receipt", back_populates="items")


# Set up DB
engine = create_engine(f"sqlite:///{DATABASE_PATH}")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def extract_metadata(text):
    store = re.search(r"Kvitto\n(.+?)\n", text)
    date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    time = re.search(r"\b(\d{2}:\d{2})\b", text)
    number = re.search(r"Kvitto ?nr\s*\n?(\d+)", text, re.IGNORECASE)
    discount = re.search(r"Erhållen rabatt\s*\n?-([\d,]+)", text)
    paid = re.search(r"Betalat\s+([\d,]+)", text)
    card = re.search(r"\*{4,}(\d{4})", text)

    # Use comma as decimal separator, convert to float
    def parse_amount(match):
        return float(match.group(1).replace(",", ".")) if match else 0.0

    if not all([store, date, time, number, paid]):
        return None

    return {
        "store": store.group(1).strip(),
        "date": date.group(1),
        "time": time.group(1),
        "number": number.group(1),
        "discount": parse_amount(discount),
        "total": parse_amount(paid),
        "card": card.group(1).strip() if card else None,
    }


def extract_items(text):
    pattern = re.compile(
        r"(?P<discount>\*?)(?P<name>.*?)\s+(?P<barcode>\d{13})\s+(?P<price>[\d.]+)\s+(?P<quantity>[\d.]+)\s+(?P<unit>\S+)\s+(?P<total>[\d.]+)(?:\n|Total)(?:(?P<discount_name>.*?)\s+- (?P<discount_total>[\d.]+))?",
        re.MULTILINE,
    )
    items = []
    for match in pattern.finditer(text):
        g = match.groupdict()
        items.append(
            {
                "name": g["name"].strip(),
                "barcode": g["barcode"],
                "price": float(g["price"]),
                "quantity": float(g["quantity"]),
                "unit": g["unit"],
                "total": float(g["total"]),
                "discount_name": (
                    g["discount_name"].strip() if g["discount_name"] else None
                ),
                "discount_value": (
                    float(g["discount_total"]) if g["discount_total"] else None
                ),
            }
        )
    return items


def process_receipts(pdf_dir: str):
    session = Session()
    for pdf_path in Path(pdf_dir).glob("*.pdf"):
        print(f"📄 Processing: {pdf_path.name}")
        doc = pymupdf.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)

        metadata = extract_metadata(text)
        if not metadata:
            print(f"⚠️ Skipping {pdf_path.name}, no metadata")
            continue

        existing = (
            session.query(Receipt)
            .filter_by(
                store=metadata["store"],
                date=metadata["date"],
                time=metadata["time"],
                number=metadata["number"],
            )
            .first()
        )
        if existing:
            print(f"⏭ Already exists: {pdf_path.name}")
            continue

        receipt = Receipt(**metadata)
        items = extract_items(text)
        for item_data in items:
            receipt.items.append(StoreItem(**item_data))

        session.add(receipt)
        session.commit()
        print(f"✅ Saved receipt with {len(items)} items")

    session.close()


if __name__ == "__main__":
    process_receipts(RECEIPTS_DIR)
