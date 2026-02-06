import reflex as rx


def youtube_register() -> rx.Component:
    return rx.container(
        rx.heading("📺 YouTube登録", size="8"),
        rx.text("YouTube登録ページ（ダミー）"),
        min_height="85vh",
    )
