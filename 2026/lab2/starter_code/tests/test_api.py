"""
Tests for the Pizza knowledge application.

Run from the project folder with:
    python -m pytest -v

These tests do NOT use your own ontology. They use the small test ontology in
tests/test_ontology.ttl (made-up pizzas with the names of the Protégé tutorial),
so the expected results are the same for everyone. Every test starts from that
ontology and an empty store file in a temporary folder, so the tests never touch
the files in data/. tests/test_own_ontology.py checks your own ontology.
"""

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402

ONTOLOGY = ROOT / "tests" / "test_ontology.ttl"


@pytest.fixture
def store(tmp_path):
    return tmp_path / "added_knowledge.ttl"


@pytest.fixture
def client(store):
    app = create_app(ONTOLOGY, store)
    app.testing = True
    return app.test_client()


def names(items):
    return sorted(item["name"] for item in items)


def by_name(items, name):
    return next(item for item in items if item["name"] == name)


ALL_PIZZAS = ["BiancaPizza1", "CapresePizza1", "CapresePizza2", "DiavolaPizza1",
              "OrtolanaPizza1", "TropicalPizza1", "TropicalPizza2"]


# --------------------------------------------------------------------------- #
# Part A: retrieving knowledge
# --------------------------------------------------------------------------- #
def test_toppings(client):
    toppings = client.get("/api/toppings").get_json()
    assert len(toppings) == 16
    mozzarella = by_name(toppings, "MozzarellaTopping")
    assert mozzarella["label"] == "Mozzarella Topping"
    assert mozzarella["parent"] == "CheeseTopping"
    assert mozzarella["category"] == "CheeseTopping"
    assert mozzarella["spiciness"] is None
    jalapeno = by_name(toppings, "JalapenoPepperTopping")
    assert jalapeno["parent"] == "PepperTopping"
    assert jalapeno["category"] == "VegetableTopping"
    assert jalapeno["spiciness"] == "Hot"
    assert by_name(toppings, "SweetPepperTopping")["spiciness"] == "Mild"
    meat = by_name(toppings, "MeatTopping")
    assert meat["parent"] == "PizzaTopping"
    assert meat["category"] == "MeatTopping"


def test_bases_and_spiciness(client):
    assert names(client.get("/api/bases").get_json()) == ["DeepPanBase", "ThinAndCrispyBase"]
    assert names(client.get("/api/spiciness").get_json()) == ["Hot", "Medium", "Mild"]


def test_pizza_types(client):
    types = client.get("/api/pizza-types").get_json()
    # VegetarianPizza and SpicyPizza are defined classes, not named pizza types.
    assert names(types) == ["BiancaPizza", "CapresePizza", "DiavolaPizza", "OrtolanaPizza", "TropicalPizza"]
    caprese = by_name(types, "CapresePizza")
    assert names(caprese["toppings"]) == ["BasilTopping", "MozzarellaTopping", "TomatoTopping"]
    assert caprese["toppings"][0] == {"name": "BasilTopping", "label": "Basil Topping"}
    assert caprese["closed"] is True
    assert caprese["comment"] == "Mozzarella, tomato and basil"
    diavola = by_name(types, "DiavolaPizza")
    assert names(diavola["toppings"]) == ["JalapenoPepperTopping", "MozzarellaTopping",
                                          "SalamiTopping", "TomatoTopping"]
    assert diavola["closed"] is False
    assert diavola["comment"] is None


def test_all_pizzas(client):
    pizzas = client.get("/api/pizzas").get_json()
    assert [p["name"] for p in pizzas] == ALL_PIZZAS          # sorted by name
    caprese1 = by_name(pizzas, "CapresePizza1")
    assert caprese1 == {"name": "CapresePizza1", "label": "Caprese Pizza 1", "type": "CapresePizza",
                        "typeLabel": "Caprese Pizza", "calories": 260}
    assert by_name(pizzas, "CapresePizza2")["calories"] == 310   # stored as xsd:decimal
    assert by_name(pizzas, "TropicalPizza2")["calories"] is None


@pytest.mark.parametrize("topping, expected", [
    ("PineappleTopping", ["TropicalPizza1", "TropicalPizza2"]),
    ("JalapenoPepperTopping", ["DiavolaPizza1"]),
    ("PepperTopping", ["DiavolaPizza1", "OrtolanaPizza1"]),              # subclasses count
    ("MeatTopping", ["DiavolaPizza1", "TropicalPizza1", "TropicalPizza2"]),
    ("GorgonzolaTopping", ["BiancaPizza1"]),
    ("CheeseTopping", ALL_PIZZAS),
    ("OliveTopping", []),
])
def test_filter_by_topping(client, topping, expected):
    assert names(client.get(f"/api/pizzas?topping={topping}").get_json()) == expected


def test_filter_by_calories(client):
    low = client.get("/api/pizzas?maxCalories=400").get_json()
    assert names(low) == ["BiancaPizza1", "CapresePizza1", "CapresePizza2", "TropicalPizza1"]
    high = client.get("/api/pizzas?minCalories=450").get_json()
    assert names(high) == ["DiavolaPizza1", "OrtolanaPizza1"]
    both = client.get("/api/pizzas?minCalories=300&maxCalories=400").get_json()
    assert names(both) == ["BiancaPizza1", "CapresePizza2", "TropicalPizza1"]


def test_filter_vegetarian(client):
    veg = client.get("/api/pizzas?vegetarian=true").get_json()
    assert names(veg) == ["BiancaPizza1", "CapresePizza1", "CapresePizza2", "OrtolanaPizza1"]


def test_filters_combine(client):
    result = client.get("/api/pizzas?vegetarian=true&topping=TomatoTopping&maxCalories=300").get_json()
    assert names(result) == ["CapresePizza1"]


def test_bad_filters(client):
    assert client.get("/api/pizzas?topping=NoSuchTopping").status_code == 400
    assert client.get("/api/pizzas?topping=CapresePizza").status_code == 400
    assert client.get("/api/pizzas?maxCalories=lots").status_code == 400


def test_pizza_details(client):
    response = client.get("/api/pizzas/OrtolanaPizza1")
    assert response.status_code == 200
    ortolana = response.get_json()
    assert ortolana["label"] == "Ortolana Pizza 1"
    assert ortolana["type"] == "OrtolanaPizza"
    assert ortolana["typeLabel"] == "Ortolana Pizza"
    assert ortolana["calories"] == 450
    assert ortolana["base"] == "DeepPanBase"
    assert ortolana["baseLabel"] == "Deep Pan Base"
    assert names(ortolana["toppings"]) == ["MozzarellaTopping", "MushroomTopping",
                                           "SweetPepperTopping", "TomatoTopping"]
    assert by_name(ortolana["toppings"], "SweetPepperTopping")["category"] == "VegetableTopping"
    assert by_name(ortolana["toppings"], "MozzarellaTopping")["category"] == "CheeseTopping"
    assert ortolana["addedByUser"] is False


def test_pizza_details_without_base_or_calories(client):
    tropical = client.get("/api/pizzas/TropicalPizza2").get_json()
    assert tropical["base"] is None
    assert tropical["calories"] is None
    assert names(tropical["toppings"]) == ["HamTopping", "MozzarellaTopping", "PineappleTopping"]


def test_pizza_details_not_found(client):
    assert client.get("/api/pizzas/NoSuchPizza").status_code == 404
    assert client.get("/api/pizzas/MozzarellaTopping").status_code == 404
    assert client.get("/api/pizzas/OrtolanaPizza1Base").status_code == 404


# --------------------------------------------------------------------------- #
# Part B: storing knowledge
# --------------------------------------------------------------------------- #
def test_add_pizza(client):
    response = client.post("/api/pizzas", json={
        "name": "CapresePizza3", "type": "CapresePizza", "calories": 250, "base": "ThinAndCrispyBase"})
    assert response.status_code == 201
    pizza = response.get_json()
    assert pizza["name"] == "CapresePizza3"
    assert pizza["label"] == "Caprese Pizza 3"
    assert pizza["base"] == "ThinAndCrispyBase"
    assert pizza["addedByUser"] is True

    details = client.get("/api/pizzas/CapresePizza3").get_json()
    assert details["calories"] == 250
    assert names(details["toppings"]) == ["BasilTopping", "MozzarellaTopping", "TomatoTopping"]
    assert "CapresePizza3" in names(client.get("/api/pizzas?vegetarian=true").get_json())
    assert "CapresePizza3" in names(client.get("/api/pizzas?maxCalories=250").get_json())


def test_add_pizza_without_base(client):
    response = client.post("/api/pizzas", json={"name": "DiavolaPizza2", "type": "DiavolaPizza",
                                                "calories": "800", "label": "Extra hot Diavola"})
    assert response.status_code == 201
    pizza = client.get("/api/pizzas/DiavolaPizza2").get_json()
    assert pizza["calories"] == 800
    assert pizza["base"] is None
    assert pizza["label"] == "Extra hot Diavola"


@pytest.mark.parametrize("body, status", [
    ({"name": "CapresePizza1", "type": "CapresePizza", "calories": 250}, 409),     # exists
    ({"name": "MyPizza", "type": "NoSuchPizza", "calories": 250}, 400),            # unknown type
    ({"name": "MyPizza", "type": "MozzarellaTopping", "calories": 250}, 400),      # not a pizza type
    ({"name": "MyPizza", "type": "SpicyPizza", "calories": 250}, 400),             # not a NamedPizza
    ({"name": "MyPizza", "type": "CapresePizza", "calories": -5}, 400),            # negative
    ({"name": "MyPizza", "type": "CapresePizza", "calories": "many"}, 400),        # not a number
    ({"name": "MyPizza", "type": "CapresePizza", "calories": True}, 400),          # not a number
    ({"name": "my pizza", "type": "CapresePizza", "calories": 250}, 400),          # bad name
    ({"name": "MyPizza", "type": "CapresePizza", "calories": 250, "base": "TomatoTopping"}, 400),
    ({"type": "CapresePizza", "calories": 250}, 400),                              # missing name
])
def test_add_pizza_invalid(client, body, status):
    assert client.post("/api/pizzas", json=body).status_code == status
    assert len(client.get("/api/pizzas").get_json()) == len(ALL_PIZZAS)   # nothing was added


def test_add_topping(client):
    response = client.post("/api/toppings", json={"name": "ArugulaTopping", "parent": "VegetableTopping"})
    assert response.status_code == 201
    assert response.get_json()["category"] == "VegetableTopping"
    # A new top-level category, and a hot topping in it
    assert client.post("/api/toppings", json={"name": "SpiceTopping", "parent": "PizzaTopping"}).status_code == 201
    response = client.post("/api/toppings", json={
        "name": "ChiliFlakeTopping", "parent": "SpiceTopping", "spiciness": "Hot"})
    assert response.status_code == 201

    toppings = client.get("/api/toppings").get_json()
    assert len(toppings) == 19
    assert by_name(toppings, "ArugulaTopping")["parent"] == "VegetableTopping"
    assert by_name(toppings, "SpiceTopping")["category"] == "SpiceTopping"
    chili = by_name(toppings, "ChiliFlakeTopping")
    assert chili["label"] == "Chili Flake Topping"
    assert chili["category"] == "SpiceTopping"
    assert chili["spiciness"] == "Hot"


def test_add_topping_invalid(client):
    assert client.post("/api/toppings", json={"name": "TomatoTopping", "parent": "VegetableTopping"}).status_code == 409
    assert client.post("/api/toppings", json={"name": "XTopping", "parent": "CapresePizza"}).status_code == 400
    assert client.post("/api/toppings", json={"name": "XTopping", "parent": "SpiceTopping"}).status_code == 400
    assert client.post("/api/toppings", json={"name": "XTopping", "parent": "VegetableTopping",
                                              "spiciness": "Volcanic"}).status_code == 400
    assert len(client.get("/api/toppings").get_json()) == 16


def test_add_pizza_type_and_use_it(client):
    client.post("/api/toppings", json={"name": "ArugulaTopping", "parent": "VegetableTopping"})
    response = client.post("/api/pizza-types", json={
        "name": "RucolaPizza",
        "toppings": ["MozzarellaTopping", "TomatoTopping", "ArugulaTopping"],
        "closed": True,
        "comment": "Mozzarella, tomato and rocket",
    })
    assert response.status_code == 201
    rucola = by_name(client.get("/api/pizza-types").get_json(), "RucolaPizza")
    assert names(rucola["toppings"]) == ["ArugulaTopping", "MozzarellaTopping", "TomatoTopping"]
    assert rucola["closed"] is True
    assert rucola["comment"] == "Mozzarella, tomato and rocket"

    assert client.post("/api/pizzas", json={
        "name": "RucolaPizza1", "type": "RucolaPizza", "calories": 280}).status_code == 201
    assert "RucolaPizza1" in names(client.get("/api/pizzas?topping=ArugulaTopping").get_json())
    assert "RucolaPizza1" in names(client.get("/api/pizzas?vegetarian=true").get_json())
    assert "RucolaPizza1" not in names(client.get("/api/pizzas?topping=MeatTopping").get_json())


def test_add_open_pizza_type(client):
    response = client.post("/api/pizza-types", json={
        "name": "SalamiPizza", "toppings": ["MozzarellaTopping", "SalamiTopping"], "closed": False})
    assert response.status_code == 201
    assert response.get_json()["closed"] is False
    statements = [s["object"] for s in client.get("/api/entity/SalamiPizza").get_json()["statements"]]
    assert not any(" only " in str(s) for s in statements)


def test_add_pizza_type_writes_owl_restrictions(client):
    client.post("/api/pizza-types", json={
        "name": "SalamiPizza", "toppings": ["MozzarellaTopping", "SalamiTopping"], "closed": True})
    statements = [s["object"] for s in client.get("/api/entity/SalamiPizza").get_json()["statements"]
                  if s["predicate"] == "rdfs:subClassOf"]
    assert "pizza:NamedPizza" in statements
    assert "pizza:hasTopping some pizza:SalamiTopping" in statements
    assert "pizza:hasTopping some pizza:MozzarellaTopping" in statements
    closure = [s for s in statements if s.startswith("pizza:hasTopping only (")]
    assert len(closure) == 1
    assert "pizza:SalamiTopping" in closure[0] and "pizza:MozzarellaTopping" in closure[0]


def test_add_pizza_type_invalid(client):
    assert client.post("/api/pizza-types", json={"name": "EmptyPizza", "toppings": []}).status_code == 400
    assert client.post("/api/pizza-types", json={"name": "BadPizza", "toppings": ["Rocks"]}).status_code == 400
    assert client.post("/api/pizza-types", json={"name": "BadPizza", "toppings": "TomatoTopping"}).status_code == 400
    assert client.post("/api/pizza-types", json={
        "name": "BadPizza", "toppings": ["TomatoTopping", "TomatoTopping"]}).status_code == 400
    assert client.post("/api/pizza-types", json={"name": "CapresePizza", "toppings": ["TomatoTopping"]}).status_code == 409
    assert len(client.get("/api/pizza-types").get_json()) == 5


def test_knowledge_is_persisted(store):
    first = create_app(ONTOLOGY, store).test_client()
    first.post("/api/toppings", json={"name": "ArugulaTopping", "parent": "VegetableTopping"})
    first.post("/api/pizza-types", json={"name": "RucolaPizza", "toppings": ["ArugulaTopping", "TomatoTopping"]})
    first.post("/api/pizzas", json={"name": "RucolaPizza1", "type": "RucolaPizza", "calories": 300,
                                    "base": "DeepPanBase"})
    assert store.exists()

    # A fresh app (e.g. after a restart) loads the stored knowledge again.
    second = create_app(ONTOLOGY, store).test_client()
    pizza = second.get("/api/pizzas/RucolaPizza1").get_json()
    assert pizza["base"] == "DeepPanBase"
    assert names(pizza["toppings"]) == ["ArugulaTopping", "TomatoTopping"]


def test_original_ontology_is_not_modified(client):
    before = hashlib.sha256(ONTOLOGY.read_bytes()).hexdigest()
    client.post("/api/pizzas", json={"name": "CapresePizza3", "type": "CapresePizza", "calories": 400})
    assert hashlib.sha256(ONTOLOGY.read_bytes()).hexdigest() == before


def test_delete_pizza(client):
    client.post("/api/pizzas", json={"name": "CapresePizza3", "type": "CapresePizza", "calories": 400,
                                     "base": "DeepPanBase"})
    assert client.delete("/api/pizzas/CapresePizza3").status_code == 204
    assert client.get("/api/pizzas/CapresePizza3").status_code == 404
    assert client.get("/api/entity/CapresePizza3Base").status_code == 404
    assert client.delete("/api/pizzas/CapresePizza1").status_code == 403   # part of the ontology
    assert client.delete("/api/pizzas/NoSuchPizza").status_code == 404


# --------------------------------------------------------------------------- #
# Generic access (given, used again in Lab 4)
# --------------------------------------------------------------------------- #
def test_api_index(client):
    endpoints = client.get("/api").get_json()["endpoints"]
    routes = {(e["method"], e["path"]) for e in endpoints}
    assert ("GET", "/api/pizzas") in routes
    assert ("POST", "/api/pizzas") in routes
    assert all(e.get("description") for e in endpoints)


def test_entity(client):
    entity = client.get("/api/entity/CapresePizza").get_json()
    objects = [s["object"] for s in entity["statements"]]
    assert "pizza:hasTopping some pizza:MozzarellaTopping" in objects
    assert "pizza:hasTopping only (pizza:MozzarellaTopping or pizza:TomatoTopping or pizza:BasilTopping)" in objects
    assert {"subject": "pizza:CapresePizza1", "predicate": "rdf:type"} in entity["referencedBy"]
    assert client.get("/api/entity/NoSuchThing").status_code == 404


def test_sparql_select(client):
    result = client.post("/api/sparql", json={"query": """
        SELECT (COUNT(?p) AS ?n) WHERE { ?p pizza:hasCaloricContent ?c }"""}).get_json()
    assert result["type"] == "SELECT"
    assert result["rows"] == [{"n": 6}]


def test_sparql_ask(client):
    result = client.post("/api/sparql", json={"query": "ASK { pizza:Hot pizza:isSpicierThan+ pizza:Mild }"})
    assert result.get_json() == {"type": "ASK", "boolean": True}


def test_sparql_is_read_only(client):
    response = client.post("/api/sparql", json={"query": "INSERT DATA { pizza:Evil a pizza:Pizza }"})
    assert response.status_code == 400
    assert client.get("/api/entity/Evil").status_code == 404
    assert client.post("/api/sparql", json={"query": "SELEKT nonsense"}).status_code == 400


def test_schema_and_export(client):
    schema = client.get("/api/schema").get_json()
    assert schema["namespace"] == "http://example.org/lab2/test-pizza#"
    assert "pizza:Pizza" in schema["classes"]
    assert any(p["name"] == "pizza:hasTopping" for p in schema["objectProperties"])
    assert schema["warnings"] == []
    response = client.get("/api/export")
    assert response.status_code == 200
    assert b"CapresePizza1" in response.data


def test_unknown_api_route_returns_json(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert "error" in response.get_json()
