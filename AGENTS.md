# Project Context

Python application for hydraulic sizing and recommendation of pump pipelines,
typically wastewater sea outfalls. It has a command-line runner, a FastAPI
backend, and a small browser UI served as a static HTML file.

## Architecture

- `hydraulikk.py`: pure hydraulic formula functions.
- `oppdrift_lodd.py`: buoyancy, ballast weight, and cost calculations.
- `data_io.py`: reads and validates the pipe catalog, discovers SDR classes,
	and canonicalizes the DN/OD column.
- `beregninger.py`: calculates each available DN/SDR combination and applies
	the absolute acceptance criteria.
- `rangering.py`: selects a recommendation from accepted alternatives.
- `tjenester.py`: coordinates catalog validation, calculation, and ranking;
	the API calls this service.
- `modeller.py`: Pydantic input, option, and result models.
- `api.py`: FastAPI routes and HTTP error translation; do not put domain
	calculations here. It mounts `static/index.html` at `/ui/`.
- `main.py`: local CLI, exports CSV/Excel files, and saves plots. It currently
	calls calculation/ranking modules directly rather than `tjenester.py`.
- `eksport.py`, `plotting.py`: generated exports and plots, written under
	`resultater/`.
- `config.py`: paths relative to the project directory.
- `tests/`: pytest coverage by module, plus integration coverage for the API
	and service layer.
- `docs/`: calculation background and catalog format.
- `_notes/`: git-ignored personal notes, not a specification of behavior.

## Domain Rules

- `data/RØR.csv` is the source catalog. It uses semicolons and decimal commas;
	SDR classes and available DN values are discovered from its contents rather
	than hardcoded in calculation logic.
- Catalog rows may omit a DN/SDR combination. Duplicate positive DN/OD values
	are an error. Suspicious rows are reported by catalog validation and are
	skipped by the calculation/export loops.
- The wall-thickness plausibility check accepts values within ±50% of DN/SDR.
	This is known to reject some small-diameter PE pipes because of minimum
	manufacturing wall thickness; do not silently broaden it without checking
	the catalog and tests.
- `BeregningsInput` requires `qdim_l_s`, `lengde_m`, and `tillatte_sdr` for
	every calculation. Other model fields have defaults; `lengde_sjo_m=None`
	means the full `lengde_m` is treated as sea-laid. The HTML form currently
	pre-fills Qdim/length and checks SDR 13.6/17 when present, but those are UI
	conveniences, not API/model defaults; users must be able to change them.
- Accepted pipes must meet minimum velocity, minimum shear stress, maximum
	total head loss, and the SDR pressure limit `p = 2σ/(SDR - 1)`. Total head
	here is friction plus minor losses; static lift is not modeled.
- Each candidate also has a hard maximum outer diameter:
	`D_max = 100 mm * (1 + 2 * 6.3 MPa / p_design)`. The current implementation
	derives `p_design` from that candidate's calculated total head, converts bar
	to MPa, and requires `DN/OD <= D_max`. The fixed 6.3 MPa is separate from the
	configurable material stress used by the existing SDR pressure check.
- Recommendation strategies are `billigste_godkjent`, `best_hydraulisk`,
	`balansert`, and `egendefinert_vekting`. Weighted strategies use min-max
	normalization among accepted options and score price, velocity, and shear
	stress; total head is an acceptance limit, not a weighted objective.
- Pydantic/FastAPI structural input errors return HTTP 422. Business/catalog
	`ValueError`s from the service are translated to HTTP 400.

## Development

Python 3.10+ is documented as the minimum. Install dependencies with:

```bash
python -m pip install -r requirements.txt
```

Run tests with:

```bash
python -m pytest
```

Run the API and UI locally with:

```bash
uvicorn api:app --reload
```

Then open `http://127.0.0.1:8000/ui/`; API docs are at `/docs`. Run the CLI
with `python main.py`. It uses project-specific Qdim, length, and SDR values
currently set in `main()` and generates files under `resultater/`; these files
are git-ignored.

When changing shared behavior, add or update the nearest module-level tests.
For orchestration changes, keep API/service behavior and the separate CLI path
in mind. Preserve the existing Norwegian domain vocabulary and units in
user-facing messages and results.

## Documentation Caveats

`README.md` describes installation and the current workflow.
`docs/faglig-grunnlag.md` documents formulas, units, ranking, and catalog
format. Verify behavior in code and tests; local `_notes/` files are personal
working notes rather than a specification.

## Coding Style

Prioritize simplicity over abstraction.

- Prefer the simplest implementation that solves the current task correctly.
- Do not introduce classes, design patterns, factories, interfaces, registries,
	or abstraction layers unless they are clearly necessary.
- Avoid premature generalization and optimization; do not build for hypothetical
	requirements.
- Prefer a few readable functions over deeply layered architectures. Keep code
	understandable and easy to modify.
- Reuse existing project patterns and minimize dependencies.
- Favor explicit, boring code over clever code.

## Scope

Make the smallest reasonable change that fulfills the request. Do not redesign
the architecture, add unrequested features, or refactor unrelated code unless
the task requires it.
