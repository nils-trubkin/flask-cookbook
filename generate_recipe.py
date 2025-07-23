""" Generate a recipe HTML file from a markdown file and update the database. """

import sys
import os
import re
from fractions import Fraction
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import db, Recipes, Ingredients, RecipesIngredients

RECIPE_DB_PATH = "recipes.db"

# SQLAlchemy setup
engine = create_engine(f"sqlite:///{RECIPE_DB_PATH}")
db.Session = scoped_session(sessionmaker(bind=engine))
session = db.Session()


def setup_database():
    """Set up the database and create tables if they do not exist."""
    db.metadata.create_all(bind=engine)


def add_ingredient_to_db(name):
    """Add an ingredient to the database if it doesn't exist."""
    ingredient = session.query(Ingredients).filter_by(name=name).first()
    if not ingredient:
        ingredient = Ingredients(name=name)
        session.add(ingredient)
        session.commit()
    return ingredient.id


def update_recipe_in_database(name, file_path, tags):
    """Update or add a recipe in the database."""
    recipe = session.query(Recipes).filter_by(file_path=file_path).first()

    if recipe:
        recipe.name = name
        recipe.tags = ",".join(tags)
    else:
        recipe = Recipes(name=name, file_path=file_path, tags=",".join(tags))
        session.add(recipe)

    session.commit()
    return recipe.id


def add_recipe_ingredient_to_db(recipe_id, ingredient_id, size, unit):
    """Add a recipe ingredient to the database."""
    ri = RecipesIngredients(
        recipe_id=recipe_id, ingredient_id=ingredient_id, size=size, unit=unit
    )
    session.add(ri)
    session.commit()


def parse_markdown(md_file):
    """
    Parse the markdown file into structured recipe data.
    Returns:
        dict with keys: name, ingredients, ingredient_links, instructions, tags
    """
    parsed = {
        "name": None,
        "ingredients": [],
        "ingredient_links": [],  # tuples of (ingredient_id, size, unit)
        "instructions": [],
        "tags": [],
    }

    with open(md_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    section = None
    for line in lines:
        line = line.strip()
        if line.startswith("# "):
            parsed["name"] = line[2:]
        elif line.startswith("## Ingredients"):
            section = "ingredients"
        elif line.startswith("## Instructions"):
            section = "instructions"
        elif line.startswith("## Tags"):
            section = "tags"
        elif line.startswith("##"):
            section = None
        elif section == "ingredients" and line[:1] in {"-", "*", "+"}:
            ingredient_line = line[1:].strip()
            processed_line, link = process_ingredient_line(ingredient_line)
            parsed["ingredients"].append(processed_line)
            if link:
                parsed["ingredient_links"].append(link)
        elif section == "instructions" and line:
            parsed["instructions"].append(line)
        elif section == "tags" and line:
            parsed["tags"] = [tag.strip().lower() for tag in line.split(",")]

    return parsed


def process_ingredient_line(line):
    """
    Process a single ingredient line, extracting size/unit and database id if available.
    Returns:
        (formatted_line: str, (ingredient_id, size, unit) or None)
    """
    if "@" in line:
        name_part, tag_part = line.split("@", 1)
        tag = tag_part.split(" ")[0].strip()
        tag_clean = re.sub(r"[^\w-]", "", tag).lower()
        formatted_tag = tag_clean.replace("-", " ")
        ingredient_id = add_ingredient_to_db(tag_clean)
        size, unit = parse_size_and_unit(name_part.strip())
        line = line.replace(f"@{tag}", formatted_tag)
        return line, (ingredient_id, size, unit)
    return line, None


def parse_size_and_unit(size_str):
    """
    Parse size and unit from a string like:
    - '1.5kg'
    - '1/2 cup'
    - '500 g'
    - 'g'     (defaults to 1)
    - ''      (defaults to 1, 'x')

    Returns: (size: float, unit: str)
    """
    size_str = size_str.strip()

    # Match optional number (fraction, float, or int), optional space, then unit
    match = re.match(r"^((\d+/\d+)|(\d*\.\d+)|(\d+))?\s*([a-zA-Z]+)?$", size_str)
    if not match:
        raise ValueError(f"Invalid format for size_str: '{size_str}'")

    num_str = match.group(1)
    unit = match.group(5).lower() if match.group(5) else "x"

    if not num_str:
        size = 1.0
    else:
        try:
            size = float(Fraction(num_str))
        except ValueError as exc:
            raise ValueError(f"Could not parse size number: '{num_str}'") from exc

    return size, unit


def generate_html_output(md_file, output_file, template_file, image_file=None):
    """
    Generate an HTML file from markdown content using a template.
    Returns:
        name, ingredient_links (tuples), tags
    """
    # Parse markdown into structured data
    parsed = parse_markdown(md_file)

    # Read HTML template
    with open(template_file, "r", encoding="utf-8") as f:
        template = f.read()

    # Generate HTML content blocks
    image_tag = (
        f"""
        <img class="recipe-main" src="{{{{ url_for('static',
        filename='images/{os.path.basename(image_file)}') }}}}" alt="{parsed['name']} image">
        """
        if image_file
        else ""
    )

    ingredients_html = "\n".join(
        [f"<li>{ingredient}</li>" for ingredient in parsed["ingredients"]]
    )

    instructions_html = "\n".join(
        [f"<p>{instruction}</p>" for instruction in parsed["instructions"]]
    )

    # Fill template placeholders
    output_html = template
    output_html = output_html.replace("{name}", parsed["name"])
    output_html = output_html.replace("{image_tag}", image_tag)
    output_html = output_html.replace("{ingredients_html}", ingredients_html)
    output_html = output_html.replace("{instructions_html}", instructions_html)

    # Write HTML output
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_html)

    # Optionally copy image to static/images/ with downscale
    if image_file:
        os.system(
            f"convert {image_file} -resize 400x static/images/{os.path.basename(image_file)}"
        )

    return parsed["name"], parsed["ingredient_links"], parsed["tags"]


def parse_args():
    """Parse CLI args and generate recipe output."""
    if len(sys.argv) < 4 or len(sys.argv) > 5:
        print(
            "Usage: python generate_recipe.py <markdown_file> <output_file> <template_file> [image_file]"
        )
        sys.exit(1)

    md_file = sys.argv[1]
    output_file = sys.argv[2]
    template_file = sys.argv[3]
    image_file = sys.argv[4] if len(sys.argv) == 5 else None

    setup_database()

    name, ingredient_links, tags = generate_html_output(
        md_file, output_file, template_file, image_file
    )

    recipe_id = update_recipe_in_database(name, os.path.basename(output_file), tags)

    for ingredient_id, size, unit in ingredient_links:
        add_recipe_ingredient_to_db(recipe_id, ingredient_id, size, unit)

    print(f"🍽️ Recipe '{name}' generated successfully and saved to {output_file}.")


if __name__ == "__main__":
    try:
        parse_args()
    finally:
        session.close()
