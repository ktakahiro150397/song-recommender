import reflex as rx


class ReusableCounter(rx.ComponentState):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def decrement(self):
        self.count -= 1

    @classmethod
    def get_component(cls, *children, **props):
        return rx.hstack(
            rx.button("-", on_click=cls.decrement),
            rx.heading(f"{cls.count}", size="4", mx="4"),
            rx.button("+", on_click=cls.increment),
            *children,
            **props,
        )
