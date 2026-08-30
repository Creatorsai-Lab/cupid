from html import escape

from app.routers.connections import _close_window_html


def test_close_windows_html_escapes_messages() -> None:
    payload = '<img src=x onerror="alert(1)">'

    response = _close_window_html(success=False, message=payload)
    body = response.body.decode("utf-8")

    assert payload not in body
    assert f"<p>{escape(payload, quote=True)}</p>" in body
