import reflex as rx


def top_page() -> rx.Component:
    return rx.container(
        rx.heading("🏠 TOPページ", size="8"),
        rx.text("楽曲レコメンドシステムのTOPページです。"),
        rx.link(rx.text("楽曲検索"), href="/search-songs"),
        rx.link(rx.text("YouTube登録"), href="/youtube-register"),
        rx.link(rx.text("登録済みコンテンツ管理"), href="/content-management"),
        rx.link(rx.text("DBメンテナンス"), href="/db-maintenance"),
        spacing="4",
        min_height="85vh",
    )
