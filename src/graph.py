from langgraph.graph import END, StateGraph

from src.nodes import critic_node, explorer_node, reader_node, should_continue, synthesizer_node
from src.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("explorer", explorer_node)
    graph.add_node("reader", reader_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("explorer")
    graph.add_edge("explorer", "reader")
    graph.add_edge("reader", "synthesizer")
    graph.add_edge("synthesizer", "critic")
    graph.add_conditional_edges("critic", should_continue, {"reader": "reader", "end": END})

    return graph.compile()
