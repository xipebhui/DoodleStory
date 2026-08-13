from threading import Event, Thread
import time
import unittest

from app.services.grokcli_runtime import serialized_grokcli_call


class GrokcliRuntimeTests(unittest.TestCase):
    def test_serializes_concurrent_calls_in_one_process(self) -> None:
        first_entered = Event()
        allow_first_exit = Event()
        second_entered = Event()
        order: list[str] = []

        def first() -> None:
            with serialized_grokcli_call():
                order.append("first-in")
                first_entered.set()
                allow_first_exit.wait(timeout=2)
                order.append("first-out")

        def second() -> None:
            first_entered.wait(timeout=2)
            with serialized_grokcli_call():
                order.append("second-in")
                second_entered.set()
                order.append("second-out")

        first_thread = Thread(target=first)
        second_thread = Thread(target=second)
        first_thread.start()
        second_thread.start()
        first_entered.wait(timeout=2)
        time.sleep(0.05)
        self.assertFalse(second_entered.is_set())
        allow_first_exit.set()
        first_thread.join(timeout=2)
        second_thread.join(timeout=2)

        self.assertEqual(
            ["first-in", "first-out", "second-in", "second-out"],
            order,
        )


if __name__ == "__main__":
    unittest.main()
