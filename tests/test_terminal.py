"""Tests for bob_dev.helpers.terminal."""

from __future__ import annotations

import asyncio

import pytest

from bob_dev.helpers.terminal import (
    BOLD,
    GREEN,
    RED,
    RESET,
    YELLOW,
    _render_car_frame,
    print_error,
    print_info,
    print_step,
    print_success,
    print_warn,
    run_with_spinner,
)


class TestPrintHelpers:
    def test_print_error_contains_message(self, capsys):
        print_error("something went wrong")
        captured = capsys.readouterr()
        assert "something went wrong" in captured.out
        assert RED in captured.out

    def test_print_error_contains_x_prefix(self, capsys):
        print_error("err")
        assert "[✗]" in capsys.readouterr().out

    def test_print_success_contains_message(self, capsys):
        print_success("all good")
        captured = capsys.readouterr()
        assert "all good" in captured.out
        assert GREEN in captured.out

    def test_print_success_contains_check_prefix(self, capsys):
        print_success("ok")
        assert "[✓]" in capsys.readouterr().out

    def test_print_info_contains_message(self, capsys):
        print_info("just info")
        captured = capsys.readouterr()
        assert "just info" in captured.out
        assert "[i]" in captured.out

    def test_print_info_no_color_codes(self, capsys):
        print_info("info msg")
        out = capsys.readouterr().out
        assert RED not in out
        assert GREEN not in out

    def test_print_warn_contains_message(self, capsys):
        print_warn("be careful")
        captured = capsys.readouterr()
        assert "be careful" in captured.out
        assert "[!]" in captured.out

    def test_print_step_contains_step_and_message(self, capsys):
        print_step("[1/4]", "Doing something")
        captured = capsys.readouterr()
        assert "[1/4]" in captured.out
        assert "Doing something" in captured.out
        assert BOLD in captured.out

    def test_print_step_resets_bold(self, capsys):
        print_step("[2/4]", "msg")
        assert RESET in capsys.readouterr().out


class TestRenderCarFrame:
    def test_returns_string(self):
        result = _render_car_frame(0, "test", 0.0)
        assert isinstance(result, str)

    def test_contains_label(self):
        result = _render_car_frame(0, "myLabel", 1.5)
        assert "myLabel" in result

    def test_contains_elapsed_time(self):
        result = _render_car_frame(0, "label", 2.3)
        assert "2.3" in result

    def test_starts_with_carriage_return(self):
        result = _render_car_frame(0, "label", 0.0)
        assert result.startswith("\r")

    def test_contains_yellow_color(self):
        result = _render_car_frame(0, "label", 0.0)
        assert YELLOW in result

    def test_frame_index_cycles_car_frames(self):
        # Different frame indices should produce valid strings.
        for i in range(8):
            result = _render_car_frame(i, "label", 0.0)
            assert isinstance(result, str)


class TestRunWithSpinner:
    def test_returns_function_result(self):
        result = asyncio.run(run_with_spinner(lambda: 42, label="test"))
        assert result == 42

    def test_forwards_positional_args(self):
        result = asyncio.run(run_with_spinner(lambda a, b: a + b, 3, 4, label="test"))
        assert result == 7

    def test_forwards_keyword_args(self):
        result = asyncio.run(
            run_with_spinner(lambda x=0: x * 2, x=5, label="test")
        )
        assert result == 10

    def test_propagates_exception(self):
        def boom():
            raise ValueError("oops")

        with pytest.raises(ValueError, match="oops"):
            asyncio.run(run_with_spinner(boom, label="test"))

    def test_label_keyword_not_forwarded_to_func(self):
        """The 'label' kwarg must be consumed by run_with_spinner, not passed on."""
        called_with_kwargs: dict = {}

        def capture(**kwargs):
            called_with_kwargs.update(kwargs)

        asyncio.run(run_with_spinner(capture, label="my-label"))
        assert "label" not in called_with_kwargs
