import streamlit as st

st.set_page_config(page_title="PIIOS — Future Modules", layout="wide")
st.title("Future Modules")
st.caption("Clean placeholders only. No fake calculations or mock decision logic populate these pages.")

modules = [
    ("Tax-Aware Recommendations", "Will surface tax-lot-aware sizing and harvesting considerations once the "
     "backend exposes tax-lot and cost-basis data."),
    ("Corporate Actions", "Will surface pending/processed corporate actions (splits, dividends, mergers) "
     "once the backend exposes a corporate-actions feed."),
    ("Agent Orchestration", "Will surface the status of any multi-agent research/analysis runs beyond the "
     "existing LangGraph run monitor, once a broader orchestration contract exists."),
    ("Options Analytics", "Will surface options-specific exposure and analytics once the backend supports "
     "options instruments and greeks."),
    ("Hedge Proposals", "Will surface advisory hedge proposals once the backend exposes a hedging-recommendation "
     "contract."),
    ("Family-Office Access Control", "Will surface per-member, per-portfolio access/permission management once "
     "the backend exposes an access-control contract beyond the current family portfolio registry."),
]

tabs = st.tabs([name for name, _ in modules])
for tab, (name, description) in zip(tabs, modules):
    with tab:
        st.subheader(name)
        st.info(f"Coming soon. {description}", icon="🕒")
        st.caption("No backend contract exists for this module yet — see dashboard/API_GAPS.md.")
