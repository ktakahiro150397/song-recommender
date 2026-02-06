import reflex as rx

config = rx.Config(
    app_name="song_recommender",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
    backend_port=8001,
)
