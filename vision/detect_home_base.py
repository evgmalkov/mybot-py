"""Определение домашней деревни по актуальной кнопке Build."""
from game_ui import visible


def detect_home_base():
    return visible('home')
