"""Backup and restore ingredient barcodes and their links to ingredients."""

import json
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from models import db, Ingredients, Barcodes
from app import app

load_dotenv()
BACKUP_FILE = "ingredient_barcodes_backup.json"
BACKUP_DIR = "backups"
BACKUP_PATH = Path(BACKUP_DIR) / BACKUP_FILE


def backup_to_file(file_path=BACKUP_PATH):
    """Export all barcodes and their links to ingredients to a JSON file."""
    with app.app_context():
        session: Session = db.session
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


def restore_from_file(file_path=BACKUP_PATH):
    """Restore barcodes and their links from a JSON file."""
    with app.app_context():
        session: Session = db.session

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # --- Restore Barcodes ---
        restored_barcodes = 0
        for entry in data.get("barcodes", []):
            if not session.query(Barcodes).filter_by(barcode=entry["barcode"]).first():
                session.add(
                    Barcodes(
                        barcode=entry["barcode"], size=entry["size"], unit=entry["unit"]
                    )
                )
                restored_barcodes += 1

        session.commit()
        print(f"✅ Restored {restored_barcodes} new barcodes.")

        # --- Restore Links ---
        barcode_map = {b.barcode: b for b in session.query(Barcodes).all()}
        ingredient_map = {i.name: i for i in session.query(Ingredients).all()}

        restored_links = 0
        for link in data.get("ingredient_barcode_links", []):
            ingr = ingredient_map.get(link["ingredient_name"])
            code = barcode_map.get(link["barcode"])

            if not ingr or not code:
                print(f"⚠️ Missing: {link}")
                continue

            if code not in ingr.barcodes:
                ingr.barcodes.append(code)
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
