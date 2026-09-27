from app.data.store import Store
from app.tools.knowledge import KnowledgeBase, tokenize
from app.tools.orders import describe_order, get_order, list_orders
from app.tools.tickets import create_ticket, list_tickets


def test_get_order_joins_customer_and_shipment():
    order = get_order(Store(), "1042")
    assert order["customer_id"] == "C-101"
    assert order["shipment_status"] == "delayed"
    assert [i["name"] for i in order["items"]] == ["Ridgeline 2P Backpacking Tent", "Pocket Jet Stove"]
    assert "Memphis" in describe_order(order)


def test_get_order_missing_returns_none():
    assert get_order(Store(), "9999") is None


def test_list_orders_is_case_insensitive():
    orders = list_orders(Store(), "c-101")
    assert {o["id"] for o in orders} == {"1041", "1042"}


def test_create_ticket_increments_ids_and_sanitizes_priority():
    store = Store()
    first = create_ticket(store, {"title": "A", "priority": "high"})
    second = create_ticket(store, {"title": "B", "priority": "not-a-priority"})
    assert (first["id"], second["id"]) == ("T-1001", "T-1002")
    assert second["priority"] == "medium"
    assert len(list_tickets(store)) == 2


def test_tokenize_stems_and_drops_stopwords():
    assert tokenize("The boots were damaged") == tokenize("boot damage")


def test_knowledge_search_finds_relevant_sections():
    kb = KnowledgeBase()
    top = kb.search("warranty on hiking boots")[0]
    assert (top.source, top.section) == ("warranty.md", "Hiking boots and footwear")
    assert kb.search("my delivery is late")[0].section == "Late or delayed deliveries"
    assert kb.search("") == []
