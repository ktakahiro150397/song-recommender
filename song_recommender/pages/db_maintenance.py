import reflex as rx


def db_maintenance() -> rx.Component:
    return rx.container(
        rx.heading("🗄️ DBメンテナンス", size="8"),
        rx.text("DBメンテナンスページ（ダミー）"),
        min_height="85vh",
    )
