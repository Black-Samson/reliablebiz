"""ReliableBiz - Stage 1 demo UI (Streamlit).

Run from the project root:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running without `pip install -e .`
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st  # noqa: E402

from reliablebiz.config import Settings  # noqa: E402
from reliablebiz.datastore import DataStore  # noqa: E402
from reliablebiz.pipeline import RequestTrace, handle_request  # noqa: E402
from reliablebiz.planner import MockPlanner  # noqa: E402
from reliablebiz.request_log import RequestLogger  # noqa: E402
from reliablebiz.tools import TOOL_REGISTRY  # noqa: E402

EXAMPLES = [
    "Do we have USB-C cables in stock?",
    "How many wireless mice are left?",
    "Is the power bank available?",
    "Where is order ORD-1001?",
    "Status of order ORD-9999",
    "Calculate 12 * 3.5 + 4",
    "What is 15% of 240?",
    "Calculate 10 / 0",
    "Where is my order?",
    "Refund order ORD-1002",
]

st.set_page_config(page_title="ReliableBiz (Stage 1)", page_icon="🧰", layout="wide")


@st.cache_resource
def get_services():
    settings = Settings.from_env()
    return settings, DataStore.from_dir(settings.data_dir), RequestLogger(settings.log_dir), MockPlanner()


settings, store, request_logger, planner = get_services()

if "history" not in st.session_state:
    st.session_state.history = []
if "prompt_text" not in st.session_state:
    st.session_state.prompt_text = ""


def _use_example(text: str) -> None:
    st.session_state.prompt_text = text


def _render_trace(trace: RequestTrace) -> None:
    plan, ex = trace.plan, trace.execution

    st.markdown("#### 1. Planner output")
    st.caption(f"Planner: {trace.planner_name}")
    if plan.action == "call_tool":
        c1, c2 = st.columns(2)
        c1.markdown("**Selected tool**")
        c1.code(plan.tool_name or "(none)", language=None)
        c2.markdown("**Proposed arguments**")
        c2.json(plan.arguments)
    elif plan.action == "refuse":
        st.error("No tool selected: request refused (unsafe or unauthorised).")
    else:
        st.info("No tool selected: the planner asked for clarification.")
    st.caption(f"Reason: {plan.rationale}")

    st.markdown("#### 2. Validation")
    if ex is None:
        st.write("Skipped, because no tool was selected.")
    elif ex.status == "rejected_unknown_tool":
        st.error("Rejected: unknown tool.")
        st.table([i.model_dump() for i in ex.issues])
    elif ex.status == "invalid_arguments":
        st.error("Validation FAILED. The tool was not run.")
        st.table([i.model_dump() for i in ex.issues])
    else:
        st.success("Validation passed.")
        st.json(ex.validated_arguments)

    st.markdown("#### 3. Execution result")
    if ex is None or ex.outcome is None:
        st.write("Not executed.")
    else:
        if ex.outcome.ok:
            st.success(f"Executed ({ex.outcome.code}): {ex.outcome.message}")
        else:
            st.warning(f"Executed, but no usable result ({ex.outcome.code}): {ex.outcome.message}")
        st.json(ex.outcome.data)

    st.markdown("#### 4. Final answer")
    st.info(trace.final_answer)
    st.caption(f"Request {trace.request_id} - {trace.latency_ms} ms - {trace.timestamp_utc}")


# ----- page -------------------------------------------------------------------

st.title("ReliableBiz - Stage 1")
st.warning(
    "**MOCK / DEMO PLANNER - this is NOT a fine-tuned model.** Tool choices below come from "
    "hand-written keyword rules. No language model is used and no training has happened. "
    "The validator, executor and tools are real and are what a model will plug into later."
)

with st.sidebar:
    st.header("Try an example")
    for i, example in enumerate(EXAMPLES):
        st.button(example, key=f"ex_{i}", on_click=_use_example, args=(example,), use_container_width=True)
    st.divider()
    st.header("Allowed tools")
    for spec in TOOL_REGISTRY.values():
        st.markdown(f"**{spec.name}**  \n{spec.description}")
    st.caption("Read-only. No payments, shell, SQL or external calls.")

st.text_input("Your request", key="prompt_text", placeholder="e.g. Where is order ORD-1001?")
if st.button("Run request", type="primary", key="run"):
    if st.session_state.prompt_text.strip():
        trace = handle_request(
            st.session_state.prompt_text, planner, store, request_logger, settings.max_input_chars
        )
        st.session_state.history.insert(0, trace)
    else:
        st.warning("Type a request or pick an example first.")

if st.session_state.history:
    _render_trace(st.session_state.history[0])
    if len(st.session_state.history) > 1:
        with st.expander(f"Earlier requests ({len(st.session_state.history) - 1})"):
            for old in st.session_state.history[1:]:
                st.markdown(f"**{old.user_input}**  \n{old.final_answer}")

with st.expander("Sample data (deterministic, read-only)"):
    tab_inv, tab_ord = st.tabs(["Inventory", "Orders"])
    tab_inv.dataframe([i.model_dump() for i in store.inventory], use_container_width=True)
    tab_ord.dataframe(
        [{**o.model_dump(), "items": ", ".join(f"{l.quantity}x {l.sku}" for l in o.items)} for o in store.orders],
        use_container_width=True,
    )

st.caption(f"Request log: {request_logger.path}")
