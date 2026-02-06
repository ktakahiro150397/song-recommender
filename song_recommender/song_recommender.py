"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config
from song_recommender.components.reusable_counter import ReusableCounter
from song_recommender.pages.search_songs import search_songs


class State(rx.State):
    """The app state."""

    count: int = 0

    @rx.event
    def increment(self):
        """An event to increment the count."""
        self.count += 1


def counter() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading(f"Count: {State.count}"),
            rx.button("increment", on_click=State.increment),
            rx.text("Click the button to increment the count."),
        ),
        spacing="5",
        justify="center",
        min_height="85vh",
    )


reusable_counter = ReusableCounter.create()


def index() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("🎵 楽曲レコメンドシステム", size="9"),
            # rx.text(
            #     "Get started by editing ",
            #     rx.code(f"{config.app_name}/{config.app_name}.py"),
            #     size="5",
            # ),
            # rx.link(
            #     rx.button("Check out our docs!"),
            #     href="https://reflex.dev/docs/getting-started/introduction/",
            #     is_external=True,
            # ),
            rx.heading("楽曲検索・プレイリスト作成"),
            rx.text("楽曲検索を行い、プレイリストの作成を行います。"),
            rx.link(
                rx.text("楽曲検索画面へ"),
                href="/search-songs",
                is_external=False,
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
app.add_page(search_songs)
