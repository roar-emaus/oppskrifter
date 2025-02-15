import sqlite3
from typing import Self
from enum import Enum
from pydantic import BaseModel  # This works for Pydantic v2 as well

# ------------------------------
# Define Pydantic Models
# ------------------------------

class Unit(str, Enum):
    GRAM = "g"
    KILOGRAM = "kg"
    MILLILITER = "ml"
    LITER = "l"
    DECILITER = "dl"
    PCS = "pcs"

class Ingredient(BaseModel):
    name: str


class RecipeIngredient(BaseModel):
    ingredient: Ingredient
    quantity: float
    unit: Unit


class Instruction(BaseModel):
    step_number: int
    description: str


class Tag(BaseModel):
    name: str
    children: Self | None = None  # Optional nested tags


class Recipe(BaseModel):
    title: str
    description: str | None = None
    comments: str | None = None
    prep_time: int | None = None  # minutes
    cook_time: int | None = None  # minutes
    servings: int | None = None
    ingredients: list[RecipeIngredient]
    instructions: list[Instruction]
    tags: list[Tag]


# ------------------------------
# SQLite Database Functions
# ------------------------------

def create_tables(conn: sqlite3.Connection):
    """Create the recipes, ingredients, instructions, tags, and join tables."""
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                comments TEXT,
                prep_time INTEGER,
                cook_time INTEGER,
                servings INTEGER
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipe_ingredients (
                recipe_id INTEGER,
                ingredient_id INTEGER,
                quantity REAL,
                unit TEXT,
                PRIMARY KEY (recipe_id, ingredient_id),
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS instructions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER,
                step_number INTEGER,
                description TEXT NOT NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipe_tags (
                recipe_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (recipe_id, tag_id),
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );
        """)


# ------------------------------
# Helper Insertion Functions
# ------------------------------

def get_or_create_ingredient(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO ingredients (name) VALUES (?)", (name,))
    return cur.lastrowid

def get_or_create_tag(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("SELECT id FROM tags WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cur.lastrowid

def insert_recipe(conn: sqlite3.Connection, recipe: Recipe) -> int:
    cur = conn.execute(
        "INSERT INTO recipes (title, description, prep_time, cook_time, servings) VALUES (?, ?, ?, ?, ?)",
        (recipe.title, recipe.description, recipe.prep_time, recipe.cook_time, recipe.servings)
    )
    recipe_id = cur.lastrowid

    # Insert instructions
    if recipe.instructions:
        for instr in recipe.instructions:
            conn.execute(
                "INSERT INTO instructions (recipe_id, step_number, description) VALUES (?, ?, ?)",
                (recipe_id, instr.step_number, instr.description)
            )

    # Insert ingredients and the join table rows
    if recipe.ingredients:
        for ri in recipe.ingredients:
            ingredient_id = get_or_create_ingredient(conn, ri.ingredient.name)
            conn.execute(
                "INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)",
                (recipe_id, ingredient_id, ri.quantity, ri.unit)
            )

    # Insert tags and recipe_tags join table rows
    if recipe.tags:
        for tag in recipe.tags:
            tag_id = get_or_create_tag(conn, tag.name)
            conn.execute(
                "INSERT INTO recipe_tags (recipe_id, tag_id) VALUES (?, ?)",
                (recipe_id, tag_id)
            )

    conn.commit()
    return recipe_id

# ------------------------------
# Mock Recipes
# ------------------------------

def create_mock_recipes():
    # Recipe 1: Pancakes
    pancakes = Recipe(
        title="Pancakes",
        description="Fluffy breakfast pancakes.",
        prep_time=10,
        cook_time=15,
        servings=4,
        ingredients=[
            RecipeIngredient(ingredient=Ingredient(name="Flour"), quantity=200, unit=Unit.GRAM),
            RecipeIngredient(ingredient=Ingredient(name="Milk"), quantity=300, unit=Unit.MILLILITER),
            RecipeIngredient(ingredient=Ingredient(name="Egg"), quantity=2, unit=Unit.PCS),
            RecipeIngredient(ingredient=Ingredient(name="Butter"), quantity=50, unit=Unit.GRAM)
        ],
        instructions=[
            Instruction(step_number=1, description="Mix all dry ingredients."),
            Instruction(step_number=2, description="Add milk and eggs, whisk until smooth."),
            Instruction(step_number=3, description="Heat a frying pan and melt butter."),
            Instruction(step_number=4, description="Pour batter into the pan and cook until golden on both sides.")
        ],
        tags=[Tag(name="Breakfast"), Tag(name="Easy")]
    )

    # Recipe 2: Spaghetti Bolognese
    spaghetti = Recipe(
        title="Spaghetti Bolognese",
        description="Classic Italian pasta with meat sauce.",
        prep_time=15,
        cook_time=45,
        servings=4,
        ingredients=[
            RecipeIngredient(ingredient=Ingredient(name="Spaghetti"), quantity=400, unit=Unit.GRAM),
            RecipeIngredient(ingredient=Ingredient(name="Ground Beef"), quantity=500, unit=Unit.GRAM),
            RecipeIngredient(ingredient=Ingredient(name="Tomato Sauce"), quantity=800, unit=Unit.GRAM),
            RecipeIngredient(ingredient=Ingredient(name="Onion"), quantity=1, unit=Unit.PCS),
            RecipeIngredient(ingredient=Ingredient(name="Garlic"), quantity=2, unit=Unit.PCS)
        ],
        instructions=[
            Instruction(step_number=1, description="Boil spaghetti until al dente."),
            Instruction(step_number=2, description="Sauté onions and garlic until translucent."),
            Instruction(step_number=3, description="Add ground beef and cook until browned."),
            Instruction(step_number=4, description="Pour in tomato sauce and simmer for 30 minutes."),
            Instruction(step_number=5, description="Serve sauce over spaghetti.")
        ],
        tags=[Tag(name="Dinner"), Tag(name="Italian")]
    )
    return [pancakes, spaghetti]


# ------------------------------
# Main Program Execution
# ------------------------------

def main():
    # Connect to an in-memory SQLite database
    conn = sqlite3.connect("oppskrifter.db")
    create_tables(conn)

    recipes = create_mock_recipes()
    for recipe in recipes:
        insert_recipe(conn, recipe)
    conn.close()


if __name__ == "__main__":
    main()

