""" Generate a recipe HTML file from a markdown file and update the database. """

import sys
import os
import sqlite3
import re


RECIPE_DB_PATH = "recipes.db"


def setup_database(db_path=RECIPE_DB_PATH):
    """
    Create or connect to the database and ensure the `recipes` table exists.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        file_path TEXT NOT NULL UNIQUE,
        tags TEXT
    );
    """
    )
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );
    """
    )
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS barcodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT NOT NULL UNIQUE,
        size REAL NOT NULL DEFAULT 1.0,
        unit TEXT NOT NULL DEFAULT 'x'
    );
    """
    )
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS ingredient_barcodes (
        ingredient_id INTEGER NOT NULL,
        barcode_id INTEGER NOT NULL,
        PRIMARY KEY (ingredient_id, barcode_id),
        FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE,
        FOREIGN KEY (barcode_id) REFERENCES barcodes(id) ON DELETE CASCADE
    );
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipe_id INTEGER NOT NULL,
        size REAL NOT NULL,
        unit TEXT NOT NULL,
        FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
    );
    """
    )
    conn.commit()
    conn.close()


def update_recipe_in_database(name, ingredient_size_unit, file_path, tags, db_path=RECIPE_DB_PATH):
    """
    Insert or update a recipe entry in the database.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the recipe already exists
    cursor.execute("SELECT id FROM recipes WHERE file_path = ?", (file_path,))
    recipe = cursor.fetchone()

    if recipe:
        recipe_id = recipe[0]
        # Update existing recipe
        cursor.execute(
            """
        UPDATE recipes
        SET name = ?, tags = ?
        WHERE file_path = ?
        """,
            (name, ",".join(tags), file_path),
        )
    else:
        # Insert new recipe
        cursor.execute(
            """
        INSERT INTO recipes (name, file_path, tags)
        VALUES (?, ?, ?)
        """,
            (name, file_path, ",".join(tags)),
        )
        recipe_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return recipe_id


def parse_markdown(md_file):
    """
    Parse the markdown file into name, ingredients, and instructions.
    """
    name = None
    ingredients = []
    ingredient_size_unit = {}
    instructions = []
    tags = []

    with open(md_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    section = None
    for line in lines:
        line = line.strip()
        if line.startswith("# "):  # Title
            name = line[2:]
        elif line.startswith("## Ingredients"):  # Ingredients section
            section = "ingredients"
        elif line.startswith("## Instructions"):  # Instructions section
            section = "instructions"
        elif line.startswith("## Tags"):  # Tags section
            section = "tags"
        elif line.startswith("##"):  # Unrecognized section (skip for now)
            section = None
        elif section == "ingredients" and line[:1] in {
            "-",
            "*",
            "+",
        }:  # Ingredient item
            ingredient = line[1:].strip()
            if "@" in ingredient:
                tag_split = ingredient.split("@")
                tag = tag_split[1].split(" ")[0].strip().lower()
                formatted_tag = tag.replace("-", " ")
                add_ingredient_to_db(tag)
                ingredient_size_unit[tag] = parse_size_and_unit(tag_split[0].strip())
                ingredient = ingredient.replace(f"@{tag}", formatted_tag)
            ingredients.append(ingredient)
        elif section == "instructions" and line:  # Instruction line
            instructions.append(line)
        elif section == "tags" and line:  # Tag line
            tags = line.split(",")
            tags = [tag.strip().lower() for tag in tags]

    return name, ingredients, ingredient_size_unit, instructions, tags


def add_ingredient_to_db(name, db_path=RECIPE_DB_PATH):
    """
    Add an ingredient to the database if it contains '@'.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the ingredient already exists
    cursor.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
    if not cursor.fetchone():
        # Insert new ingredient
        cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (name,))

    conn.commit()
    conn.close()


def add_recipe_ingredient_to_db(recipe_id, size, unit, db_path=RECIPE_DB_PATH):
    """
    Add a recipe ingredient to the database.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert new recipe ingredient
    cursor.execute(
        """
        INSERT INTO recipe_ingredients (recipe_id, size, unit)
        VALUES (?, ?, ?)
        """,
        (recipe_id, size, unit),
    )

    conn.commit()
    conn.close()


def parse_size_and_unit(size_str):
    """
    Parse the size and unit from a string like '1.5kg' or '2x'.
    Returns a tuple (size: float, unit: str).
    """
    match = re.match(r'^([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)$', size_str)
    if match:
        size = float(match.group(1))
        unit = match.group(2) if match.group(2) else "x"
        return size, unit
    else:
        raise ValueError(f"Invalid size string: {size_str}")


def generate_html_output(md_file, output_file, template_file, image_file=None):
    """
    Generate an HTML file with the desired template structure from the markdown content.
    """
    # Parse markdown content into name, ingredients, and instructions
    name, ingredients, ingredient_size_unit, instructions, tags = parse_markdown(md_file)

    # Read the template
    with open(template_file, "r", encoding="utf-8") as f:
        template = f.read()

    # Generate the content for each block
    image_tag = (
        f"""
        <img class="recipe-main" src="{{{{ url_for('static',
        filename='images/{os.path.basename(image_file)}') }}}}" alt="{name} image">
        """
        if image_file
        else ""
    )

    ingredients_html = "\n".join(
        [f"<li>{ingredient}</li>" for ingredient in ingredients]
    )

    instructions_html = "\n".join(
        [f"<p>{instruction}</p>" for instruction in instructions]
    )

    # Replace the placeholders in the template with actual content
    output_html = template
    output_html = output_html.replace("{name}", name)
    output_html = output_html.replace("{image_tag}", image_tag)
    output_html = output_html.replace("{ingredients_html}", ingredients_html)
    output_html = output_html.replace("{instructions_html}", instructions_html)

    # Write the generated HTML to the output file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_html)

    # Copy the image to /static folder while downsampling it to 400px width
    if image_file:
        os.system(
            f"convert {image_file} -resize 400x static/images/{os.path.basename(image_file)}"
        )

    return name, ingredient_size_unit, tags


def parse_args():
    """Parse command line arguments and call the main function."""
    if len(sys.argv) < 4 or len(sys.argv) > 5:
        print(
            "Usage: python generate_recipe.py <markdown_file> <output_file> <template_file> \
[image_file]"
        )
        sys.exit(1)

    md_file = sys.argv[1]
    output_file = sys.argv[2]
    template_file = sys.argv[3]
    image_file = sys.argv[4] if len(sys.argv) == 5 else None

    # Ensure the database is set up
    setup_database()

    name, ingredient_size_unit, tags = generate_html_output(md_file, output_file, template_file, image_file)

    # Update the database with the new recipe
    recipe_id = update_recipe_in_database(name, ingredient_size_unit, output_file.split("/")[-1], tags)

    # Add recipe ingredients to the database
    for ingredient, (size, unit) in ingredient_size_unit.items():
        add_recipe_ingredient_to_db(recipe_id, size, unit)


if __name__ == "__main__":
    parse_args()
