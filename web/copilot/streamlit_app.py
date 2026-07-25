from __future__ import annotations

import streamlit as st

from web.copilot.navigation import pages


def main() -> None:
    st.set_page_config(
        page_title="Embedded Copilot",
        page_icon=":material/developer_board:",
        layout="wide",
    )
    navigation = st.navigation(pages(), position="top")
    navigation.run()


if __name__ == "__main__":
    main()
