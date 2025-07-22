""" Flask app for the cookbook """

import json
import os
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse
from dotenv import load_dotenv
from flask import Flask, render_template, request, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "recipes.db")

load_dotenv()
RECIPES_DIR = os.getenv("RECIPES_DIR")
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
os.environ["BROWSER"] = "chromium-browser"
os.environ["GIT_SSH"] = "/home/dietpi/gitssh.sh"
os.environ["DISPLAY"] = ":0.0"
db = SQLAlchemy(app)

# Association Table
ingredient_barcodes = db.Table(
    'ingredient_barcodes',
    db.Column('ingredient_id', db.Integer, db.ForeignKey('ingredients.id', ondelete="CASCADE"), primary_key=True),
    db.Column('barcode_id', db.Integer, db.ForeignKey('barcodes.id', ondelete="CASCADE"), primary_key=True),
    db.Column('unit', db.String(20), nullable=True)  # Optional unit for the ingredient
)

commands = []


@dataclass
class Recipes(db.Model):
    """Database model for recipes"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    file_path = db.Column(db.String(120), nullable=False)
    tags = db.Column(db.String(200))  # Comma-separated tags
    

@dataclass
class Ingredients(db.Model):
    """Database model for ingredients"""
    id: int
    name: str

    __tablename__ = "ingredients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)

    # Relationship to barcodes (many-to-many)
    barcodes = db.relationship(
        "Barcodes",
        secondary=ingredient_barcodes,
        back_populates="ingredients"
    )


@dataclass
class RecipesIngredients(db.Model):
    """Database model for recipe ingredients"""
    id: int
    recipe_id: int
    ingredient_id: int
    size: float
    unit: str

    __tablename__ = "recipe_ingredients"

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    size = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)


@dataclass
class Barcodes(db.Model):
    """Database model for barcodes"""
    id: int
    barcode: str
    size: float
    unit: str

    __tablename__ = "barcodes"

    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(50), nullable=False, unique=True)
    size = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)

    # Relationship to ingredients (many-to-many)
    ingredients = db.relationship(
        "Ingredients",
        secondary=ingredient_barcodes,
        back_populates="barcodes"
    )

@dataclass
class Receipt(db.Model):
    """Database model for receipts"""
    id: int
    store: str
    date: str
    time: str
    number: str
    discount: float
    total: float
    card: str

    __tablename__ = "receipts"

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
    """Database model for store items"""
    id: int
    name: str
    barcode: str
    price: float
    quantity: float
    unit: str
    total: float
    discount_name: str = None
    discount_value: float = 0.0

    __tablename__ = "store_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    barcode = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    total = db.Column(db.Float, nullable=False)
    discount_name = db.Column(db.String(50))
    discount_value = db.Column(db.Float, default=0.0)

    receipt_id = db.Column(
        db.Integer, db.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    
    receipt = db.relationship("Receipt", back_populates="items")


@dataclass
class Recipe:
    """Recipe dataclass"""

    name: str
    url: str
    image: str
    number: int


@app.route("/")
def home():
    """Display the home page"""
    recipe_files = []
    tags = []
    try:
        results = Recipes.query.all()
        recipe_files = [
            Recipe(
                " ".join(
                    [
                        word.capitalize()
                        for word in recipe.file_path.split(".")[0].split("_")
                    ]
                ),
                f"/recipes/{recipe.file_path.split('.')[0]}",
                (
                    f"images/{recipe.file_path.split('.')[0]}.jpg"
                    if os.path.isfile(
                        f"static/images/{recipe.file_path.split('.')[0]}.jpg"
                    )
                    else "images/default.svg"
                ),
                recipe.id,
            )
            for recipe in results
        ]
        # all non-empty tags in the database, split by comma, capitalized, sorted and unique
        tags = sorted(
            {
                tag.capitalize()
                for recipe in results
                for tag in recipe.tags.split(",")
                if tag
            }
        )
    except OperationalError as e:
        app.logger.error("Database error: %s", e)

    return render_template("index.html", recipes=recipe_files, tags=tags)


@app.route("/find", methods=["POST"])
def find():
    """Search for recipes by name or tag"""
    search = request.form.get("search", "")
    tag = request.args.get("tag")

    if tag:
        results = Recipes.query.filter(Recipes.tags.contains(tag)).all()
    elif search:
        results = Recipes.query.filter(
            (Recipes.name.contains(search)) | (Recipes.tags.contains(search))
        ).all()
    else:
        results = Recipes.query.all()

    results = [
        Recipe(
            name=" ".join(
                [
                    word.capitalize()
                    for word in recipe.file_path.split(".")[0].split("_")
                ]
            ),
            url=f"/recipes/{recipe.file_path.split('.')[0]}",
            image=(
                f"images/{recipe.file_path.split('.')[0]}.jpg"
                if os.path.isfile(f"static/images/{recipe.file_path.split('.')[0]}.jpg")
                else "images/default.svg"
            ),
            number=recipe.id,
        )
        for recipe in results
    ]

    # sort results by name
    results = sorted(results, key=lambda x: x.name)

    return render_template("search.html", recipes=results)


@app.route("/grid")
def grid():
    """List all recipes"""
    recipes = Recipes.query.all()
    recipes = [
        Recipe(
            name=" ".join(
                [
                    word.capitalize()
                    for word in recipe.file_path.split(".")[0].split("_")
                ]
            ),
            url=f"/recipes/{recipe.file_path.split('.')[0]}",
            image=(
                f"images/{recipe.file_path.split('.')[0]}.jpg"
                if os.path.isfile(f"static/images/{recipe.file_path.split('.')[0]}.jpg")
                else "images/default.svg"
            ),
            number=recipe.id,
        )
        for recipe in recipes
    ]
    recipes = sorted(recipes, key=lambda x: x.name)
    return render_template("list.html", recipes=recipes)


def is_safe_url(url):
    """Validate that the URL is safe to open."""
    parsed = urlparse(url)
    unsafe_symbols = {"`", "|", "&", ";", "<", ">", "(", ")", "$", "{", "}"}
    return (
        parsed.scheme in ("http", "https")
        and parsed.netloc
        and not any(symbol in parsed.path for symbol in unsafe_symbols)
    )


def xdg_open(url):
    """Open a URL in the default browser."""
    if not url or not is_safe_url(url):
        return error("Invalid or unsafe URL")
    try:
        subprocess.run(["xdg-open", url], check=True)
    except subprocess.CalledProcessError as e:
        return error(e)
    return "", 200  # Return empty response


@app.route("/open_link")
def open_link():
    """Open a link in the browser."""
    url = request.args.get("url")
    return xdg_open(url)


@app.route("/git_pull")
def git_pull():
    """Pull the latest changes from the Git repository and restart the Flask app"""
    try:
        subprocess.run(["git", "pull"], check=True)
    except subprocess.CalledProcessError as e:
        return error(e)
    try:
        subprocess.run(["sudo", "systemctl", "restart", "flaskapp.service"], check=True)
    except subprocess.CalledProcessError as e:
        return error(e)
    return "", 200  # Return empty response


@app.route("/make_recipes")
def make_recipes():
    """Generate the HTML files for the recipes"""
    try:
        subprocess.run(["make", f"RECIPES_DIR={RECIPES_DIR}"], check=True)
    except subprocess.CalledProcessError as e:
        return error(e)
    return "", 200


@app.route("/reset")
def reset():
    """Clean the generated HTML files"""
    try:
        subprocess.run(["make", "clean"], check=True)
    except subprocess.CalledProcessError as e:
        return error(e)
    return "", 200


@app.route("/recipes/<recipe>")
def view_recipe(recipe):
    """View a specific recipe"""
    if recipe.isdigit():
        # Get the filename number from sorted list of recipes by db name
        recipe = sorted([recipe.file_path for recipe in Recipes.query.all()])[
            int(recipe) - 1
        ].split(".")[0]
    return xdg_open(f"http://localhost:8001/view/{recipe}")


@app.route("/view/<recipe>")
def view(recipe):
    """View a specific recipe"""
    return render_template(f"recipes/{recipe}.html")


@app.route("/page_up")
def page_up():
    """Scroll up the browser window"""
    xdotool("key Page_Up")
    return "", 200  # Return empty response


@app.route("/page_down")
def page_down():
    """Scroll down the browser window"""
    xdotool("key Page_Down")
    return "", 200  # Return empty response


@app.route("/scroll_up")
def scroll_up():
    """Scroll up the browser window"""
    xdotool("mousemove 100 100 click 4")
    return "", 200  # Return empty response


@app.route("/scroll_down")
def scroll_down():
    """Scroll down the browser window"""
    xdotool("mousemove 100 100 click 5")
    return "", 200  # Return empty response


@app.route("/zoom_in")
def zoom_in():
    """Zoom in the browser window"""
    xdotool("key ctrl+plus")
    return "", 200  # Return empty response


@app.route("/zoom_out")
def zoom_out():
    """Zoom out the browser window"""
    xdotool("key ctrl+minus")
    return "", 200  # Return empty response


@app.route("/commands", methods=["POST"])
def add_command():
    """Add a command to the queue"""
    data = request.json
    commands.append(data)
    return Response(json.dumps({"status": "success"}), content_type="application/json")


@app.route("/commands", methods=["GET"])
def get_commands():
    """Get the next command from the queue"""
    if commands:
        return Response(json.dumps(commands.pop(0)), content_type="application/json")
    return Response(json.dumps({}), content_type="application/json")


@app.route("/api/receipts", methods=["GET"])
def get_receipts():
    """Get all receipts"""
    receipts = Receipt.query.all()
    receipts_list = [
        {
            "id": receipt.id,
            "store": receipt.store,
            "date": receipt.date,
            "time": receipt.time,
            "number": receipt.number,
            "discount": receipt.discount,
            "total": receipt.total,
            "card": receipt.card,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "barcode": item.barcode,
                    "price": item.price,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "total": item.total,
                    "discount_name": item.discount_name,
                    "discount_value": item.discount_value,
                    "receipt_id": item.receipt_id,
                }
                for item in receipt.items
            ],
        }
        for receipt in receipts
    ]
    return Response(json.dumps(receipts_list), content_type="application/json")


@app.route("/api/receipt", methods=["GET"])
def get_receipt():
    """Get a specific receipt by id"""
    receipt_id = request.args.get("id")
    if not receipt_id:
        return error("Receipt ID is required")

    receipt = Receipt.query.get(receipt_id)
    if not receipt:
        return error("Receipt not found")

    receipt_data = {
        "id": receipt.id,
        "store": receipt.store,
        "date": receipt.date,
        "time": receipt.time,
        "number": receipt.number,
        "discount": receipt.discount,
        "total": receipt.total,
        "card": receipt.card,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "barcode": item.barcode,
                "price": item.price,
                "quantity": item.quantity,
                "unit": item.unit,
                "total": item.total,
                "discount_name": item.discount_name,
                "discount_value": item.discount_value,
                "receipt_id": item.receipt_id,
            }
            for item in receipt.items
        ],
    }
    return Response(json.dumps(receipt_data), content_type="application/json")


@app.route("/api/recipes", methods=["GET"])
def get_recipes():
    """Get all recipes"""
    recipes = Recipes.query.all()
    recipes_list = [
        {
            "id": recipe.id,
            "name": recipe.name,
            "url": f"view/{recipe.file_path.split('.')[0]}",
            "tags": recipe.tags
        }
        for recipe in recipes
    ]
    return Response(json.dumps(recipes_list), content_type="application/json")


@app.route("/api/recipe", methods=["GET"])
def get_recipe():
    """Get a specific recipe by id"""
    recipe_id = request.args.get("id")
    if not recipe_id:
        return error("Recipe ID is required")

    recipe = Recipes.query.get(recipe_id)
    if not recipe:
        return error("Recipe not found")

    recipe_ingredients = RecipesIngredients.query.filter_by(recipe_id=recipe.id).all()
    recipe_data = {
        "id": recipe.id,
        "name": recipe.name,
        "url": f"view/{recipe.file_path.split('.')[0]}",
        "ingredients": [ # recipe ingredients
            {
                "id": ing.id,
                "name": ing.name,
                "size": ri.size,
                "unit": ri.unit,
                "info": get_latest_ingredient_info(ing.id)
            }
            for ri in recipe_ingredients
            for ing in Ingredients.query.filter_by(id=ri.ingredient_id).all()
        ],

        "tags": recipe.tags
    }
    return Response(json.dumps(recipe_data), content_type="application/json")


def get_latest_ingredient_info(id):
    """Get the latest price of each linked barcode and return the lowest price with the store item name"""
    ingredient = Ingredients.query.get(id)
    if not ingredient:
        return None

    barcodes = ingredient.barcodes
    if not barcodes:
        return None

    store_items = StoreItem.query.filter(StoreItem.barcode.in_([barcode.barcode for barcode in barcodes])).all()
    
    if not store_items:
        return None

    # Get the store item with the lowest price
    lowest_price_item = min(store_items, key=lambda item: item.price)
    
    return {
        "name": lowest_price_item.name,
        "price": lowest_price_item.price,
        "barcode": lowest_price_item.barcode
    }


@app.route("/api/ingredients", methods=["GET"])
def get_ingredients():
    """Get all ingredients"""
    ingredients = Ingredients.query.all()
    ingredients_list = [
        {
            "id": ing.id,
            "name": ing.name,
            "barcodes": { 
                barcode.barcode : { 
                    "name": get_barcode_name(barcode.barcode),
                    "size": barcode.size,
                    "unit": barcode.unit,
                } for barcode in ing.barcodes 
            },
        }
        for ing in ingredients
    ]
    return Response(json.dumps(ingredients_list), content_type="application/json")


def get_barcode_name(barcode):
    """Get the latest store item name by barcode"""
    store_item = StoreItem.query.filter_by(barcode=barcode).order_by(StoreItem.id.desc()).first()
    return store_item.name if store_item else None


@app.route("/api/unlinked_ingredients", methods=["GET"])
def get_unlinked_ingredients():
    """Get all ingredients that are not linked to any barcodes"""
    unlinked_ingredients = Ingredients.query.filter(
        ~Ingredients.barcodes.any()
    ).all()
    ingredients_list = [
        {
            "id": ing.id,
            "name": ing.name,
        }
        for ing in unlinked_ingredients
    ]
    return Response(json.dumps(ingredients_list), content_type="application/json")


@app.route("/api/ingredient", methods=["GET"])
def get_ingredient():
    """Get a specific ingredient by id"""
    ingredient_id = request.args.get("id")
    if not ingredient_id:
        return error("Ingredient ID is required")

    ingredient = Ingredients.query.get(ingredient_id)
    if not ingredient:
        return error("Ingredient not found")

    ingredient_data = {
        "id": ingredient.id,
        "name": ingredient.name,
        "barcodes": { 
            barcode.barcode: { 
                "name": get_barcode_name(barcode.barcode),
                "size": barcode.size,
                "unit": barcode.unit,
            } for barcode in ingredient.barcodes 
        },
    }
    return Response(json.dumps(ingredient_data), content_type="application/json")


@app.route("/api/link_ingredient", methods=["POST"])
def link_ingredient():
    """Link an ingredient to a barcode"""
    ingredient_id = request.args.get("ingredient_id")
    if not ingredient_id:
        return error("Ingredient ID is required")

    barcode = request.args.get("barcode")
    if not barcode:
        return error("Barcode is required")

    ingredient = Ingredients.query.get(ingredient_id)
    if not ingredient:
        return error("Ingredient not found")

    size = request.args.get("size", "1.0")
    unit = request.args.get("unit", "x")

    barcode_entry = Barcodes.query.filter_by(barcode=barcode).first()
    if not barcode_entry:
        # If the barcode does not exist, create a new one
        barcode_entry = Barcodes(barcode=barcode, size=float(size), unit=unit)
        db.session.add(barcode_entry)
        db.session.commit()

    # Link the ingredient to the barcode
    if barcode_entry not in ingredient.barcodes:
        ingredient.barcodes.append(barcode_entry)
        db.session.commit()

    # Return the ingredient data
    ingredient_data = {
        "id": ingredient.id,
        "name": ingredient.name,
        "barcodes": { 
            barcode.barcode: { 
                "name": get_barcode_name(barcode.barcode),
                "size": barcode.size,
                "unit": barcode.unit,
            } for barcode in ingredient.barcodes 
        },
    }
    return Response(json.dumps(ingredient_data), content_type="application/json")


@app.route("/api/unlink_ingredient", methods=["POST"])
def unlink_ingredient():
    """Unlink an ingredient from a barcode"""
    ingredient_id = request.args.get("ingredient_id")
    if not ingredient_id:
        return error("Ingredient ID is required")

    barcode = request.args.get("barcode")
    if not barcode:
        return error("Barcode is required")

    ingredient = Ingredients.query.get(ingredient_id)
    if not ingredient:
        return error("Ingredient not found")

    barcode_entry = Barcodes.query.filter_by(barcode=barcode).first()
    if not barcode_entry:
        return error("Barcode not found")

    # Unlink the ingredient from the barcode
    if barcode_entry in ingredient.barcodes:
        ingredient.barcodes.remove(barcode_entry)
        db.session.commit()

    # If the barcode is not linked to any other ingredients, delete it
    if not barcode_entry.ingredients:
        db.session.delete(barcode_entry)
        db.session.commit()

    # Return the ingredient data
    ingredient_data = {
        "id": ingredient.id,
        "name": ingredient.name,
        "barcodes": { 
            barcode.barcode: { 
                "name": get_barcode_name(barcode.barcode),
                "size": barcode.size,
                "unit": barcode.unit,
            } for barcode in ingredient.barcodes 
        },
    }
    return Response(json.dumps(ingredient_data), content_type="application/json")


@app.route("/api/update_barcode_size", methods=["POST"])
def update_barcode_size():
    """Update the size of a barcode"""
    barcode = request.args.get("barcode")
    if not barcode:
        return error("Barcode is required")

    size = request.args.get("size")
    if not size:
        return error("Size is required")

    barcode_entry = Barcodes.query.filter_by(barcode=barcode).first()
    if not barcode_entry:
        return error("Barcode not found")
    try:
        size = float(size)
    except ValueError:
        return error("Size must be a number")
    barcode_entry.size = size
    db.session.commit()

    return Response(json.dumps({"status": "success"}), content_type="application/json")


@app.route("/api/store_items", methods=["GET"])
def get_store_items():
    """Get all store items"""
    store_items = StoreItem.query.all()
    items_list = [
        {
            "id": item.id,
            "name": item.name,
            "barcode": item.barcode,
            "price": item.price,
            "quantity": item.quantity,
            "unit": item.unit,
            "total": item.total,
            "discount_name": item.discount_name,
            "discount_value": item.discount_value,
            "receipt_id": item.receipt_id,
        }
        for item in store_items
    ]
    return Response(json.dumps(items_list), content_type="application/json")


@app.route("/api/store_item", methods=["GET"])
def get_store_item():
    """Get a specific store item by id"""
    item_id = request.args.get("id")
    if not item_id:
        return error("Store Item ID is required")

    item = StoreItem.query.get(item_id)
    if not item:
        return error("Store Item not found")

    item_data = {
        "id": item.id,
        "name": item.name,
        "barcode": item.barcode,
        "price": item.price,
        "quantity": item.quantity,
        "unit": item.unit,
        "total": item.total,
        "discount_name": item.discount_name,
        "discount_value": item.discount_value,
        "receipt_id": item.receipt_id,
    }
    return Response(json.dumps(item_data), content_type="application/json")


@app.route("/api/barcodes_by_ingredient_name", methods=["GET"])
def get_barcodes_by_ingredient_name():
    """Get all barcodes for a specific ingredient by name"""
    ingredient_name = request.args.get("name")
    if not ingredient_name:
        return error("Ingredient name is required")

    ingredient = Ingredients.query.filter_by(name=ingredient_name).first()
    if not ingredient:
        return error("Ingredient not found")

    barcodes = [barcode.barcode for barcode in ingredient.barcodes]
    return Response(json.dumps(barcodes), content_type="application/json")
    

@app.route("/api/link_ingredient_to_barcode", methods=["POST"])
def link_ingredient_to_barcode():
    """Link an ingredient to a barcode"""
    barcode = request.args.get("barcode")
    if not barcode:
        return error("Barcode is required")

    ingredient_name = request.args.get("ingredient")
    if not ingredient_name:
        return error("Ingredient name is required")

    ingredient = Ingredients.query.filter_by(name=ingredient_name).first()
    if not ingredient:
        return error("Ingredient not found")

    barcode_entry = Barcodes.query.filter_by(barcode=barcode).first()
    if not barcode_entry:
        return error("Barcode not found")

    # Link the ingredient to the barcode
    if barcode_entry not in ingredient.barcodes:
        ingredient.barcodes.append(barcode_entry)
        db.session.commit()

    return Response(json.dumps({"status": "success"}), content_type="application/json")


def xdotool(cmd):
    """Run the xdotool command with the correct DISPLAY environment variable"""
    try:
        subprocess.run(["xdotool", *cmd.split()], check=True)
    except subprocess.CalledProcessError as e:
        return error(e)
    return "", 200  # Return empty response


def error(e):
    """Return an error message"""
    app.logger.error("Error: %s", e)  # Log the error message
    return str(e), 400  # Return error message


if __name__ == "__main__":
    os.chdir(BASE_DIR)
    app.run(host="0.0.0.0", port=8001)
