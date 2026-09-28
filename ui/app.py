"""Streamlit UI. Run: streamlit run ui/app.py

Render all user text with st.text / st.code / st.markdown without unsafe_allow_html.
"""

import streamlit as st

st.set_page_config(page_title="Incident Response Agent", layout="wide")
st.title("Incident Response Agent")
st.caption("Recalls past ShopFast incidents from Hindsight memory and suggests fixes.")

submit_tab, outcome_tab, memory_tab = st.tabs(["Submit incident", "Record outcome", "Memory"])

with submit_tab:
    st.info("TODO(UI owner): form for Incident -> IncidentService.analyze_incident -> show Suggestion.")

with outcome_tab:
    st.info("TODO(UI owner): form for Outcome -> IncidentService.record_outcome.")

with memory_tab:
    st.info("TODO(UI owner): show recalled memories and their source incident IDs.")
