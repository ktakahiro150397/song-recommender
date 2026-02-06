import reflex as rx


def content_management() -> rx.Component:
    return rx.container(
        rx.heading("📋 登録済みコンテンツ管理", size="8"),
        rx.text("登録済みコンテンツ管理ページ（ダミー）"),
        min_height="85vh",
    )
