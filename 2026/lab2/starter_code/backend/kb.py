"""
Knowledge-base layer of the Pizza knowledge application (starter code).

All knowledge lives in an rdflib ``Graph``. The graph is the union of

* the ontology you built in Protégé in Part 1 (``data/pizza_tutorial.rdf``),
  which is never modified, and
* the knowledge added through the API, which is kept in a second graph
  (``self.added``) and saved as Turtle to ``data/added_knowledge.ttl``.

Retrieval is done with SPARQL. Storing is done by building new triples and
adding them to both graphs.
"""

from __future__ import annotations

import re
import threading
from decimal import Decimal
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

# Local names of new entities must look like the ones in the ontology,
# e.g. "MargheritaPizza3" or "BasilTopping".
NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")

MAX_SPARQL_ROWS = 1000


# --------------------------------------------------------------------------- #
# Errors. The Flask app turns these into JSON error responses.
# --------------------------------------------------------------------------- #
class KBError(Exception):
    status = 400


class InvalidInput(KBError):
    status = 400


class Forbidden(KBError):
    status = 403


class NotFound(KBError):
    status = 404


class Conflict(KBError):
    status = 409


class OntologyError(RuntimeError):
    """The ontology file is missing or cannot be used by the application."""


# Names from the Protégé pizza tutorial that the application relies on.
REQUIRED_VOCABULARY = {
    "Pizza": OWL.Class,
    "NamedPizza": OWL.Class,
    "PizzaTopping": OWL.Class,
    "hasTopping": OWL.ObjectProperty,
}
# Only some features need these; the application starts without them.
RECOMMENDED_VOCABULARY = {
    "PizzaBase": OWL.Class,
    "CheeseTopping": OWL.Class,
    "VegetableTopping": OWL.Class,
    "Spiciness": OWL.Class,
    "hasBase": OWL.ObjectProperty,
    "hasSpiciness": OWL.ObjectProperty,
    "hasCaloricContent": OWL.DatatypeProperty,
}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def split_camel(name: str) -> str:
    """'AmericanaHotPizza1' -> 'Americana Hot Pizza 1'."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=[0-9])",
                  " ", name).replace("_", " ")


def to_python(literal: Literal):
    """Convert an rdflib Literal into a JSON-friendly Python value."""
    value = literal.toPython()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(literal)


class KnowledgeBase:
    def __init__(self, ontology_path: str | Path, store_path: str | Path):
        self.ontology_path = Path(ontology_path)
        self.store_path = Path(store_path)
        self.lock = threading.RLock()

        self.graph = Graph()   # everything: ontology + added knowledge
        self.added = Graph()   # only knowledge added through the API
        self._load_ontology()

        self.ns = Namespace(self._detect_namespace())
        self.prefixes = {"pizza": self.ns, "owl": OWL, "rdf": RDF, "rdfs": RDFS, "xsd": XSD}
        for g in (self.graph, self.added):
            for prefix, namespace in self.prefixes.items():
                g.bind(prefix, namespace, override=True, replace=True)
        self.warnings = self._check_vocabulary()

        if self.store_path.exists():
            self.added.parse(self.store_path, format="turtle")
            self.graph += self.added

    # ------------------------------------------------------------------ #
    # Helpers (given)
    # ------------------------------------------------------------------ #
    def _load_ontology(self) -> None:
        """Parse the ontology from Part 1, with helpful errors."""
        if not self.ontology_path.exists():
            raise OntologyError(
                f"Ontology file not found: {self.ontology_path}\n"
                "Save the pizza ontology you built in Part 1 there: in Protégé, use "
                "File > Save as..., choose 'RDF/XML Syntax' and name the file pizza_tutorial.rdf."
            )
        try:
            self.graph.parse(self.ontology_path)
        except Exception as error:
            raise OntologyError(
                f"Could not read {self.ontology_path}: {error}\n"
                "Save the ontology in Protégé with 'RDF/XML Syntax' (or Turtle), "
                "not OWL/XML, Manchester or functional syntax."
            ) from None

    def _detect_namespace(self) -> str:
        """The namespace of the pizza ontology, e.g.
        'http://www.semanticweb.org/<user>/ontologies/2025/10/PizzaTutorial#'.

        Protégé gives every ontology its own namespace, so it is read from the
        file (from the IRI of the class Pizza) instead of being hard-coded."""
        for cls in sorted(self.graph.subjects(RDF.type, OWL.Class), key=str):
            iri = str(cls)
            if isinstance(cls, URIRef) and iri.endswith(("#Pizza", "/Pizza")):
                return iri[: -len("Pizza")]
        raise OntologyError(
            f"No class called 'Pizza' found in {self.ontology_path}. Is this the pizza "
            "ontology from Part 1, saved in Protégé with 'RDF/XML Syntax'?"
        )

    def _check_vocabulary(self) -> list[str]:
        """Check that the ontology uses the names from the Protégé pizza tutorial.

        Raises OntologyError if something the application cannot work without is
        missing, and returns warnings for things only some features need."""
        def missing(vocabulary):
            return [f"{name} ({self.short(kind)})" for name, kind in vocabulary.items()
                    if (self.iri(name), RDF.type, kind) not in self.graph]

        required = missing(REQUIRED_VOCABULARY)
        if required:
            raise OntologyError(
                f"{self.ontology_path} does not define: {', '.join(required)}.\n"
                "The application expects the class and property names of the Protégé pizza tutorial."
            )
        warnings = [f"The ontology does not define {item}; some features will not work."
                    for item in missing(RECOMMENDED_VOCABULARY)]
        if not self.ask("ASK { ?pizza a ?type . ?type rdfs:subClassOf+ pizza:NamedPizza }"):
            warnings.append("The ontology has no pizza individuals (e.g. MargheritaPizza1) yet.")
        return warnings

    def iri(self, name: str) -> URIRef:
        """Local name -> IRI in the pizza namespace."""
        return self.ns[name]

    def local(self, term) -> str | None:
        """IRI in the pizza namespace -> local name ('MargheritaPizza')."""
        if term is None:
            return None
        text = str(term)
        return text[len(str(self.ns)):] if text.startswith(str(self.ns)) else text

    def label(self, term) -> str | None:
        """rdfs:label of a term, or a readable version of its local name."""
        if term is None:
            return None
        label = self.graph.value(term, RDFS.label)
        return str(label) if label is not None else split_camel(self.local(term))

    def short(self, term) -> str:
        """Prefixed name, e.g. 'pizza:MargheritaPizza' or 'rdfs:subClassOf'."""
        return term.n3(self.graph.namespace_manager)

    def query(self, sparql: str, **bindings):
        """Run a SPARQL query with the standard prefixes.

        Keyword arguments are bound to SPARQL variables, so user input never
        has to be pasted into the query string:
            kb.query("SELECT ?x WHERE { ?x a ?type }", type=kb.iri("MargheritaPizza"))
        """
        return self.graph.query(sparql, initNs=self.prefixes, initBindings=bindings)

    def ask(self, sparql: str, **bindings) -> bool:
        return bool(self.query(sparql, **bindings).askAnswer)

    def exists(self, name: str) -> bool:
        """Is the local name already used anywhere in the graph?"""
        term = self.iri(name)
        return (term, None, None) in self.graph or (None, None, term) in self.graph

    def is_subclass_of(self, cls: URIRef, ancestor: URIRef, strict: bool = True) -> bool:
        path = "rdfs:subClassOf+" if strict else "rdfs:subClassOf*"
        return self.ask(f"ASK {{ ?cls {path} ?ancestor }}", cls=cls, ancestor=ancestor)

    def _check_new_name(self, name, what: str) -> URIRef:
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise InvalidInput(
                f"Invalid {what} name {name!r}: use letters and digits only, "
                "starting with a capital letter (e.g. 'MargheritaPizza3')."
            )
        if self.exists(name):
            raise Conflict(f"{name!r} already exists in the knowledge base.")
        return self.iri(name)

    def _check_class(self, name, ancestor: str, what: str) -> URIRef:
        """Check that `name` is a class below `ancestor` (e.g. a PizzaTopping)."""
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise InvalidInput(f"Invalid {what}: {name!r}.")
        cls = self.iri(name)
        if not self.is_subclass_of(cls, self.iri(ancestor)):
            raise InvalidInput(f"Unknown {what} {name!r}: it is not a subclass of {ancestor}.")
        return cls

    def _commit(self, new: Graph) -> None:
        """Add new triples to the knowledge base and save them to disk."""
        with self.lock:
            self.graph += new
            self.added += new
            self.save()

    def save(self) -> None:
        """Write the added knowledge to the store file (Turtle)."""
        with self.lock:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.store_path.with_suffix(self.store_path.suffix + ".tmp")
            self.added.serialize(destination=tmp, format="turtle")
            tmp.replace(self.store_path)

    # ------------------------------------------------------------------ #
    # Part A: retrieving knowledge (bases() and spiciness_levels() are given as examples)
    # ------------------------------------------------------------------ #
    def toppings(self) -> list[dict]:
        """TODO (Task 1): all topping classes below pizza:PizzaTopping."""
        rows = self.query("""
            SELECT DISTINCT ?topping ?parent ?category ?spiciness WHERE {
                ?topping rdfs:subClassOf+ pizza:PizzaTopping ;
                         rdfs:subClassOf ?parent ;
                         rdfs:subClassOf* ?category .
                ?category rdfs:subClassOf pizza:PizzaTopping .
                FILTER(isIRI(?parent))
                OPTIONAL {
                    ?topping rdfs:subClassOf ?r .
                    ?r owl:onProperty pizza:hasSpiciness ;
                       owl:hasValue ?spiciness .
                }
            }
        """)
        return sorted(
            ({
                "name": self.local(r.topping),
                "label": self.label(r.topping),
                "parent": self.local(r.parent),
                "category": self.local(r.category),
                "spiciness": self.local(r.spiciness),
            } for r in rows),
            key=lambda t: t["name"],
        )

    def bases(self) -> list[dict]:
        rows = self.query("SELECT DISTINCT ?base WHERE { ?base rdfs:subClassOf+ pizza:PizzaBase }")
        return sorted(({"name": self.local(r.base), "label": self.label(r.base)} for r in rows),
                      key=lambda b: b["name"])

    def spiciness_levels(self) -> list[dict]:
        rows = self.query("""
            SELECT DISTINCT ?level WHERE {
                { pizza:Spiciness owl:equivalentClass/owl:oneOf/rdf:rest*/rdf:first ?level }
                UNION
                { ?level a pizza:Spiciness }
            }
        """)
        return sorted(({"name": self.local(r.level), "label": self.label(r.level)} for r in rows),
                      key=lambda s: s["name"])

    def pizza_types(self) -> list[dict]:
        """TODO (Task 2): all named pizza types (classes below pizza:NamedPizza).

        Return a list sorted by name, e.g. for CapresePizza in tests/test_ontology.ttl:
            {"name": "CapresePizza", "label": "Caprese Pizza",
             "comment": "Mozzarella, tomato and basil",   # rdfs:comment, or None
             "closed": True,   # True if the type has a closure axiom (owl:allValuesFrom on hasTopping)
             "toppings": [{"name": "BasilTopping", "label": "Basil Topping"},
                          {"name": "MozzarellaTopping", "label": "Mozzarella Topping"},
                          {"name": "TomatoTopping", "label": "Tomato Topping"}]}   # sorted by name

        The toppings are not plain triples. Each topping is an OWL restriction (a blank node):
            pizza:MargheritaPizza rdfs:subClassOf
                [ a owl:Restriction ; owl:onProperty pizza:hasTopping ;
                  owl:someValuesFrom pizza:TomatoTopping ] .
        Tip: one SPARQL row per (type, topping) is fine; group the rows in Python.
        """
        rows = self.query("""
            SELECT DISTINCT ?type ?comment ?topping WHERE {
                ?type rdfs:subClassOf+ pizza:NamedPizza .
                OPTIONAL { ?type rdfs:comment ?comment }
                OPTIONAL {
                    ?type rdfs:subClassOf ?r .
                    ?r owl:onProperty pizza:hasTopping ;
                       owl:someValuesFrom ?topping .
                    FILTER(isIRI(?topping))
                }
            }
        """)
        types: dict[str, dict] = {}
        for r in rows:
            name = self.local(r.type)
            if name not in types:
                closed = self.ask("""
                    ASK {
                        ?type rdfs:subClassOf ?r .
                        ?r owl:onProperty pizza:hasTopping ;
                           owl:allValuesFrom ?u .
                    }
                """, type=r.type)
                types[name] = {
                    "name": name,
                    "label": self.label(r.type),
                    "comment": str(r.comment) if r.comment is not None else None,
                    "closed": closed,
                    "toppings": [],
                }
            if r.topping is not None:
                t_name = self.local(r.topping)
                if not any(t["name"] == t_name for t in types[name]["toppings"]):
                    types[name]["toppings"].append({
                        "name": t_name,
                        "label": self.label(r.topping),
                    })
        for entry in types.values():
            entry["toppings"].sort(key=lambda t: t["name"])
        return sorted(types.values(), key=lambda t: t["name"])

    def pizzas(self, topping: str | None = None, min_calories: int | None = None,
               max_calories: int | None = None, vegetarian: bool = False) -> list[dict]:
        """TODO (Task 3): pizza individuals, optionally filtered.

        Return a list sorted by name:
            {"name": "MargheritaPizza1", "label": "Margherita Pizza 1",
             "type": "MargheritaPizza", "typeLabel": "Margherita Pizza", "calories": 263}

        Filters (all optional, they can be combined):
          topping      -- only pizzas whose type has this topping or a topping below it:
                          "MeatTopping" must also match pizzas with PepperoniTopping.
                          Raise InvalidInput for an unknown topping (self._check_class helps).
          min_calories, max_calories -- inclusive bounds on pizza:hasCaloricContent
          vegetarian   -- only pizzas where *every* topping is below CheeseTopping or
                          VegetableTopping (think FILTER NOT EXISTS)

        Hints:
          * Build the query from a base pattern plus one FILTER per active filter.
          * Never paste user input into a query string. Bind it to a variable instead:
                self.query("... ?t rdfs:subClassOf* ?wanted ...", wanted=self.iri(topping))
            (Integers that you have converted with int() can be formatted into the query.)
          * to_python() turns the calorie literal into a number.
        """
        bindings = {}
        extra_clauses = []

        if topping is not None:
            bindings["wanted"] = self._check_class(topping, "PizzaTopping", "topping")
            extra_clauses.append("""
                ?type rdfs:subClassOf ?r_top .
                ?r_top owl:onProperty pizza:hasTopping ;
                       owl:someValuesFrom ?t .
                ?t rdfs:subClassOf* ?wanted .
            """)

        if min_calories is not None:
            extra_clauses.append(f"FILTER(BOUND(?calories) && ?calories >= {int(min_calories)})")

        if max_calories is not None:
            extra_clauses.append(f"FILTER(BOUND(?calories) && ?calories <= {int(max_calories)})")

        if vegetarian:
            extra_clauses.append("""
                FILTER NOT EXISTS {
                    ?type rdfs:subClassOf ?r_veg .
                    ?r_veg owl:onProperty pizza:hasTopping ;
                           owl:someValuesFrom ?t_veg .
                    FILTER(isIRI(?t_veg))
                    FILTER NOT EXISTS {
                        VALUES ?ok { pizza:CheeseTopping pizza:VegetableTopping }
                        ?t_veg rdfs:subClassOf* ?ok .
                    }
                }
            """)

        where_extra = "\n".join(extra_clauses)
        rows = self.query(f"""
            SELECT DISTINCT ?pizza ?type ?calories WHERE {{
                ?pizza a ?type .
                ?type rdfs:subClassOf+ pizza:NamedPizza .
                OPTIONAL {{ ?pizza pizza:hasCaloricContent ?calories }}
                {where_extra}
            }}
        """, **bindings)

        return sorted(
            ({
                "name": self.local(r.pizza),
                "label": self.label(r.pizza),
                "type": self.local(r.type),
                "typeLabel": self.label(r.type),
                "calories": to_python(r.calories) if r.calories is not None else None,
            } for r in rows),
            key=lambda p: p["name"],
        )

    def pizza(self, name: str) -> dict:
        """TODO (Task 4): everything we know about one pizza individual.

        Return
            {"name": "MargheritaPizza1", "label": "Margherita Pizza 1",
             "type": "MargheritaPizza", "typeLabel": "Margherita Pizza",
             "calories": 263,                     # None if unknown
             "base": None, "baseLabel": None,     # e.g. "ThinAndCrispyBase", "Thin And Crispy Base"
             "toppings": [{"name": "MozzarellaTopping", "label": "Mozzarella Topping",
                           "category": "CheeseTopping"},
                          {"name": "TomatoTopping", "label": "Tomato Topping",
                           "category": "VegetableTopping"}],               # sorted by name
             "addedByUser": False}                # True if the pizza is in self.added

        Raise NotFound if `name` is not a pizza individual.
        The base of a pizza is an individual (see add_pizza); report the class of that individual.
        """
        pizza_iri = self.iri(name)
        rows = list(self.query("""
            SELECT DISTINCT ?type ?calories ?baseClass ?topping ?category WHERE {
                ?pizza a ?type .
                ?type rdfs:subClassOf+ pizza:NamedPizza .
                OPTIONAL { ?pizza pizza:hasCaloricContent ?calories }
                OPTIONAL {
                    ?pizza pizza:hasBase ?baseInd .
                    ?baseInd a ?baseClass .
                    ?baseClass rdfs:subClassOf+ pizza:PizzaBase .
                }
                OPTIONAL {
                    ?type rdfs:subClassOf ?r .
                    ?r owl:onProperty pizza:hasTopping ;
                       owl:someValuesFrom ?topping .
                    ?topping rdfs:subClassOf* ?category .
                    ?category rdfs:subClassOf pizza:PizzaTopping .
                }
            }
        """, pizza=pizza_iri))

        if not rows:
            raise NotFound(f"No pizza individual called {name!r}.")

        first = rows[0]
        toppings_by_name: dict[str, dict] = {}
        for r in rows:
            if r.topping is not None:
                t_name = self.local(r.topping)
                toppings_by_name[t_name] = {
                    "name": t_name,
                    "label": self.label(r.topping),
                    "category": self.local(r.category),
                }

        return {
            "name": name,
            "label": self.label(pizza_iri),
            "type": self.local(first.type),
            "typeLabel": self.label(first.type),
            "calories": to_python(first.calories) if first.calories is not None else None,
            "base": self.local(first.baseClass) if first.baseClass is not None else None,
            "baseLabel": self.label(first.baseClass) if first.baseClass is not None else None,
            "toppings": sorted(toppings_by_name.values(), key=lambda t: t["name"]),
            "addedByUser": (pizza_iri, None, None) in self.added,
        }

    # ------------------------------------------------------------------ #
    # Part B: storing knowledge
    # ------------------------------------------------------------------ #
    def add_pizza(self, name, type, calories, base=None, label=None) -> dict:
        """TODO (Task 5): add a pizza individual and return self.pizza(name).

        add_pizza("MargheritaPizza3", "MargheritaPizza", 250, base="ThinAndCrispyBase")
        must store

            pizza:MargheritaPizza3 a owl:NamedIndividual, pizza:MargheritaPizza ;
                rdfs:label "Margherita Pizza 3" ;
                pizza:hasCaloricContent "250"^^xsd:integer ;
                pizza:hasBase pizza:MargheritaPizza3Base .
            pizza:MargheritaPizza3Base a owl:NamedIndividual, pizza:ThinAndCrispyBase .

        Validation (raise InvalidInput / Conflict, nothing may be stored on failure):
          * name: valid and not used before        -> self._check_new_name()
          * type: a class below pizza:NamedPizza   -> self._check_class()
          * calories: a whole number >= 0 (not a bool; the string "250" is accepted)
          * base (optional): a class below pizza:PizzaBase
          * label (optional): defaults to split_camel(name)

        Put the new triples in a fresh Graph() and pass it to self._commit(),
        which adds them to the knowledge base and saves them to disk.
        """
        raise NotImplementedError("Task 5: KnowledgeBase.add_pizza()")

    def add_topping(self, name, parent, spiciness=None, label=None) -> dict:
        """TODO (Task 6): add a topping class and return its entry from self.toppings().

        add_topping("HabaneroPepperTopping", "VegetableTopping", spiciness="Hot") must store

            pizza:HabaneroPepperTopping a owl:Class ;
                rdfs:label "Habanero Pepper Topping" ;
                rdfs:subClassOf pizza:VegetableTopping ,
                    [ a owl:Restriction ; owl:onProperty pizza:hasSpiciness ; owl:hasValue pizza:Hot ] .

        Validation: a valid new name; parent is PizzaTopping itself or a class below it;
        spiciness (optional) is one of self.spiciness_levels().
        A restriction is a blank node: BNode().
        """
        raise NotImplementedError("Task 6: KnowledgeBase.add_topping()")

    def add_pizza_type(self, name, toppings, closed=True, comment=None, label=None) -> dict:
        """TODO (Task 7): add a named pizza type and return its entry from self.pizza_types().

        add_pizza_type("OlivaPizza", ["MozzarellaTopping", "TomatoTopping", "OliveTopping"],
                       closed=True, comment="Mozzarella, tomato and olives")
        must store the same pattern that Protégé wrote for MargheritaPizza:

            pizza:OlivaPizza a owl:Class ;
                rdfs:label "Oliva Pizza" ;
                rdfs:comment "Mozzarella, tomato and olives" ;
                rdfs:subClassOf pizza:NamedPizza ,
                    [ a owl:Restriction ; owl:onProperty pizza:hasTopping ;
                      owl:someValuesFrom pizza:MozzarellaTopping ] ,
                    ...one such restriction per topping... ,
                    # the closure axiom, only if closed is True:
                    [ a owl:Restriction ; owl:onProperty pizza:hasTopping ;
                      owl:allValuesFrom [ a owl:Class ;
                          owl:unionOf ( pizza:MozzarellaTopping pizza:TomatoTopping pizza:OliveTopping ) ] ] .

        Validation: a valid new name; toppings is a non-empty list without duplicates
        and every element is a class below pizza:PizzaTopping.
        Hint: Collection(graph, BNode(), [a, b, c]) builds the RDF list ( a b c ) in graph.
        """
        raise NotImplementedError("Task 7: KnowledgeBase.add_pizza_type()")

    def delete_pizza(self, name: str) -> None:
        """TODO (Task 10, optional): delete a pizza that was added through the API.

        * Raise NotFound if there is no such pizza, and Forbidden if the pizza is part of
          the original ontology (i.e. it is not in self.added).
        * Remove every triple with the pizza as subject or object from both self.graph and
          self.added, and do the same for its base individual. Then call self.save().
        """
        raise NotImplementedError("Task 10 (optional): KnowledgeBase.delete_pizza()")

    # ------------------------------------------------------------------ #
    # Generic access (given): used by the SPARQL console and, in Lab 4,
    # by an LLM that retrieves knowledge through this API.
    # ------------------------------------------------------------------ #
    def render(self, node) -> str | int | float | bool:
        """Human/LLM-readable form of a term. Blank-node class expressions are
        written in Manchester-like syntax, e.g. 'pizza:hasTopping some pizza:TomatoTopping'."""
        g = self.graph
        if isinstance(node, Literal):
            return to_python(node)
        if isinstance(node, URIRef):
            return self.short(node)

        def items(lst):
            return [self.render(x) for x in Collection(g, lst)]

        prop = g.value(node, OWL.onProperty)
        if prop is not None:
            p = self.render(prop)
            if (value := g.value(node, OWL.someValuesFrom)) is not None:
                return f"{p} some {self.render(value)}"
            if (value := g.value(node, OWL.allValuesFrom)) is not None:
                return f"{p} only {self.render(value)}"
            if (value := g.value(node, OWL.hasValue)) is not None:
                return f"{p} value {self.render(value)}"
            for card, word in ((OWL.minQualifiedCardinality, "min"), (OWL.maxQualifiedCardinality, "max"),
                               (OWL.qualifiedCardinality, "exactly"), (OWL.minCardinality, "min"),
                               (OWL.maxCardinality, "max"), (OWL.cardinality, "exactly")):
                if (n := g.value(node, card)) is not None:
                    on_class = g.value(node, OWL.onClass)
                    suffix = f" {self.render(on_class)}" if on_class is not None else ""
                    return f"{p} {word} {n}{suffix}"
        if (lst := g.value(node, OWL.unionOf)) is not None:
            return "(" + " or ".join(map(str, items(lst))) + ")"
        if (lst := g.value(node, OWL.intersectionOf)) is not None:
            return "(" + " and ".join(map(str, items(lst))) + ")"
        if (lst := g.value(node, OWL.oneOf)) is not None:
            return "{" + ", ".join(map(str, items(lst))) + "}"
        if (datatype := g.value(node, OWL.onDatatype)) is not None:
            facets = []
            for facet in Collection(g, g.value(node, OWL.withRestrictions)):
                for p, o in g.predicate_objects(facet):
                    symbol = {XSD.minInclusive: ">=", XSD.maxInclusive: "<=",
                              XSD.minExclusive: ">", XSD.maxExclusive: "<"}.get(p, self.short(p))
                    facets.append(f"{symbol} {o}")
            return f"{self.render(datatype)}[{', '.join(facets)}]"
        return f"_:{node}"

    def describe(self, name: str) -> dict:
        """All statements about an entity (outgoing and incoming)."""
        term = self.iri(name)
        if not self.exists(name):
            raise NotFound(f"Nothing called {name!r} in the knowledge base.")
        return {
            "name": name,
            "iri": str(term),
            "label": self.label(term),
            "statements": [
                {"predicate": self.short(p), "object": self.render(o)}
                for p, o in sorted(self.graph.predicate_objects(term), key=lambda po: (str(po[0]), str(po[1])))
            ],
            "referencedBy": [
                {"subject": self.render(s), "predicate": self.short(p)}
                for s, p in sorted(self.graph.subject_predicates(term), key=lambda sp: (str(sp[1]), str(sp[0])))
                if isinstance(s, URIRef)
            ],
            "addedByUser": (term, None, None) in self.added,
        }

    def sparql(self, query: str) -> dict:
        """Run a read-only SPARQL query (SELECT, ASK, CONSTRUCT or DESCRIBE).

        rdflib's query parser does not accept SPARQL Update, so INSERT/DELETE
        are rejected here; new knowledge can only enter through add_*()."""
        if not isinstance(query, str) or not query.strip():
            raise InvalidInput("Missing SPARQL query.")
        try:
            result = self.query(query)
            if result.type == "ASK":
                return {"type": "ASK", "boolean": bool(result.askAnswer)}
            if result.type in ("CONSTRUCT", "DESCRIBE"):
                return {"type": result.type, "turtle": result.graph.serialize(format="turtle")}
            variables = [str(v) for v in result.vars]
            rows = []
            for i, row in enumerate(result):
                if i >= MAX_SPARQL_ROWS:
                    break
                rows.append({v: (self.render(row[v]) if row[v] is not None else None) for v in variables})
        except KBError:
            raise
        except Exception as error:  # parse errors, unsupported features, ...
            raise InvalidInput(f"SPARQL error: {error}") from None
        return {"type": "SELECT", "variables": variables, "rows": rows,
                "truncated": len(rows) == MAX_SPARQL_ROWS}

    def schema(self) -> dict:
        """Overview of the vocabulary: useful as context for an LLM in Lab 4."""
        def names(rdf_type):
            return sorted(self.short(s) for s in set(self.graph.subjects(RDF.type, rdf_type))
                          if isinstance(s, URIRef))

        def properties(rdf_type):
            out = []
            for prop in sorted(set(self.graph.subjects(RDF.type, rdf_type)), key=str):
                entry = {"name": self.short(prop)}
                for key, predicate in (("domain", RDFS.domain), ("range", RDFS.range),
                                       ("inverseOf", OWL.inverseOf), ("subPropertyOf", RDFS.subPropertyOf)):
                    if (value := self.graph.value(prop, predicate)) is not None:
                        entry[key] = self.render(value)
                out.append(entry)
            return out

        return {
            "namespace": str(self.ns),
            "prefixes": {p: str(n) for p, n in self.prefixes.items()},
            "classes": names(OWL.Class),
            "objectProperties": properties(OWL.ObjectProperty),
            "dataProperties": properties(OWL.DatatypeProperty),
            "individuals": names(OWL.NamedIndividual),
            "triples": len(self.graph),
            "addedTriples": len(self.added),
            "warnings": self.warnings,
        }

    def export(self, fmt: str = "xml") -> str:
        """The whole knowledge base (ontology + added knowledge), e.g. to open in Protégé."""
        return self.graph.serialize(format=fmt)
