from scripts.update_movers_data import quantity_at

def test_sale_does_not_look_like_price_loss():
    txs=[{"date":"2026-10-02","id":"boerse-de-aktienfonds","type":"Verkauf","quantity":34.0}]
    # 30 units remain today; before the sale there were 64.
    assert quantity_at("01.10.2026","boerse-de-aktienfonds",30.0,txs)==64.0

def test_purchase_is_reversed_from_current_quantity():
    txs=[{"date":"2026-09-15","id":"example","type":"Kauf","quantity":5.0}]
    assert quantity_at("01.09.2026","example",12.0,txs)==7.0
