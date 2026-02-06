"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from song_recommender.pages.search_songs import search_songs
from song_recommender.pages.top_page import top_page
from song_recommender.pages.youtube_register import youtube_register
from song_recommender.pages.content_management import content_management
from song_recommender.pages.db_maintenance import db_maintenance

app = rx.App()
app.add_page(
    top_page,
    route="/",
    title="TOP",
    description="楽曲レコメンドシステムのTOPページ",
    image="",
    on_load=None,
)
app.add_page(
    search_songs,
    route="/search-songs",
    title="楽曲検索",
    description="楽曲検索ページ",
    image="",
    on_load=None,
)
app.add_page(
    youtube_register,
    route="/youtube-register",
    title="YouTube登録",
    description="YouTube登録ページ",
    image="",
    on_load=None,
)
app.add_page(
    content_management,
    route="/content-management",
    title="登録済みコンテンツ管理",
    description="登録済みコンテンツ管理ページ",
    image="",
    on_load=None,
)
app.add_page(
    db_maintenance,
    route="/db-maintenance",
    title="DBメンテナンス",
    description="DBメンテナンスページ",
    image="",
    on_load=None,
)
