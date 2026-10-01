from decimal import Decimal

from app.domain import Offer, PartCandidate
from app.ui import parts_results_keyboard, price_alert_target_keyboard


def candidate(index: int) -> PartCandidate:
    offer = Offer(
        provider="Store",
        brand="Brand",
        article=f"A{index}",
        title="Part",
        price=Decimal(str(100 + index)),
        delivery_days=1,
        quality=.9,
    )
    return PartCandidate(
        brand="Brand",
        article=f"A{index}",
        title="Part",
        quality=.9,
        offers=(offer,),
    )


def callback_values(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def test_result_keyboard_has_next_page():
    markup = parts_results_keyboard(
        [candidate(i) for i in range(5)],
        page=0,
        total_count=12,
    )
    values = callback_values(markup)
    assert "page:1" in values
    assert "page:noop" in values
    assert "page:-1" not in values


def test_middle_page_has_previous_and_next():
    markup = parts_results_keyboard(
        [candidate(i) for i in range(5)],
        page=1,
        total_count=12,
    )
    values = callback_values(markup)
    assert "page:0" in values
    assert "page:2" in values


def test_alert_target_keyboard_has_expected_thresholds():
    values = callback_values(price_alert_target_keyboard(2))
    assert "alert:set:2:5" in values
    assert "alert:set:2:10" in values
    assert "alert:set:2:20" in values
    assert "alert:set:2:0" in values
