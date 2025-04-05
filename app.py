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
commands = []


@dataclass
class Recipes(db.Model):
    """Database model for recipes"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    file_path = db.Column(db.String(120), nullable=False)
    tags = db.Column(db.String(200))  # Comma-separated tags


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
