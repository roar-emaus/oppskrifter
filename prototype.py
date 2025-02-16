import sys
import sqlite3
import logging
from typing import Self
from enum import Enum
from pydantic import BaseModel  # This works for Pydantic v2 as well


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
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


class IngredientCategory(str, Enum):
    VEGETABLE = "vegetable"
    MEAT = "meat"
    FISH = "fish"
    FRUIT = "fruit"
    SPICE = "spice"


class Ingredient(BaseModel):
    name: str
    category: IngredientCategory | None = None


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
    ingredients: list[RecipeIngredient | None]
    instructions: list[Instruction | None]
    tags: list[Tag | None]


# ------------------------------
# SQLite Database Functions
# ------------------------------

def create_tables(conn: sqlite3.Connection):
    """Create the recipes, ingredients, instructions, tags, and join tables."""
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,   -- identifier to group different iterations of the same recipe
                version INTEGER NOT NULL,
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
                name TEXT NOT NULL,
                category TEXT
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

def get_or_create_ingredient(conn: sqlite3.Connection, ingredient: Ingredient) -> int:
    cur = conn.execute("SELECT id FROM ingredients WHERE name = ?", (ingredient.name,))
    row = cur.fetchone()
    if row:
        logger.info(f"Ingredient {ingredient.name} already exists")
        return row[0]
    cur = conn.execute("INSERT INTO ingredients (name, category) VALUES (?, ?)", (ingredient.name, ingredient.category))
    logger.info(f"Inserted ingredient {ingredient.name} with ID {cur.lastrowid}")
    return cur.lastrowid


def get_or_create_tag(conn: sqlite3.Connection, tag: Tag) -> int:
    cur = conn.execute("SELECT id FROM tags WHERE name = ?", (tag.name,))
    row = cur.fetchone()
    if row:
        logger.info(f"Tag {tag.name} already exists")
        return row[0]
    cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (tag.name,))
    logger.info(f"Inserted Tag {tag.name} with ID {cur.lastrowid}")
    return cur.lastrowid


def insert_recipe(conn: sqlite3.Connection, recipe: Recipe, group_id: int | None = None) -> int:

    if group_id is None:
        # New recipe, version 1
        cur = conn.execute(
            "INSERT INTO recipes (group_id, version, title, description, comments, prep_time, cook_time, servings) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (None, 1, recipe.title, recipe.description, recipe.comments, recipe.prep_time, recipe.cook_time, recipe.servings)
        )
        recipe_id = cur.lastrowid
        # Use the inserted id as the group_id for subsequent versions.
        conn.execute("UPDATE recipes SET group_id = ? WHERE id = ?", (recipe_id, recipe_id))
        group_id = recipe_id
        version = 1
    else:
        # Insert a new version for an existing recipe group.
        cur = conn.execute("SELECT MAX(version) FROM recipes WHERE group_id = ?", (group_id,))
        max_version = cur.fetchone()[0] or 0
        version = max_version + 1
        cur = conn.execute(
            "INSERT INTO recipes (group_id, version, title, description, comments, prep_time, cook_time, servings) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (group_id, version, recipe.title, recipe.description, recipe.comments, recipe.prep_time, recipe.cook_time, recipe.servings)
        )
        recipe_id = cur.lastrowid

    logger.info(f"Inserting recipe {recipe_id}, version {version}\n{recipe.model_dump()}")

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
            ingredient_id = get_or_create_ingredient(conn, ri.ingredient)
            conn.execute(
                "INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)",
                (recipe_id, ingredient_id, ri.quantity, ri.unit)
            )

    # Insert tags and recipe_tags join table rows
    if recipe.tags:
        for tag in recipe.tags:
            tag_id = get_or_create_tag(conn, tag)
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
    # Original version of Pancakes
    pancakes_v1 = Recipe(
        title="Pancakes",
        description="Fluffy breakfast pancakes.",
        prep_time=10,
        cook_time=15,
        servings=4,
        ingredients=[
            RecipeIngredient(ingredient=Ingredient(name="Flour"), quantity=200, unit=Unit.GRAM),
            RecipeIngredient(ingredient=Ingredient(name="Milk"), quantity=300, unit=Unit.MILLILITER),
            RecipeIngredient(ingredient=Ingredient(name="Egg"), quantity=2, unit=Unit.PCS),  # Adjust unit if needed
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

    # A new version of Pancakes with a slight variation.
    pancakes_v2 = Recipe(
        title="Pancakes",
        description="Fluffy breakfast pancakes with a hint of vanilla.",
        comments="this is much better",
        prep_time=12,
        cook_time=15,
        servings=4,
        ingredients=[
            RecipeIngredient(ingredient=Ingredient(name="Flour"), quantity=200, unit=Unit.GRAM),
            RecipeIngredient(ingredient=Ingredient(name="Milk"), quantity=300, unit=Unit.MILLILITER),
            RecipeIngredient(ingredient=Ingredient(name="Egg"), quantity=2, unit=Unit.PCS),
            RecipeIngredient(ingredient=Ingredient(name="Butter"), quantity=50, unit=Unit.GRAM),
            RecipeIngredient(ingredient=Ingredient(name="Vanilla Extract"), quantity=5, unit=Unit.MILLILITER)
        ],
        instructions=[
            Instruction(step_number=1, description="Mix all dry ingredients."),
            Instruction(step_number=2, description="Add milk, eggs, and vanilla extract, then whisk until smooth."),
            Instruction(step_number=3, description="Heat a frying pan and melt butter."),
            Instruction(step_number=4, description="Pour batter into the pan and cook until golden on both sides.")
        ],
        tags=[Tag(name="Breakfast"), Tag(name="Easy"), Tag(name="Sweet")]
    )

    # Original version of Spaghetti Bolognese
    spaghetti_v1 = Recipe(
        title="Spaghetti Bolognese",
        description="Classic Italian pasta with meat sauce.",
        prep_time=15,
        cook_time=45,
        servings=4,
        ingredients=[
            RecipeIngredient(ingredient=Ingredient(name="Spaghetti"), quantity=400, unit=Unit.GRAM),
            RecipeIngredient(ingredient=Ingredient(name="Ground Beef"), quantity=500, unit=Unit.GRAM),
            RecipeIngredient(ingredient=Ingredient(name="Tomato Sauce"), quantity=800, unit=Unit.MILLILITER),
            RecipeIngredient(ingredient=Ingredient(name="Onion"), quantity=1, unit=Unit.PCS),  # Adjust unit for countable items if needed
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
    return pancakes_v1, pancakes_v2, spaghetti_v1


if __name__ == "__main__":
    # Connect to an in-memory SQLite database
    conn = sqlite3.connect("oppskrifter.db")
    create_tables(conn)

    pancakes_v1,  pancakes_v2, spaghetti_v1 = create_mock_recipes()
    pancake_id = insert_recipe(conn=conn, recipe=pancakes_v1, group_id=None)
    pancake_id = insert_recipe(conn=conn, recipe=pancakes_v2, group_id=pancake_id)
    spaghetti_id = insert_recipe(conn=conn, recipe=spaghetti_v1, group_id=None)
    conn.close()


