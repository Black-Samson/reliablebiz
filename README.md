# ReliableBiz (Stage 1: local app)

A small, safe, **read-only** business assistant sandbox: inventory lookup, order lookup and a calculator,
with every tool call validated by Pydantic schemas before anything runs.

> **The planner in this stage is a MOCK/DEMO rule-based router. It is NOT a language model and NOT fine-tuned.**
> No training has happened. The validator, executor and tools are real; a model will plug in at the
> `Planner` interface in a later stage. The UI shows this notice permanently.

Needs **no paid API key** and no internet access after installation.

## What it does

For each request the UI shows four steps: **1. selected tool + proposed arguments**, **2. validation result**,
**3. execution result**, **4. final answer**. Each request is also appended to `logs/requests.jsonl`.

Safety properties (all covered by tests):

- Tools are an allow-list of three read-only functions; unknown tool names are rejected.
- Arguments are validated by Pydantic (`extra="forbid"`, length and character limits). Missing fields,
  malformed order IDs and hostile text (e.g. `'; DROP TABLE`) never reach a tool.
- The calculator parses with `ast` and an allow-list of operators. No `eval()`/`exec()`, no names, no calls.
  It uses `Decimal` (so `0.1 + 0.2 = 0.3`), rejects `**`, and handles division by zero and huge results.
- No SQL, shell, file writes, payments, e-mail or network calls exist anywhere in the code.
  Requests such as "refund order ORD-1002" are refused by the mock planner and no tool runs.
- Unknown order IDs and nonexistent products return a clear "not found" answer.

## Setup on Windows (PowerShell)

Run these from the project folder (the one containing `app` and `src`).

```powershell
# 1. Create a virtual environment (use "python" instead of "py -3" if "py" is not installed)
py -3 -m venv .venv

# 2. Activate it. If PowerShell blocks the script, run the next line first (affects only this window):
#    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies (add -dev to also get pytest)
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

# 4. Run the tests
python -m pytest

# 5. Launch the app (opens http://localhost:8501)
python -m streamlit run app/streamlit_app.py
```

Press `Ctrl+C` in PowerShell to stop the app. Optional settings: copy `.env.example` to `.env`.

## Example requests

- `Do we have USB-C cables in stock?` / `How many wireless mice are left?` / `Is the power bank available?`
- `Where is order ORD-1001?` / `Status of order ORD-9999` (unknown ID)
- `Calculate 12 * 3.5 + 4` / `What is 15% of 240?` / `Calculate 10 / 0`
- `Where is my order?` (missing order ID: validation fails and no tool runs)
- `Refund order ORD-1002` (refused)

## Project layout

```
app/streamlit_app.py       UI only; no business logic
src/reliablebiz/
  schemas.py               Pydantic input schemas + result models
  calculator.py            safe ast-based arithmetic
  tools.py                 the 3 tools + allow-list registry (+ JSON-schema catalog)
  executor.py              allow-list -> validate -> run; never raises
  planner.py               Planner protocol + MockPlanner (rule-based, NOT a model)
  answers.py               deterministic answer templates
  pipeline.py              planner -> executor -> answer -> log
  datastore.py             read-only sample data
  request_log.py  config.py
data/inventory.json  data/orders.json     deterministic sample data
tests/                     77 tests
```

## Plugging in a model later

Implement `Planner` (`name`, `is_fine_tuned`, `plan(text) -> PlanResult`) and pass it to
`handle_request(...)`. The executor re-validates every proposed call, so a model cannot bypass the
schemas or the allow-list. Nothing in this stage imports any training code.

## Known limitations

- The mock planner only understands the phrasings above; anything else gets a clarification message.
- `%` in the calculator means modulo; "15% of 240" is handled by the planner, not the calculator.
- Sample data is fictional. Licences for later stages (AgentTune/AuditKIT/Tiny Aya) are non-commercial.
