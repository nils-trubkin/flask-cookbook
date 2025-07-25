"""Backup and restore ingredient barcodes and their links to ingredients."""

import json
from sqlalchemy.orm import Session
from models import db, Ingredients, Barcodes

BACKUP_FILE = "ingredient_barcodes_backup.json"
session: Session = db.session


def backup_to_file(file_path=BACKUP_FILE):
    """Export all barcodes and their links to ingredients to a JSON file."""
    # Export all barcodes
    barcodes = session.query(Barcodes).all()
    barcode_data = [
        {"barcode": b.barcode, "size": b.size, "unit": b.unit} for b in barcodes
    ]

    # Export all links: ingredient name ↔ barcode string
    link_data = []
    for barcode in barcodes:
        for ingredient in barcode.ingredients:
            link_data.append(
                {"ingredient_name": ingredient.name, "barcode": barcode.barcode}
            )

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(
            {"barcodes": barcode_data, "ingredient_barcode_links": link_data},
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"✅ Backup complete: {len(barcode_data)} barcodes, {len(link_data)} links → {file_path}"
    )


def restore_from_file(file_path=BACKUP_FILE):
    """Restore barcodes and their links from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    barcodes = data.get("barcodes", [])
    links = data.get("ingredient_barcode_links", [])

    # Restore barcodes if missing
    restored_barcodes = 0
    for b in barcodes:
        exists = session.query(Barcodes).filter_by(barcode=b["barcode"]).first()
        if not exists:
            new_b = Barcodes(barcode=b["barcode"], size=b["size"], unit=b["unit"])
            session.add(new_b)
            restored_barcodes += 1
    session.commit()
    print(f"✅ Restored {restored_barcodes} new barcodes.")

    # Refresh maps
    barcode_map = {b.barcode: b for b in session.query(Barcodes).all()}
    ingredient_map = {i.name: i for i in session.query(Ingredients).all()}

    restored_links = 0
    for link in links:
        ingredient = ingredient_map.get(link["ingredient_name"])
        barcode = barcode_map.get(link["barcode"])
        if not ingredient or not barcode:
            print(f"⚠️ Missing: {link}")
            continue

        if barcode not in ingredient.barcodes:
            ingredient.barcodes.append(barcode)
            restored_links += 1

    session.commit()
    print(f"✅ Restored {restored_links} ingredient-barcode links.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backup and restore ingredient barcodes."
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a backup of all barcodes and links.",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore barcodes and links from backup file.",
    )

    args = parser.parse_args()

    if args.backup:
        backup_to_file()
    elif args.restore:
        restore_from_file()
    else:
        print("Please specify --backup or --restore.")
