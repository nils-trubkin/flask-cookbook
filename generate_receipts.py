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


def extract_metadata_old(text):
    store = re.search(r"Kvitto\n(.+?)\n", text)
    date = re.search(r"Datum:\n(\d{4}-\d{2}-\d{2})", text)
    time = re.search(r"Tid:\n(\d{2}:\d{2})", text)
    number = re.search(r"Kvittonr:\n(\d+)", text)
    discount = re.search(r"Erhållen rabatt:\n-([\d.]+)", text)
    total = re.search(r"Total:\n([\d.]+)", text)
    card = re.search(r"\*{12}(\d{4})", text)
    if not all([store, date, time, number, discount, total, card]):
        return None
    return {
        "store": store.group(1).strip(),
        "date": date.group(1),
        "time": time.group(1),
        "number": number.group(1),
        "discount": float(discount.group(1)),
        "total": float(total.group(1)),
        "card": card.group(1).strip(),
    }

def extract_metadata_ai(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    try:
        idx = lines.index("Datum")
        date = lines[idx + 6]
        time = lines[idx + 7]
        number = lines[idx + 9]
    except (ValueError, IndexError):
        return None  # Structure doesn't match expected format

    # Extract store name
    store_match = re.search(r"Kvitto\n(.+?)\n", text)
    store = store_match.group(1).strip() if store_match else None

    # Extract optional discount and paid total
    discount_match = re.search(r"Erhållen rabatt\s*\n?-([\d,]+)", text)
    paid_match = re.search(r"Betalat\s+([\d,]+)", text)
    card_match = re.search(r"\*{4,}(\d{4})", text)

    def parse_amount(match):
        return float(match.group(1).replace(",", ".")) if match else 0.0

    return {
        "store": store,
        "date": date,
        "time": time,
        "number": number,
        "discount": parse_amount(discount_match),
        "total": parse_amount(paid_match),
        "card": card_match.group(1) if card_match else None,
    }


def extract_items(text):
    pattern = re.compile(
        r"(?P<discount>\*?)(?P<name>.*?)\s+(?P<barcode>\d{13})\s+(?P<price>[\d,]+)\s+(?P<quantity>[\d,]+)\s+(?P<unit>\S+)\s+(?P<total>[\d,]+)(?:\n|Total)(?:(?P<discount_name>.*?)\s+-(?P<discount_total>[\d,]+))?",
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


def extract_items_old(text):
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

def extract_items(text):
    lines = text.splitlines()
    items = []
    i = 0

    while i < len(lines):
        name_line = lines[i].strip()
        if not name_line or name_line.startswith("Datum") or name_line.startswith("Betalat"):
            i += 1
            continue

        # Look ahead to check if the next few lines match expected format
        if (
            i + 3 < len(lines)
            and re.match(r"^\d{13}$", lines[i + 1].strip())
            and re.match(r"^[\d,]+\s*$", lines[i + 2].strip())
            and re.match(r"^[\d,]+\s+[a-zA-Z]+\s*$", lines[i + 3].strip())
        ):
            name = name_line.strip("*").strip()
            barcode = lines[i + 1].strip()
            price = float(lines[i + 2].replace(",", ".").strip())

            quantity_unit = lines[i + 3].strip().split()
            quantity = float(quantity_unit[0].replace(",", "."))
            unit = quantity_unit[1]

            total = price * quantity

            item = {
                "name": name,
                "barcode": barcode,
                "price": price,
                "quantity": quantity,
                "unit": unit,
                "total": round(total, 2),
                "discount_name": None,
                "discount_value": None,
            }

            # Check for discount line
            if (
                i + 4 < len(lines)
                and re.match(r"^-?\d{1,3},\d{2}$", lines[i + 4].strip())
                and not re.match(r"^\d{13}$", lines[i + 4].strip())  # avoid matching next barcode
            ):
                discount_total = float(lines[i + 4].replace(",", ".").strip())
                item["discount_value"] = abs(discount_total)
                item["discount_name"] = "Discount"

                i += 5
            else:
                i += 4

            items.append(item)
        else:
            i += 1

    return items

def process_receipts(pdf_dir: str):
    session = Session()
    for pdf_path in Path(pdf_dir).glob("*.pdf"):
        print(f"📄 Processing: {pdf_path.name}")
        doc = pymupdf.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)

        metadata = extract_metadata(text)
        if not all(metadata.values()):
            print(f"⚠️ Skipping {pdf_path.name}, metadata incomplete: {metadata}")
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
        if not items:
            print(f"⚠️ No items found in {pdf_path.name}")
            continue
        for item_data in items:
            receipt.items.append(StoreItem(**item_data))

        session.add(receipt)
        session.commit()
        print(f"✅ Saved receipt with {len(items)} items")

    session.close()


if __name__ == "__main__":
    process_receipts(RECEIPTS_DIR)
