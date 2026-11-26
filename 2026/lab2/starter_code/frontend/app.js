// Frontend of the Pizza knowledge application (starter code).
// Plain JavaScript: every piece of knowledge shown here comes from the REST API.

// --------------------------------------------------------------------------
// Helpers (given)
// --------------------------------------------------------------------------

/** Call the API and return the JSON response. Throws an Error with the API's message on failure. */
async function api(path, options = {}) {
  const init = { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } };
  if (init.body && typeof init.body !== "string") init.body = JSON.stringify(init.body);
  const response = await fetch(path, init);
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
  return data;
}

/** Create a DOM element: el("td", {className: "num"}, "123"). Text is never parsed as HTML. */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined) node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

function chip(text, extraClass = "") {
  return el("span", { className: `chip ${extraClass}`.trim() }, text);
}

function toast(message, isError = false) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.className = `toast${isError ? " error" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => box.classList.add("hidden"), 4000);
}

function fillSelect(select, items, { keepFirst = false } = {}) {
  const first = keepFirst ? select.options[0] : null;
  select.replaceChildren(...(first ? [first] : []),
    ...items.map(item => el("option", { value: item.value ?? item.name }, item.text ?? item.label)));
}

/** Read a form into a plain object: {name: "...", calories: "250", ...} */
function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

// --------------------------------------------------------------------------
// Shared reference data (toppings, types, bases, spiciness levels)
// --------------------------------------------------------------------------
const state = { toppings: [], types: [], bases: [], spiciness: [] };

async function loadReferenceData() {
  // allSettled: the page still works if some endpoints are not implemented yet.
  const results = await Promise.allSettled([
    api("/api/toppings"), api("/api/pizza-types"), api("/api/bases"), api("/api/spiciness"),
  ]);
  [state.toppings, state.types, state.bases, state.spiciness] =
    results.map(r => (r.status === "fulfilled" ? r.value : []));
  const failed = results.find(r => r.status === "rejected");
  if (failed) toast(failed.reason.message, true);

  const categories = state.toppings.filter(t => t.category === t.name);
  const toppingOptions = [
    ...categories.map(t => ({ value: t.name, text: `Any ${t.label.toLowerCase()}` })),
    ...state.toppings.filter(t => t.category !== t.name).map(t => ({ value: t.name, text: t.label })),
  ];
  fillSelect(document.querySelector("#filter-form [name=topping]"), toppingOptions, { keepFirst: true });
  fillSelect(document.querySelector("#add-pizza-form [name=type]"), state.types);
  fillSelect(document.querySelector("#add-pizza-form [name=base]"), state.bases, { keepFirst: true });
  fillSelect(document.querySelector("#add-topping-form [name=parent]"),
    [{ value: "PizzaTopping", text: "Pizza Topping (new category)" }, ...state.toppings]);
  fillSelect(document.querySelector("#add-topping-form [name=spiciness]"), state.spiciness, { keepFirst: true });

  document.getElementById("type-toppings").replaceChildren(
    ...state.toppings.filter(t => t.category !== t.name).map(t =>
      el("label", { className: "checkbox" }, el("input", { type: "checkbox", name: "toppings", value: t.name }), t.label)));

  renderMenu();
  renderToppingTree();
  loadStats();
}

async function loadStats() {
  const schema = await api("/api/schema");
  document.getElementById("stats").textContent =
    `${schema.triples} triples (${schema.addedTriples} added by users)`;
  if (schema.warnings?.length && !loadStats.warned) {
    loadStats.warned = true;
    toast(schema.warnings.join(" "), true);
  }
}

// --------------------------------------------------------------------------
// Pizzas tab: search and details
// --------------------------------------------------------------------------
let selectedPizza = null;

async function loadPizzas() {
  const params = new URLSearchParams();
  const form = document.getElementById("filter-form");
  const { topping, minCalories, maxCalories } = formData(form);
  if (topping) params.set("topping", topping);
  if (minCalories) params.set("minCalories", minCalories);
  if (maxCalories) params.set("maxCalories", maxCalories);
  if (form.elements.vegetarian.checked) params.set("vegetarian", "true");

  try {
    const pizzas = await api(`/api/pizzas?${params}`);
    const rows = pizzas.map(p => el("tr", {
      className: p.name === selectedPizza ? "selected" : "",
      "data-name": p.name,
      onClick: () => showPizza(p.name),
    }, el("td", {}, p.label), el("td", {}, p.typeLabel), el("td", { className: "num" }, p.calories ?? "–")));
    document.querySelector("#pizza-table tbody").replaceChildren(...rows);
    document.getElementById("pizza-count").textContent = `${pizzas.length} pizza(s)`;
  } catch (error) {
    toast(error.message, true);
  }
}

async function showPizza(name) {
  selectedPizza = name;
  document.querySelectorAll("#pizza-table tbody tr").forEach(row =>
    row.classList.toggle("selected", row.dataset.name === name));
  const panel = document.getElementById("pizza-details");
  try {
    const pizza = await api(`/api/pizzas/${encodeURIComponent(name)}`);
    // TODO (Task 9a): show the pizza's label, type, calories, base and toppings in the panel.
    // Build elements with el() and chip() (renderMenu() is an example) and pass them to
    // panel.replaceChildren(...). For now the raw JSON is shown.
    // TODO (Task 10, optional): if pizza.addedByUser is true, also add a Delete button
    // that calls deletePizza(pizza.name).
    panel.replaceChildren(
      el("h2", {}, pizza.label, pizza.addedByUser ? [" ", chip("Added by user", "user")] : null),
      el("dl", {},
        el("dt", {}, "Name"), el("dd", { className: "mono" }, pizza.name),
        el("dt", {}, "Type"), el("dd", {}, pizza.typeLabel),
        el("dt", {}, "Calories"), el("dd", {}, pizza.calories !== null ? `${pizza.calories} kcal` : "Unknown"),
        el("dt", {}, "Base"), el("dd", {}, pizza.baseLabel ?? "None"),
      ),
      el("h3", {}, "Toppings"),
      pizza.toppings.length
        ? el("div", { className: "chips" }, pizza.toppings.map(t => chip(t.label)))
        : el("p", { className: "muted" }, "None"),
      pizza.addedByUser
        ? el("div", { className: "actions" },
            el("button", { type: "button", className: "secondary small", onClick: () => deletePizza(pizza.name) }, "Delete pizza"))
        : null,
    );
  } catch (error) {
    panel.replaceChildren(el("p", { className: "muted" }, error.message));
  }
}

async function deletePizza(name) {
  if (!confirm(`Delete ${name} from the knowledge base?`)) return;
  try {
    await api(`/api/pizzas/${encodeURIComponent(name)}`, { method: "DELETE" });
    toast(`Deleted ${name}`);
    selectedPizza = null;
    document.getElementById("pizza-details").replaceChildren(el("p", { className: "muted" }, "Pizza deleted."));
    loadPizzas();
    loadStats();
  } catch (error) {
    toast(error.message, true);
  }
}

// --------------------------------------------------------------------------
// Menu and topping tabs
// --------------------------------------------------------------------------
function renderMenu() {
  document.getElementById("menu").replaceChildren(...state.types.map(type =>
    el("div", { className: "card" },
      el("h3", {}, type.label),
      type.comment ? el("p", { className: "muted" }, type.comment) : null,
      el("div", { className: "chips" }, type.toppings.map(t => chip(t.label))),
      type.closed ? el("p", { className: "muted" }, "Only these toppings") : el("p", { className: "muted" }, "May have other toppings too"))));
}

function renderToppingTree() {
  const children = name => state.toppings.filter(t => t.parent === name);
  const branch = topping => el("li", {},
    topping.label, topping.spiciness ? [" ", chip(topping.spiciness, topping.spiciness === "Hot" ? "hot" : "")] : null,
    children(topping.name).length ? el("ul", {}, children(topping.name).map(branch)) : null);
  document.getElementById("topping-tree").replaceChildren(...children("PizzaTopping").map(category =>
    el("div", { className: "card tree" }, el("h3", {}, category.label), el("ul", {}, children(category.name).map(branch)))));
}

// --------------------------------------------------------------------------
// Add-knowledge tab
// --------------------------------------------------------------------------

/** After storing something, show the triples the backend now has about it. */
async function showStored(name, message) {
  const entity = await api(`/api/entity/${encodeURIComponent(name)}`);
  document.getElementById("add-message").textContent = message;
  document.querySelector("#add-statements tbody").replaceChildren(...entity.statements.map(s =>
    el("tr", {}, el("td", { className: "mono" }, s.predicate), el("td", { className: "mono" }, s.object))));
  document.getElementById("add-result").classList.remove("hidden");
}

async function submitForm(event, path, buildBody, describe) {
  event.preventDefault();
  const form = event.target;
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const body = buildBody(form);
    const created = await api(path, { method: "POST", body });
    form.reset();
    await loadReferenceData();
    await loadPizzas();
    await showStored(created.name, describe(created));
    toast(`Stored ${created.name}`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

document.getElementById("add-pizza-form").addEventListener("submit", event =>
  submitForm(event, "/api/pizzas", form => {
    // TODO (Task 9b): return the JSON body for POST /api/pizzas built from the form
    // fields name, type, calories and base. The add-topping form below is an example.
    // Remember that calories must be sent as a number and an empty base as null.
    const data = formData(form);
    return {
      name: data.name.trim(),
      type: data.type,
      calories: Number(data.calories),
      base: data.base || null,
    };
  }, pizza => `Added pizza ${pizza.label} (${pizza.typeLabel}, ${pizza.calories} kcal).`));

document.getElementById("add-topping-form").addEventListener("submit", event =>
  submitForm(event, "/api/toppings", form => {
    const data = formData(form);
    return { name: data.name.trim(), parent: data.parent, spiciness: data.spiciness || null };
  }, topping => `Added topping ${topping.label} in category ${topping.category}.`));

document.getElementById("add-type-form").addEventListener("submit", event =>
  submitForm(event, "/api/pizza-types", form => {
    // TODO (Task 9c): return the JSON body for POST /api/pizza-types:
    //   {name, comment, toppings: [names of the checked boxes], closed: true/false}
    // Hint: form.querySelectorAll("[name=toppings]:checked") and form.elements.closed.checked
    const data = formData(form);
    const toppings = Array.from(form.querySelectorAll("[name=toppings]:checked"), cb => cb.value);
    return {
      name: data.name.trim(),
      comment: data.comment.trim() || null,
      toppings,
      closed: form.elements.closed.checked,
    };
  }, type => `Added pizza type ${type.label} with ${type.toppings.length} topping(s).`));

// --------------------------------------------------------------------------
// SPARQL tab
// --------------------------------------------------------------------------
const EXAMPLES = {
  "All pizzas": `SELECT ?pizza ?type ?kcal WHERE {
  ?pizza a ?type ;
         pizza:hasCaloricContent ?kcal .
  ?type rdfs:subClassOf+ pizza:Pizza .
}
ORDER BY ?kcal`,
  "Toppings of a type": `SELECT ?topping WHERE {
  pizza:MargheritaPizza rdfs:subClassOf ?r .
  ?r owl:onProperty pizza:hasTopping ;
     owl:someValuesFrom ?topping .
}`,
  "Meat toppings": `SELECT ?topping WHERE {
  ?topping rdfs:subClassOf+ pizza:MeatTopping .
}`,
  "Spicier than Mild?": `ASK { pizza:Hot pizza:isSpicierThan+ pizza:Mild }`,
  "Count by category": `SELECT ?category (COUNT(?t) AS ?toppings) WHERE {
  ?category rdfs:subClassOf pizza:PizzaTopping .
  ?t rdfs:subClassOf+ ?category .
}
GROUP BY ?category
ORDER BY DESC(?toppings)`,
};

function setupSparql() {
  const textarea = document.getElementById("sparql-query");
  textarea.value = EXAMPLES["All pizzas"];
  document.getElementById("examples").replaceChildren(...Object.entries(EXAMPLES).map(([title, query]) =>
    el("button", { className: "chip", type: "button", onClick: () => { textarea.value = query; } }, title)));
  document.getElementById("run-sparql").addEventListener("click", runSparql);
  textarea.addEventListener("keydown", event => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) runSparql();
  });
}

async function runSparql() {
  const output = document.getElementById("sparql-result");
  try {
    const result = await api("/api/sparql", { method: "POST", body: { query: document.getElementById("sparql-query").value } });
    if (result.type === "ASK") {
      output.replaceChildren(el("p", {}, "Answer: ", el("strong", {}, String(result.boolean))));
    } else if (result.type === "SELECT") {
      output.replaceChildren(
        el("table", {},
          el("thead", {}, el("tr", {}, result.variables.map(v => el("th", {}, v)))),
          el("tbody", {}, result.rows.map(row =>
            el("tr", {}, result.variables.map(v => el("td", { className: "mono" }, row[v] ?? "")))))),
        el("p", { className: "muted" }, `${result.rows.length} row(s)${result.truncated ? " (truncated)" : ""}`));
    } else {
      output.replaceChildren(el("pre", { className: "mono" }, result.turtle));
    }
  } catch (error) {
    output.replaceChildren(el("p", { className: "muted" }, error.message));
  }
}

// --------------------------------------------------------------------------
// Start-up
// --------------------------------------------------------------------------
document.querySelectorAll("#tabs button").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("active", b === button));
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.id === `tab-${button.dataset.tab}`));
}));

const filterForm = document.getElementById("filter-form");
filterForm.addEventListener("submit", event => { event.preventDefault(); loadPizzas(); });
filterForm.addEventListener("reset", () => setTimeout(loadPizzas, 0));

setupSparql();
loadReferenceData().then(loadPizzas).catch(error => toast(`Could not reach the API: ${error.message}`, true));
