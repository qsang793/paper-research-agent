"""
Regression test: create_graph() must build the LangGraph without raising.

Pre-existing bug: the graph registered a node named "intent", but AgentState
also has a key "intent". Newer LangGraph forbids a node id that collides with a
state key, so create_graph() raised:
    ValueError: 'intent' is already being used as a state key

The fix renames the node id to "classify_intent" (the metrics label stays
"intent"). This test also guards against any future node-id/state-key clash.
"""
from agent.graph import create_graph
from agent.state import AgentState


def test_create_graph_builds_without_state_key_collision():
    graph = create_graph()  # previously raised ValueError on the "intent" node
    assert graph is not None


def test_no_node_id_collides_with_a_state_key():
    graph = create_graph()
    node_ids = set(graph.get_graph().nodes.keys())
    state_keys = set(AgentState.__annotations__.keys())
    overlap = node_ids & state_keys
    assert not overlap, f"node ids collide with AgentState keys: {overlap}"
