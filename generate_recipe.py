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
    Parse the markdown file into name, ingredients, and instructions.
    """
    name = None
    ingredients = []
    ingredient_id_size_unit = {}
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
                tag = tag_split[1].split(" ")[0].strip()
                tag_lower = tag.lower()
                formatted_tag = tag_lower.replace("-", " ")
                ingredient_id = add_ingredient_to_db(tag_lower)
                size, unit = parse_size_and_unit(tag_split[0].strip())
                ingredient_id_size_unit[tag] = (ingredient_id, size, unit)
                ingredient = ingredient.replace(f"@{tag}", formatted_tag)
            ingredients.append(ingredient)
        elif section == "instructions" and line:  # Instruction line
            instructions.append(line)
        elif section == "tags" and line:  # Tag line
            tags = line.split(",")
            tags = [tag.strip().lower() for tag in tags]

    return name, ingredients, ingredient_id_size_unit, instructions, tags


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
    unit = match.group(5) if match.group(5) else "x"

    if not num_str:
        size = 1.0
    else:
        try:
            size = float(Fraction(num_str))
        except ValueError:
            raise ValueError(f"Could not parse size number: '{num_str}'")

    return size, unit


def generate_html_output(md_file, output_file, template_file, image_file=None):
    """
    Generate an HTML file with the desired template structure from the markdown content.
    """
    # Parse markdown content into name, ingredients, and instructions
    name, ingredients, ingredient_id_size_unit, instructions, tags = parse_markdown(
        md_file
    )

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

    return name, ingredient_id_size_unit, tags


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

    name, ingredient_id_size_unit, tags = generate_html_output(
        md_file, output_file, template_file, image_file
    )

    # Update the database with the new recipe
    recipe_id = update_recipe_in_database(name, output_file.split("/")[-1], tags)

    # Add recipe ingredients to the database
    for ingredient_id, size, unit in ingredient_id_size_unit.values():
        add_recipe_ingredient_to_db(recipe_id, ingredient_id, size, unit)
    print(f"🍽️ Recipe '{name}' generated successfully and saved to {output_file}.")


if __name__ == "__main__":
    try:
        parse_args()
    finally:
        session.close()
