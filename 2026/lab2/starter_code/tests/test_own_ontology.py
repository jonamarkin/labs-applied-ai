"""
Checks that the application works with YOUR ontology from Part 1.

Save your ontology as data/pizza_tutorial.rdf (in Protégé: File > Save as... >
RDF/XML Syntax). These tests are skipped until that file exists. Your ontology
differs from everybody else's, so the tests do not check exact answers; they check
that the answers of the different endpoints are consistent with each other.
Most of them need Tasks 1-4.
"""

import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from kb import KnowledgeBase  # noqa: E402

OWN_ONTOLOGY = ROOT / "data" / "pizza_tutorial.rdf"

pytestmark = pytest.mark.skipif(
    not OWN_ONTOLOGY.exists(),
    reason="data/pizza_tutorial.rdf not found: save your ontology from Part 1 there",
)


@pytest.fixture
def client(tmp_path):
    # Added knowledge goes to a temporary file, so data/added_knowledge.ttl is not used.
    app = create_app(OWN_ONTOLOGY, tmp_path / "added_knowledge.ttl")
    app.testing = True
    return app.test_client()


@pytest.fixture
def pizzas(client):
    pizzas = client.get("/api/pizzas").get_json()
    assert pizzas, "No pizza individuals found. Create some in Protégé, e.g. MargheritaPizza1."
    return pizzas


@pytest.fixture
def details(client, pizzas):
    result = {}
    for pizza in pizzas:
        response = client.get(f"/api/pizzas/{pizza['name']}")
        assert response.status_code == 200, f"GET /api/pizzas/{pizza['name']} failed"
        result[pizza["name"]] = response.get_json()
    return result


def test_own_ontology_loads(tmp_path):
    kb = KnowledgeBase(OWN_ONTOLOGY, tmp_path / "added_knowledge.ttl")  # explains what is wrong
    for warning in kb.warnings:
        warnings.warn(warning)


def test_own_ontology_toppings(client):
    toppings = client.get("/api/toppings").get_json()
    assert toppings, "No subclasses of PizzaTopping found."
    assert all(t["category"] for t in toppings)


def test_own_ontology_pizza_types(client):
    types = client.get("/api/pizza-types").get_json()
    assert types, "No subclasses of NamedPizza found."
    assert any(t["toppings"] for t in types), \
        "No pizza type has a topping (hasTopping some ...) restriction."


def test_own_ontology_pizza_details(pizzas, details):
    for pizza in pizzas:
        assert details[pizza["name"]]["type"] == pizza["type"]
        assert details[pizza["name"]]["calories"] == pizza["calories"]


def test_own_ontology_topping_filter_matches_details(client, details):
    categories = {t["category"] for d in details.values() for t in d["toppings"] if t["category"]}
    for category in categories:
        found = {p["name"] for p in client.get(f"/api/pizzas?topping={category}").get_json()}
        expected = {name for name, d in details.items()
                    if any(t["category"] == category for t in d["toppings"])}
        assert found == expected, f"?topping={category}"


def test_own_ontology_vegetarian_filter_matches_details(client, details):
    found = {p["name"] for p in client.get("/api/pizzas?vegetarian=true").get_json()}
    expected = {name for name, d in details.items()
                if all(t["category"] in ("CheeseTopping", "VegetableTopping") for t in d["toppings"])}
    assert found == expected


def test_own_ontology_calorie_filter(client, pizzas):
    found = {p["name"] for p in client.get("/api/pizzas?maxCalories=400").get_json()}
    expected = {p["name"] for p in pizzas if p["calories"] is not None and p["calories"] <= 400}
    assert found == expected
