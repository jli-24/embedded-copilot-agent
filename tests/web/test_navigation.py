from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from web.navigation import PAGES


def test_navigation_exposes_four_product_views_in_stable_order() -> None:
    assert PAGES == ("Overview", "Workbench", "Benchmark", "Example Report")


def test_streamlit_app_loads_with_overview_as_default_page() -> None:
    app = AppTest.from_file("web/app.py").run(timeout=15)

    assert not app.exception
    assert app.sidebar.radio[0].options == list(PAGES)
    assert app.sidebar.radio[0].value == "Overview"
    assert app.title[0].value == "Embedded Copilot"


@pytest.mark.parametrize(
    ("page", "title"),
    (
        ("Overview", "Embedded Copilot"),
        ("Workbench", "Workbench"),
        ("Benchmark", "Benchmark"),
        ("Example Report", "ESP32 Camera Example"),
    ),
)
def test_each_product_view_loads_without_runtime_exceptions(
    page: str,
    title: str,
) -> None:
    app = AppTest.from_file("web/app.py").run(timeout=15)

    app.sidebar.radio[0].set_value(page).run(timeout=15)

    assert not app.exception
    assert app.title[0].value == title
