# Put your ontology from Part 1 here

Save the pizza ontology you built in Protégé in Lab 2, Part 1 in this folder as
`pizza_tutorial.rdf`:

1. Open your ontology in Protégé.
2. **File > Save as...** and choose **RDF/XML Syntax**.
3. Save it as `data/pizza_tutorial.rdf` in this project.

The application reads the namespace from your file, but it expects the class and property
names from the tutorial (`Pizza`, `NamedPizza`, `PizzaTopping`, `hasTopping`, ...). If something
is missing, `python backend/app.py` tells you what.

Knowledge you add through the application is stored in `data/added_knowledge.ttl`; your
ontology file is never changed. Delete `added_knowledge.ttl` to start over.
