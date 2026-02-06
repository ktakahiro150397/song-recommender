import reflex as rx


# @rx.page(route="/search-songs", title="Search Songs")
def search_songs() -> rx.Component:
    return rx.container(
        rx.heading("Search Songs Page"),
        rx.text("This is where you can search for songs."),
        min_width="100%",
        padding="20px",
        align_items="center",
        justify_content="center",
        display="flex",
        flex_direction="column",
        gap="20px",
        min_height="85vh",
    )
