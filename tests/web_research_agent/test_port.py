import asyncio

import pytest

from embedded_copilot.web_research_agent import (
    WebResearchRequest,
    WebResearchUnavailable,
    UnavailableWebResearchPort,
)


def test_unavailable_web_research_is_explicit_and_safe() -> None:
    port = UnavailableWebResearchPort()
    with pytest.raises(WebResearchUnavailable):
        asyncio.run(port.research(WebResearchRequest(query="SPI timing")))
