import reflex as rx

from song_recommender.pages.db_maintenance import db_maintenance
from song_recommender.pages.search_songs import search_songs

from song_recommender.pages.youtube_register import youtube_register
from song_recommender.pages.content_management import content_management


def top_page() -> rx.Component:
    return rx.container(
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger(
                    "🏠 楽曲検索",
                    value="search",
                    color_scheme="crimson",
                ),
                rx.tabs.trigger(
                    "🏠 YouTube登録",
                    value="register",
                    color_scheme="crimson",
                ),
                rx.tabs.trigger(
                    "🏠 登録済みコンテンツ管理",
                    value="management",
                    color_scheme="crimson",
                ),
                rx.tabs.trigger(
                    "🗄️ DBメンテナンス",
                    value="maintenance",
                    color_scheme="crimson",
                ),
            ),
            rx.tabs.content(
                search_songs(),
                value="search",
            ),
            rx.tabs.content(
                youtube_register(),
                value="register",
            ),
            rx.tabs.content(
                content_management(),
                value="management",
            ),
            rx.tabs.content(
                db_maintenance(),
                value="maintenance",
            ),
            default_value="search",
            color_scheme="crimson",
        ),
        spacing="4",
        min_height="85vh",
    )
