"""
Flask backend of the Pizza knowledge application (starter code).

Run from the project folder:
    python backend/app.py
and open http://localhost:8000 in a browser. The REST API lives under /api.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from kb import InvalidInput, KBError, KnowledgeBase, OntologyError

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
DEFAULT_ONTOLOGY = ROOT / "data" / "pizza_tutorial.rdf"
DEFAULT_STORE = ROOT / "data" / "added_knowledge.ttl"

# A machine-readable description of the API. GET /api returns it, so that
# a client (or, in Lab 4, an LLM) can discover what the API can do.
ENDPOINTS = [
    {"method": "GET", "path": "/api", "description": "This list of endpoints."},
    {"method": "GET", "path": "/api/schema", "description": "Namespace, prefixes, classes, properties and individuals of the ontology."},
    {"method": "GET", "path": "/api/toppings", "description": "All topping classes with parent, top-level category and spiciness."},
    {"method": "GET", "path": "/api/bases", "description": "All pizza base classes."},
    {"method": "GET", "path": "/api/spiciness", "description": "The spiciness levels (Hot, Medium, Mild)."},
    {"method": "GET", "path": "/api/pizza-types", "description": "All named pizza types with their toppings."},
    {"method": "GET", "path": "/api/pizzas", "description": "Pizza individuals.",
     "query": {"topping": "topping or topping category, e.g. MeatTopping",
               "minCalories": "integer, inclusive", "maxCalories": "integer, inclusive",
               "vegetarian": "true/false"}},
    {"method": "GET", "path": "/api/pizzas/<name>", "description": "Details of one pizza: type, calories, base, toppings."},
    {"method": "GET", "path": "/api/entity/<name>", "description": "All statements about any entity (class, individual or property)."},
    {"method": "GET", "path": "/api/export", "description": "The whole knowledge base as RDF/XML (?format=turtle for Turtle)."},
    {"method": "POST", "path": "/api/sparql", "description": "Run a read-only SPARQL query. Prefixes pizza:, owl:, rdf:, rdfs:, xsd: are predefined.",
     "body": {"query": "SELECT ..."}},
    {"method": "POST", "path": "/api/pizzas", "description": "Add a pizza individual.",
     "body": {"name": "MargheritaPizza3", "type": "MargheritaPizza", "calories": 250, "base": "ThinAndCrispyBase (optional)", "label": "(optional)"}},
    {"method": "POST", "path": "/api/toppings", "description": "Add a topping class.",
     "body": {"name": "BasilTopping", "parent": "VegetableTopping", "spiciness": "Hot/Medium/Mild (optional)", "label": "(optional)"}},
    {"method": "POST", "path": "/api/pizza-types", "description": "Add a named pizza type.",
     "body": {"name": "CapricciosaPizza", "toppings": ["MozzarellaTopping", "TomatoTopping", "HamTopping", "MushroomTopping"],
              "closed": True, "comment": "(optional)", "label": "(optional)"}},
    {"method": "DELETE", "path": "/api/pizzas/<name>", "description": "Delete a pizza that was added through the API."},
]


def create_app(ontology_path: str | Path | None = None, store_path: str | Path | None = None) -> Flask:
    ontology_path = ontology_path or os.environ.get("PIZZA_ONTOLOGY", DEFAULT_ONTOLOGY)
    store_path = store_path or os.environ.get("PIZZA_STORE", DEFAULT_STORE)

    app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
    app.json.sort_keys = False
    kb = KnowledgeBase(ontology_path, store_path)
    app.config["KB"] = kb

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def json_body() -> dict:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise InvalidInput("Expected a JSON object in the request body.")
        return data

    def int_arg(name: str) -> int | None:
        value = request.args.get(name)
        if value in (None, ""):
            return None
        try:
            return int(value)
        except ValueError:
            raise InvalidInput(f"{name} must be an integer.") from None

    @app.errorhandler(KBError)
    def handle_kb_error(error: KBError):
        return jsonify(error=str(error)), error.status

    @app.errorhandler(NotImplementedError)
    def handle_not_implemented(error: NotImplementedError):
        return jsonify(error=f"Not implemented yet: {error}"), 501

    @app.errorhandler(404)
    def handle_not_found(error):
        if request.path.startswith("/api"):
            return jsonify(error=f"No endpoint {request.method} {request.path}. See GET /api."), 404
        return error

    @app.errorhandler(405)
    def handle_bad_method(error):
        return jsonify(error=f"Method {request.method} not allowed on {request.path}."), 405

    # ------------------------------------------------------------------ #
    # Frontend
    # ------------------------------------------------------------------ #
    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    # ------------------------------------------------------------------ #
    # Retrieve knowledge
    # ------------------------------------------------------------------ #
    @app.get("/api")
    def api_index():
        return jsonify(endpoints=ENDPOINTS)

    @app.get("/api/schema")
    def get_schema():
        return jsonify(kb.schema())

    @app.get("/api/toppings")
    def get_toppings():
        return jsonify(kb.toppings())

    @app.get("/api/bases")
    def get_bases():
        return jsonify(kb.bases())

    @app.get("/api/spiciness")
    def get_spiciness():
        return jsonify(kb.spiciness_levels())

    @app.get("/api/pizza-types")
    def get_pizza_types():
        return jsonify(kb.pizza_types())

    @app.get("/api/pizzas")
    def get_pizzas():
        return jsonify(kb.pizzas(
            topping=request.args.get("topping") or None,
            min_calories=int_arg("minCalories"),
            max_calories=int_arg("maxCalories"),
            vegetarian=request.args.get("vegetarian", "").lower() in ("1", "true", "yes"),
        ))

    @app.get("/api/pizzas/<name>")
    def get_pizza(name: str):
        return jsonify(kb.pizza(name))

    @app.get("/api/entity/<name>")
    def get_entity(name: str):
        return jsonify(kb.describe(name))

    @app.get("/api/export")
    def export():
        fmt = request.args.get("format", "xml")
        if fmt not in ("xml", "turtle"):
            raise InvalidInput("format must be 'xml' or 'turtle'.")
        mimetype = "application/rdf+xml" if fmt == "xml" else "text/turtle"
        filename = "pizza_knowledge.rdf" if fmt == "xml" else "pizza_knowledge.ttl"
        return Response(kb.export(fmt), mimetype=mimetype,
                        headers={"Content-Disposition": f"attachment; filename={filename}"})

    @app.post("/api/sparql")
    def run_sparql():
        return jsonify(kb.sparql(json_body().get("query")))

    # ------------------------------------------------------------------ #
    # Store knowledge
    # ------------------------------------------------------------------ #
    @app.post("/api/pizzas")
    def post_pizza():
        # TODO (Task 8): read the JSON body with json_body(), call kb.add_pizza(...) and
        # return the new pizza as JSON with status 201 (Created). post_topping() below is
        # an example. Errors raised by the knowledge base (InvalidInput, Conflict, ...) are
        # turned into JSON error responses by handle_kb_error() above.
        data = json_body()
        pizza = kb.add_pizza(
            name=data.get("name"),
            type=data.get("type"),
            calories=data.get("calories"),
            base=data.get("base") or None,
            label=data.get("label") or None,
        )
        return jsonify(pizza), 201

    @app.post("/api/toppings")
    def post_topping():
        data = json_body()
        topping = kb.add_topping(
            name=data.get("name"),
            parent=data.get("parent"),
            spiciness=data.get("spiciness") or None,
            label=data.get("label") or None,
        )
        return jsonify(topping), 201

    @app.post("/api/pizza-types")
    def post_pizza_type():
        # TODO (Task 8): like post_pizza(), but for kb.add_pizza_type(). The body is
        # {"name": ..., "toppings": [...], "closed": true/false, "comment": ...};
        # "closed" defaults to true.
        raise NotImplementedError("Task 8: POST /api/pizza-types")

    @app.delete("/api/pizzas/<name>")
    def delete_pizza(name: str):
        # TODO (Task 10, optional): call kb.delete_pizza(name) and return an empty
        # response with status 204 (No Content).
        raise NotImplementedError("Task 10 (optional): DELETE /api/pizzas/<name>")

    return app


if __name__ == "__main__":
    try:
        application = create_app()
    except OntologyError as error:
        sys.exit(f"\nCannot start the application:\n{error}\n")
    for warning in application.config["KB"].warnings:
        print(f"Warning: {warning}")
    port = int(os.environ.get("PORT", 8000))
    application.run(host="127.0.0.1", port=port, debug=True)
