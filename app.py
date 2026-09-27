"""Dual-Pane Streamlit App for ScrollMind Instagram Reels Multimodal Knowledge Graph.

Finalized Lakebase 4-Tier Topology:
Category -> Subcategory -> Concept -> Reel

Right Pane: Paginated Card Carousel UI with Navigation and Indicator Bubbles.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from agent.graph_engine import ReelGraphEngine
from agent.langgraph_agent import run_reel_agent

st.set_page_config(layout="wide", page_title="ScrollMind | Reel Knowledge Graph")


@st.cache_resource
def load_graph_engine() -> ReelGraphEngine:
    """Loads and caches the ReelGraphEngine."""
    lakebase_url = os.getenv("LAKEBASE_DATABASE_URL")
    data_source = lakebase_url if lakebase_url else "data/dummy_reels.jsonl"
    return ReelGraphEngine(data_source)


def generate_graph_html(engine: ReelGraphEngine, selected_categories: list[str]) -> str:
    """Generates an interactive PyVis HTML network visualization with Obsidian styling.

    Styling:
    - Categories: Diamonds (#e06c75, size 28)
    - Subcategories: Dots (#d19a66, size 20)
    - Concepts: Dots (#98c379, size 14)
    - Reels: Dots (#61afef, size 16), hover tooltip showing title, summary with embedded URLs, and Instagram link
    """
    net = Network(height="720px", width="100%", bgcolor="#1e1e2e", font_color="#cdd6f4")
    net.barnes_hut(
        gravity=-12000,
        central_gravity=0.25,
        spring_length=120,
        spring_strength=0.03,
        damping=0.09,
        overlap=0.1,
    )

    # Determine visible nodes based on selected categories
    if not selected_categories or "All" in selected_categories:
        visible_nodes = set(engine.graph.nodes())
    else:
        visible_nodes = set()
        # Find category nodes matching selected names/labels
        cat_nodes = []
        for n, d in engine.graph.nodes(data=True):
            if d.get("node_type") == "category":
                if d.get("name") in selected_categories or d.get("label") in selected_categories:
                    cat_nodes.append(n)

        for cat_node in cat_nodes:
            visible_nodes.add(cat_node)
            # Traverse to subcategories
            for subcat_node in engine.graph.neighbors(cat_node):
                if engine.graph.nodes[subcat_node].get("node_type") == "subcategory":
                    visible_nodes.add(subcat_node)
                    # Traverse to concepts
                    for concept_node in engine.graph.neighbors(subcat_node):
                        if engine.graph.nodes[concept_node].get("node_type") == "concept":
                            visible_nodes.add(concept_node)
                            # Traverse to reels
                            for reel_node in engine.graph.neighbors(concept_node):
                                if engine.graph.nodes[reel_node].get("node_type") == "reel":
                                    visible_nodes.add(reel_node)

    # Add nodes to PyVis network
    for node_id in visible_nodes:
        data = engine.graph.nodes[node_id]
        node_type = data.get("node_type", "concept")
        name = data.get("name", node_id)

        if node_type == "category":
            net.add_node(
                node_id,
                label=name,
                title=f"<b>Category:</b> {name}",
                shape="diamond",
                color="#e06c75",
                size=28,
                borderWidth=2,
            )
        elif node_type == "subcategory":
            net.add_node(
                node_id,
                label=name,
                title=f"<b>Subcategory:</b> {name}",
                shape="dot",
                color="#d19a66",
                size=20,
                borderWidth=1,
            )
        elif node_type == "concept":
            net.add_node(
                node_id,
                label=name,
                title=f"<b>Concept:</b> {name}",
                shape="dot",
                color="#98c379",
                size=14,
                borderWidth=1,
            )
        elif node_type == "reel":
            title = data.get("title", name)
            trunc_title = (title[:22] + "...") if len(title) > 25 else title
            summary = data.get("summary", "")
            url = data.get("url", "")
            obs_url = data.get("obsidian_url", "")
            tooltip = (
                f"<b>{title}</b><br><br>"
                f"<b>Summary:</b> {summary}<br><br>"
                f"<b>Instagram Reel:</b> <a href='{url}' target='_blank'>{url}</a><br>"
                f"<b>Obsidian Vault:</b> <a href='{obs_url}' target='_blank'>{obs_url}</a>"
            )
            net.add_node(
                node_id,
                label=trunc_title,
                title=tooltip,
                shape="dot",
                color="#61afef",
                size=16,
                borderWidth=2,
            )

    # Add edges between visible nodes
    for u, v, edge_data in engine.graph.edges(data=True):
        if u in visible_nodes and v in visible_nodes:
            relation = edge_data.get("relation", "")
            dash = True if "BRIDGE" in relation else False
            net.add_edge(
                u,
                v,
                color="#585b70",
                title=relation,
                width=1.5,
                dashes=dash,
                smooth={"type": "continuous"},
            )

    return net.generate_html()


def main():
    engine = load_graph_engine()

    st.title("🧠 ScrollMind | Reels Multimodal Knowledge Graph")
    st.caption("Lakebase Postgres Decoupled GraphRAG Layer for Instagram Reels")

    # Dual-pane columns: Left pane (1.2) for Graph, Right pane (1.0) for Assistant Carousel
    col_left, col_right = st.columns([1.2, 1.0])

    with col_left:
        st.subheader("🕸️ Reels Knowledge Graph")

        # Category Multi-Select Filter
        categories = sorted(list({
            d.get("name")
            for _, d in engine.graph.nodes(data=True)
            if d.get("node_type") == "category"
        }))
        selected_cats = st.multiselect(
            "Filter by Category:",
            options=categories,
            default=[],
            placeholder="Showing All Categories",
        )

        # Legend badges
        st.markdown(
            """
            <div style="display: flex; gap: 14px; margin-bottom: 8px; font-size: 0.85rem;">
                <span style="color: #e06c75; font-weight: bold;">◆ Category</span>
                <span style="color: #d19a66; font-weight: bold;">● Subcategory</span>
                <span style="color: #98c379; font-weight: bold;">● Concept</span>
                <span style="color: #61afef; font-weight: bold;">● Reel</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.spinner("Rendering multimodal knowledge graph..."):
            html_graph = generate_graph_html(engine, selected_categories=selected_cats)
            components.html(html_graph, height=720, scrolling=True)

    with col_right:
        st.subheader("💬 ReelMind Assistant")

        # 1. Session State Initialization
        if "qa_cards" not in st.session_state:
            st.session_state.qa_cards = []
        if "active_card_idx" not in st.session_state:
            st.session_state.active_card_idx = 0

        # Ensure active_card_idx stays bounded
        if st.session_state.qa_cards:
            if st.session_state.active_card_idx >= len(st.session_state.qa_cards):
                st.session_state.active_card_idx = len(st.session_state.qa_cards) - 1
            elif st.session_state.active_card_idx < 0:
                st.session_state.active_card_idx = 0

        # Quick starter prompts
        st.markdown("**Quick Prompts:**")
        qcol1, qcol2, qcol3 = st.columns(3)
        starter_query = None

        with qcol1:
            if st.button("💡 Data Science Prep", use_container_width=True, help="Prep me for a data science interview based on my reels"):
                starter_query = "Prep me for a data science interview based on my reels"
        with qcol2:
            if st.button("🥗 Meal Prep", use_container_width=True, help="What meal prep recipes did I save?"):
                starter_query = "What meal prep recipes did I save?"
        with qcol3:
            if st.button("🛠️ Top CLI Tools", use_container_width=True, help="Show the top developer CLI tools list"):
                starter_query = "Show the top developer CLI tools list"

        # 2. Card Carousel Component
        qa_cards = st.session_state.qa_cards
        active_idx = st.session_state.active_card_idx

        if not qa_cards:
            # Welcome card when carousel is empty
            with st.container(border=True):
                st.markdown("### 👋 Welcome to **ScrollMind**")
                st.markdown(
                    "I am your AI research assistant for multimodal Instagram Reels.\n\n"
                    "Ask me questions about your saved reels, explore interview topics, extract recipes with checklist ingredients, "
                    "or review curated developer tools.\n\n"
                    "Click a **Quick Prompt** above or type your question below to create your first interactive Q&A Card!"
                )
        else:
            current_card = qa_cards[active_idx]

            with st.container(border=True):
                # Header row: Query on left, Card pagination indicator on right
                hdr_col1, hdr_col2 = st.columns([3, 1])
                with hdr_col1:
                    st.caption(f"🗓️ {current_card.get('timestamp', '')}")
                with hdr_col2:
                    st.markdown(
                        f"<div style='text-align: right; font-size: 0.85rem; font-weight: 600; color: #61afef;'>"
                        f"Card {active_idx + 1} of {len(qa_cards)}</div>",
                        unsafe_allow_html=True,
                    )

                # User Question Section
                st.markdown(f"**👤 Question:**\n> **{current_card['query']}**")
                st.divider()

                # Agent Response Section
                st.markdown(current_card["response"])

                st.write("")
                # Download button for current card
                download_text = (
                    f"# ReelMind Research Note\n\n"
                    f"**Question:** {current_card['query']}\n"
                    f"**Generated:** {current_card.get('timestamp', '')}\n\n"
                    f"---\n\n"
                    f"{current_card['response']}\n"
                )
                st.download_button(
                    label="📥 Save this Card (.md)",
                    data=download_text,
                    file_name=f"reelmind_card_{active_idx + 1}.md",
                    mime="text/markdown",
                    use_container_width=True,
                    key=f"dl_card_{active_idx}",
                )

            # 3. Carousel Navigation & Indicator Bubbles
            # NOTE: Streamlit allows only ONE level of column nesting, so the
            # [1 : 2 : 1] three-part nav bar is expressed as a single row of
            # weighted columns: [◀ Prev] [bubble 1] [bubble 2] ... [bubble N] [Next ▶]
            total_cards = len(qa_cards)

            # Window the bubbles if there are many cards so they stay readable
            MAX_BUBBLES = 10
            if total_cards <= MAX_BUBBLES:
                visible_indices = list(range(total_cards))
            else:
                half = MAX_BUBBLES // 2
                start = max(0, min(active_idx - half, total_cards - MAX_BUBBLES))
                visible_indices = list(range(start, start + MAX_BUBBLES))

            nav_weights = [1.0] + [0.6] * len(visible_indices) + [1.0]
            nav_cols = st.columns(nav_weights)

            # Left column: Previous
            with nav_cols[0]:
                if st.button(
                    "◀ Prev",
                    disabled=(active_idx == 0),
                    use_container_width=True,
                    key="btn_prev",
                ):
                    st.session_state.active_card_idx = max(0, active_idx - 1)
                    st.rerun()

            # Center columns: clickable indicator bubbles (● active, ○ inactive)
            for col_offset, b_idx in enumerate(visible_indices):
                with nav_cols[1 + col_offset]:
                    is_active = b_idx == active_idx
                    bubble_label = f"● {b_idx + 1}" if is_active else f"○ {b_idx + 1}"
                    if st.button(
                        bubble_label,
                        key=f"bubble_{b_idx}",
                        use_container_width=True,
                        help=f"Jump to Card {b_idx + 1}: {qa_cards[b_idx]['query'][:40]}...",
                    ):
                        st.session_state.active_card_idx = b_idx
                        st.rerun()

            # Right column: Next
            with nav_cols[-1]:
                if st.button(
                    "Next ▶",
                    disabled=(active_idx == total_cards - 1),
                    use_container_width=True,
                    key="btn_next",
                ):
                    st.session_state.active_card_idx = min(total_cards - 1, active_idx + 1)
                    st.rerun()

        # 4. Input Persistence: chat_input pinned to the bottom of the column
        chat_prompt = st.chat_input("Ask a question about your saved reels...")
        submitted_prompt = starter_query or chat_prompt

        if submitted_prompt:
            with st.spinner("Traversing knowledge graph & generating card..."):
                response = run_reel_agent(submitted_prompt)
                card_data = {
                    "query": submitted_prompt,
                    "response": response,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                }
                st.session_state.qa_cards.append(card_data)
                # Focus on the newest card
                st.session_state.active_card_idx = len(st.session_state.qa_cards) - 1
            st.rerun()


if __name__ == "__main__":
    main()
