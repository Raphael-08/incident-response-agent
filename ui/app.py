"""Streamlit UI. Run: streamlit run ui/app.py

Render all user text with st.text / st.code / st.markdown without unsafe_allow_html.
Incident text and LLM output go through st.text or st.code only, never markdown, so a crafted log or
LLM reply cannot render links or images.
"""

import sys
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # streamlit puts ui/ on the path, not the repo root

from agent.config import ConfigError, load_settings  # noqa: E402
from agent.llm import IncidentAdvisor  # noqa: E402
from agent.memory import IncidentMemory, IncidentMemoryError  # noqa: E402
from agent.models import Incident, Outcome, Severity, Suggestion  # noqa: E402
from agent.service import IncidentService  # noqa: E402
from shopfast.faults import FAULT_LOGS, Fault  # noqa: E402


@st.cache_resource
def build_service() -> IncidentService:
    settings = load_settings()
    return IncidentService(IncidentMemory(settings), IncidentAdvisor(settings))


def get_service() -> IncidentService:
    """The service from session state (tests put a fake there), else the real one."""
    if "service" not in st.session_state:
        try:
            st.session_state["service"] = build_service()
        except ConfigError as exc:
            st.error(f"Configuration error: {exc}. Fill in .env (see .env.example) and restart.")
            st.stop()
    return st.session_state["service"]


def validation_message(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in err['loc']) or 'input'}: {err['msg']}" for err in exc.errors())


def lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def load_example() -> None:
    st.session_state["error_log"] = FAULT_LOGS[Fault(st.session_state["example_fault"])]


def show_suggestion(incident: Incident, suggestion: Suggestion) -> None:
    st.subheader("Suggestion")
    st.text(f"Incident {incident.incident_id}  |  confidence: {suggestion.confidence}")
    if suggestion.llm_error:
        st.warning(f"AI suggestion unavailable: {suggestion.llm_error}")
    if suggestion.memory_used:
        st.success(f"Based on {len(suggestion.similar_incidents)} similar past incident(s) from memory.")
    else:
        st.info("No similar past incident in memory. This is a generic answer.")

    st.markdown("**Probable root cause**")
    st.text(suggestion.probable_root_cause)
    if suggestion.fix_steps:
        st.markdown("**Fix steps, in order**")
        for number, step in enumerate(suggestion.fix_steps, start=1):
            st.text(f"{number}. {step}")
    if suggestion.avoid_steps:
        st.markdown("**Avoid (failed before)**")
        for step in suggestion.avoid_steps:
            st.text(f"- {step}")

    if suggestion.similar_incidents:
        st.subheader("Similar past incidents")
        for item in suggestion.similar_incidents:
            with st.expander(item.incident_id):
                st.text(item.summary)
                if item.source_text:
                    st.caption("Source stored in memory")
                    st.code(item.source_text, language=None)


def submit_tab(service: IncidentService) -> None:
    left, right = st.columns([3, 1])
    left.selectbox("Example error log (ShopFast fault)", [f.value for f in Fault], key="example_fault")
    right.button("Load example", key="load_example", on_click=load_example)

    with st.form("incident_form"):
        st.text_input("Service", key="service_name", placeholder="payment-api")
        st.selectbox("Severity", [s.value for s in Severity], key="severity")
        st.text_input("Title", key="title")
        st.text_area("Symptoms", key="symptoms")
        st.text_area("Error log", key="error_log", height=120)
        submitted = st.form_submit_button("Analyze", key="analyze")

    if submitted:
        try:
            incident = Incident(
                service=st.session_state["service_name"],
                severity=st.session_state["severity"],
                title=st.session_state["title"],
                symptoms=st.session_state["symptoms"],
                error_log=st.session_state["error_log"],
            )
        except ValidationError as exc:
            st.error(f"Invalid incident: {validation_message(exc)}")
            return
        try:
            with st.spinner("Recalling past incidents and asking the advisor..."):
                suggestion = service.analyze_incident(incident)
        except IncidentMemoryError as exc:
            st.error(f"Memory unavailable: {exc}")
            return
        st.session_state.setdefault("incidents", {})[incident.incident_id] = (incident, suggestion)
        st.session_state["last_id"] = incident.incident_id

    last_id = st.session_state.get("last_id")
    if last_id:
        show_suggestion(*st.session_state["incidents"][last_id])


def outcome_tab(service: IncidentService) -> None:
    incidents = st.session_state.get("incidents", {})
    if not incidents:
        st.info("Analyze an incident first, then record its outcome here.")
        return
    ids = list(reversed(incidents))
    with st.form("outcome_form"):
        st.selectbox("Incident", ids, key="outcome_incident",
                     format_func=lambda i: f"{i}: {incidents[i][0].title}")
        st.checkbox("Resolved", key="resolved")
        st.text_area("Actual root cause", key="actual_root_cause")
        st.text_area("Steps that worked (one per line)", key="steps_worked")
        st.text_area("Failed attempts (one per line)", key="failed_attempts")
        st.text_area("Notes", key="notes")
        submitted = st.form_submit_button("Record outcome", key="record_outcome")

    if submitted:
        incident, _ = incidents[st.session_state["outcome_incident"]]
        try:
            outcome = Outcome(
                incident_id=incident.incident_id,
                resolved=st.session_state["resolved"],
                actual_root_cause=st.session_state["actual_root_cause"],
                steps_that_worked=lines(st.session_state["steps_worked"]),
                failed_attempts=lines(st.session_state["failed_attempts"]),
                notes=st.session_state["notes"],
            )
        except ValidationError as exc:
            st.error(f"Invalid outcome: {validation_message(exc)}")
            return
        try:
            service.record_outcome(incident, outcome)
        except IncidentMemoryError as exc:
            st.error(f"Memory unavailable: {exc}")
            return
        st.success(f"Outcome for {incident.incident_id} saved to memory. The next similar incident will use it.")


def learned_tab() -> None:
    last_id = st.session_state.get("last_id")
    if not last_id:
        st.info("Analyze an incident to see what the agent has learned about it.")
        return
    incident, suggestion = st.session_state["incidents"][last_id]
    st.caption(f"Patterns Hindsight consolidated across past incidents, relevant to {incident.incident_id}")
    if not suggestion.learned_patterns:
        st.info("No learned patterns yet for this kind of incident.")
    for pattern in suggestion.learned_patterns:
        st.text(f"- {pattern.text}")


st.set_page_config(page_title="Incident Response Agent", layout="wide")
st.title("Incident Response Agent")
st.caption("Recalls past ShopFast incidents from Hindsight memory and suggests fixes.")

incident_service = get_service()
submit, outcome, learned = st.tabs(["Submit incident", "Record outcome", "What the agent has learned"])
with submit:
    submit_tab(incident_service)
with outcome:
    outcome_tab(incident_service)
with learned:
    learned_tab()
