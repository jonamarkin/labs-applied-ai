# Lab 2, Part 2 — Pizza Knowledge Application (starter code)

Build a knowledge application on top of the pizza ontology **you built in Part 1**. The lab
description (PDF) explains the tasks. This README only covers how to run the code.

Using this starter code is optional: you may build your application with any language, framework
and RDF library, as long as it meets the requirements (R1–R4) in the lab description. Even then,
`tests/test_ontology.ttl` is useful for checking your results.

## Run

1. Save your ontology from Part 1 as `data/pizza_tutorial.rdf`
   (in Protégé: **File > Save as... > RDF/XML Syntax**, see `data/README.md`).
2. Install and start:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python backend/app.py              # open http://localhost:8000
python -m pytest -v                # run the tests
```

If the application cannot use your ontology, it tells you why when it starts. The app starts
before you have done any task; features that are not implemented yet show a "Not implemented
yet" message. The **SPARQL** tab works from the start, so use it to explore your ontology before
you write any code.

## Structure

```
data/pizza_tutorial.rdf     YOUR ontology from Part 1 (never modified by the app)
data/added_knowledge.ttl    knowledge you add through the app (created automatically; delete it to reset)
backend/kb.py               KnowledgeBase: Tasks 1–7 (and optional Task 10)
backend/app.py              Flask REST API: Task 8 (and optional Task 10)
frontend/app.js             Frontend: Task 9
tests/test_api.py           tests against a small test ontology, do not change
tests/test_ontology.ttl     the test ontology (made-up pizzas), do not change
tests/test_own_ontology.py  checks that the app works with YOUR ontology, do not change
```

All places you need to change are marked with `TODO (Task N)`.

## Tests

`tests/test_api.py` uses `tests/test_ontology.ttl`, not your ontology, so the expected results
are the same for everyone. `tests/test_own_ontology.py` runs the application on your
`data/pizza_tutorial.rdf` and checks that the answers are consistent; it is skipped until the file
exists. Most tests go through the REST API, so some of them need more than one task.

| Task | Tests | Also needs |
|---|---|---|
| 1 | `test_toppings` | |
| 2 | `test_pizza_types` | |
| 3 | `test_all_pizzas`, `test_filter_*`, `test_filters_combine`, `test_bad_filters` | |
| 4 | `test_pizza_details*` | |
| 5 | `test_add_pizza*` | 3, 4, 8 |
| 6 | `test_add_topping*` | 1 |
| 7 | `test_add_pizza_type*`, `test_add_open_pizza_type` | 1–6, 8 |
| 5–8 | `test_knowledge_is_persisted` | 1–8 |
| 1–4 | `test_own_ontology_*` (your ontology) | |
| 10 (optional) | `test_delete_pizza` | 5, 8 |
| — | all other tests (`test_bases_and_spiciness`, `test_entity`, `test_sparql_*`, ...) | pass from the start: they test the given code |

Run a single test with, for example, `python -m pytest -v -k test_toppings`.
