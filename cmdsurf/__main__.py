#!/usr/bin/env python3
import os
import subprocess
import shutil
from datetime import datetime
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout


def get_terminal_size():
    try:
        return os.get_terminal_size()
    except:
        return (80, 24)


def get_history_path():
    histfile = os.getenv("HISTFILE")
    if not histfile:
        histfile = os.path.expanduser("~/.bash_history")
    if not os.path.exists(histfile):
        zsh_hist = os.path.expanduser("~/.zsh_history")
        if os.path.exists(zsh_hist):
            histfile = zsh_hist
    return histfile


def load_history():
    history_file = get_history_path()
    if not os.path.exists(history_file):
        return [], history_file

    with open(history_file, "r", encoding="utf-8", errors="ignore") as f:
        history = [line.strip() for line in f.readlines() if line.strip()]

    seen = set()
    unique_history = []
    for cmd in reversed(history):
        if cmd not in seen:
            seen.add(cmd)
            unique_history.append(cmd)

    return list(reversed(unique_history)), history_file


def save_history(history, history_file):
    with open(history_file, "w", encoding="utf-8") as f:
        f.write("\n".join(history) + "\n")


async def main():
    history, history_file = load_history()
    undo_stack = []
    _, term_rows = get_terminal_size()
    visible_lines = term_rows - 5

    if not history:
        print("No history found in:", history_file)
        return

    bindings = KeyBindings()
    current_selection = len(history) - 1
    viewport_top = max(0, len(history) - visible_lines)

    def display_history():
        print("\033c", end="")
        print(
            "Bash History (↑/↓: navigate, Enter: execute, Del: delete, Ctrl+Z: undo, q: quit)"
        )
        print(f"Editing: {history_file}")
        print()

        viewport_bottom = min(len(history), viewport_top + visible_lines)

        for i in range(viewport_top, viewport_bottom):
            prefix = "> " if i == current_selection else "  "
            line_num = f"{i+1}:".ljust(5)
            print(f"{prefix}{line_num}{history[i]}")

        print("\n" + "-" * 50)
        if viewport_top > 0:
            print("↑↑↑ More items above ↑↑↑")
        if viewport_bottom < len(history):
            print("↓↓↓ More items below ↓↓↓")

    def ensure_selection_visible():
        nonlocal viewport_top
        if current_selection < viewport_top:
            viewport_top = current_selection
        elif current_selection >= viewport_top + visible_lines:
            viewport_top = current_selection - visible_lines + 1

    @bindings.add("up")
    def _(event):
        nonlocal current_selection
        if current_selection > 0:
            current_selection -= 1
            ensure_selection_visible()
            display_history()

    @bindings.add("down")
    def _(event):
        nonlocal current_selection
        if current_selection < len(history) - 1:
            current_selection += 1
            ensure_selection_visible()
            display_history()

    @bindings.add("pageup")
    def _(event):
        nonlocal current_selection, viewport_top
        current_selection = max(0, current_selection - visible_lines)
        viewport_top = max(0, viewport_top - visible_lines)
        display_history()

    @bindings.add("pagedown")
    def _(event):
        nonlocal current_selection, viewport_top
        current_selection = min(len(history) - 1, current_selection + visible_lines)
        viewport_top = min(len(history) - visible_lines, viewport_top + visible_lines)
        display_history()

    @bindings.add("delete")
    def _(event):
        nonlocal history, current_selection
        if history:
            undo_stack.append((current_selection, history[current_selection]))
            del history[current_selection]
            if current_selection >= len(history) and len(history) > 0:
                current_selection = len(history) - 1
            save_history(history, history_file)
            ensure_selection_visible()
            display_history()

    @bindings.add("c-z")
    def _(event):
        nonlocal history, current_selection
        if undo_stack:
            pos, cmd = undo_stack.pop()
            history.insert(pos, cmd)
            current_selection = pos
            save_history(history, history_file)
            ensure_selection_visible()
            display_history()

    @bindings.add("enter")
    def _(event):
        if history:
            selected_command = history[current_selection]
            print(f"\nExecuting: {selected_command}\n")
            try:
                subprocess.run(selected_command, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Command failed with exit code {e.returncode}")
        event.app.exit()

    @bindings.add("c-c")
    @bindings.add("q")
    def _(event):
        print("\nExiting...")
        event.app.exit()

    display_history()
    session = PromptSession(key_bindings=bindings)

    with patch_stdout():
        await session.prompt_async()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
