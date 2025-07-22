from flask_sqlalchemy import SQLAlchemy
from dataclasses import dataclass, field

db = SQLAlchemy()

# Association table between Ingredients and Barcodes
ingredient_barcodes = db.Table(
    'ingredient_barcodes',
    db.Column('ingredient_id', db.Integer, db.ForeignKey('ingredients.id', ondelete="CASCADE"), primary_key=True),
    db.Column('barcode_id', db.Integer, db.ForeignKey('barcodes.id', ondelete="CASCADE"), primary_key=True),
    db.Column('unit', db.String(20), nullable=True)
)

@dataclass
class Recipes(db.Model):
    __tablename__ = "recipes"

    id: int = field(init=False)
    name: str
    file_path: str
    tags: str

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    file_path = db.Column(db.String(120), nullable=False)
    tags = db.Column(db.String(200))  # Comma-separated tags

@dataclass
class Ingredients(db.Model):
    __tablename__ = "ingredients"

    id: int = field(init=False)
    name: str

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)

    barcodes = db.relationship(
        "Barcodes",
        secondary=ingredient_barcodes,
        back_populates="ingredients"
    )

@dataclass
class Barcodes(db.Model):
    __tablename__ = "barcodes"

    id: int = field(init=False)
    barcode: str
    size: float
    unit: str

    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(50), nullable=False, unique=True)
    size = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)

    ingredients = db.relationship(
        "Ingredients",
        secondary=ingredient_barcodes,
        back_populates="barcodes"
    )

@dataclass
class RecipesIngredients(db.Model):
    __tablename__ = "recipe_ingredients"

    id: int = field(init=False)
    recipe_id: int
    ingredient_id: int
    size: float
    unit: str

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    size = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)

@dataclass
class Receipt(db.Model):
    __tablename__ = "receipts"

    id: int = field(init=False)
    store: str
    date: str
    time: str
    number: str
    discount: float
    total: float
    card: str

    id = db.Column(db.Integer, primary_key=True)
    store = db.Column(db.String(80), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    number = db.Column(db.String(20), nullable=False)
    discount = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    card = db.Column(db.String(20), nullable=False)

    items = db.relationship("StoreItem", back_populates="receipt", cascade="all, delete-orphan")

@dataclass
class StoreItem(db.Model):
    __tablename__ = "store_items"

    id: int = field(init=False)
    name: str
    barcode: str
    price: float
    quantity: float
    unit: str
    total: float
    discount_name: str = None
    discount_value: float = 0.0

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    barcode = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    total = db.Column(db.Float, nullable=False)
    discount_name = db.Column(db.String(50))
    discount_value = db.Column(db.Float, default=0.0)

    receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    receipt = db.relationship("Receipt", back_populates="items")

