""" Generate a recipe HTML file from a markdown file and update the database. """

import sys
import os
import sqlite3


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

    CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS barcodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingredient_id INTEGER NOT NULL,
        barcode TEXT NOT NULL,
        UNIQUE(ingredient_id, barcode),
        FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
    );
    """
    )
    conn.commit()
    conn.close()


def update_recipe_in_database(name, file_path, tags, db_path=RECIPE_DB_PATH):
    """
    Insert or update a recipe entry in the database.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the recipe already exists
    cursor.execute("SELECT id FROM recipes WHERE file_path = ?", (file_path,))
    recipe = cursor.fetchone()

    if recipe:
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

    conn.commit()
    conn.close()


def parse_markdown(md_file):
    """
    Parse the markdown file into name, ingredients, and instructions.
    """
    name = None
    ingredients = []
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
            if ingredient.contains("@"):
                tag = ingredient.split("@")[1].split(" ")[0].strip()
                formatted_tag = tag.replace("-", " ")
                add_ingredient_to_db(tag)
                ingredient = ingredient.replace(f"@{tag}", formatted_tag)
            ingredients.append(ingredient)
        elif section == "instructions" and line:  # Instruction line
            instructions.append(line)
        elif section == "tags" and line:  # Tag line
            tags = line.split(",")
            tags = [tag.strip().lower() for tag in tags]

    return name, ingredients, instructions, tags


def add_ingredient_to_db(ingredient, db_path=RECIPE_DB_PATH):
    """
    Add an ingredient to the database if it contains '@'.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the ingredient already exists
    cursor.execute("SELECT id FROM ingredients WHERE name = ?", (ingredient,))
    if not cursor.fetchone():
        # Insert new ingredient
        cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (ingredient,))

    conn.commit()
    conn.close()


def generate_html_output(md_file, output_file, template_file, image_file=None):
    """
    Generate an HTML file with the desired template structure from the markdown content.
    """
    # Parse markdown content into name, ingredients, and instructions
    name, ingredients, instructions, tags = parse_markdown(md_file)

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

    return name, tags


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

    name, tags = generate_html_output(md_file, output_file, template_file, image_file)

    # Update the database with the new recipe
    update_recipe_in_database(name, output_file.split("/")[-1], tags)


if __name__ == "__main__":
    parse_args()
