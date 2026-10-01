from app.domain import OrderCase, OrderCaseNote
from app.ui import order_case_text, operator_case_keyboard, user_case_keyboard


def build_case(status="open"):
    return OrderCase(
        id=5,
        order_id=7,
        telegram_user_id=42,
        case_type="support",
        status=status,
        priority="normal",
        summary="Проблема с заказом",
        assigned_operator_user_id=9001,
        resolution="Вопрос решён" if status == "resolved" else None,
    )


def callbacks(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def test_user_case_hides_internal_operator_notes():
    notes = [
        OrderCaseNote(
            id=1,
            case_id=5,
            author_user_id=42,
            author_role="user",
            body="Пользовательское сообщение",
        ),
        OrderCaseNote(
            id=2,
            case_id=5,
            author_user_id=9001,
            author_role="operator_internal",
            body="Внутренняя заметка оператора",
        ),
    ]

    user_text = order_case_text(build_case(), notes)
    assert "Пользовательское сообщение" in user_text
    assert "Внутренняя заметка оператора" not in user_text

    operator_text = order_case_text(build_case(), notes, operator_view=True)
    assert "Пользовательское сообщение" in operator_text
    assert "Внутренняя заметка оператора" in operator_text


def test_case_controls_change_after_resolution():
    user_open = callbacks(user_case_keyboard(build_case("open")))
    assert "case:note:5" in user_open

    user_resolved = callbacks(user_case_keyboard(build_case("resolved")))
    assert "case:note:5" not in user_resolved

    operator_open = callbacks(operator_case_keyboard(build_case("open")))
    assert "ops:assign:5" in operator_open
    assert "ops:resolve:5" in operator_open

    operator_resolved = callbacks(operator_case_keyboard(build_case("resolved")))
    assert "ops:assign:5" not in operator_resolved
    assert "ops:resolve:5" not in operator_resolved
