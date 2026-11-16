"""Регрессии рецептов и наград без подключения к эмулятору."""
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch, call

sys.path.insert(0, str(Path.cwd()))
from paths import BASE_DIR
for layer in ('core', 'emu', 'vision', 'train', 'villages', 'ui'):
    sys.path.insert(0, str(BASE_DIR / layer))
import main
import game_ui as ui
import quick_train as quick
import smart_train
import numpy as np


class EventNavigation(unittest.TestCase):
    def test_reward_chain_survives_brief_home(self):
        frames = iter(['chest_hammer', 'animation', 'chest_continue', 'home',
                       'reward_tap', 'food_continue', 'home', 'home', 'home', 'home'])
        clock = iter(range(100))
        with patch.object(ui, 'capture_array', side_effect=lambda: next(frames)), \
                patch.object(ui, 'visible', side_effect=lambda name, image: name == image), \
                patch.object(ui, 'tap_named') as tap, \
                patch.object(ui.time, 'monotonic', side_effect=lambda: next(clock)), \
                patch.object(ui.time, 'sleep'), patch.object(main, '_check_stop', return_value=False):
            self.assertTrue(ui.collect_treasure_rewards())
            self.assertEqual(tap.call_args_list, [call('chest_hit'), call('chest_continue'),
                                                call('chest_hit'), call('chest_continue')])

    def test_unknown_reward_does_not_tap(self):
        with patch.object(ui, 'capture_array', return_value='unknown'), \
                patch.object(ui, 'visible', return_value=False), patch.object(ui, 'tap_named') as tap, \
                patch.object(ui.time, 'monotonic', side_effect=[0, 1, 61]), \
                patch.object(ui.time, 'sleep'), patch.object(main, '_check_stop', return_value=False):
            self.assertFalse(ui.collect_treasure_rewards())
            tap.assert_not_called()

    def test_stop_does_not_tap(self):
        with patch.object(main, '_check_stop', return_value=True), patch.object(ui, 'tap_named') as tap:
            self.assertFalse(ui.collect_treasure_rewards())
            tap.assert_not_called()

    def test_search_requires_opponent_screen(self):
        with patch.object(ui, 'visible', return_value=True), patch.object(ui, 'tap_named') as tap, \
                patch.object(ui, 'wait_visible', return_value=False):
            self.assertFalse(main.search_attack())
            tap.assert_called_once_with('confirm_attack')

    def test_recipe_with_and_without_confirmation(self):
        for confirmation in (True, False):
            with self.subTest(confirmation=confirmation), ExitStack() as stack:
                stack.enter_context(patch.object(quick, 'open_army', return_value=True))
                stack.enter_context(patch.object(quick, 'capture_array', return_value=np.zeros((900, 1600, 3), np.uint8)))
                stack.enter_context(patch.object(quick, 'load_template', return_value=np.zeros((10, 10, 3), np.uint8)))
                stack.enter_context(patch.object(quick.cv2, 'minMaxLoc', return_value=(0, 1, (0, 0), (0, 0))))
                stack.enter_context(patch.object(quick, 'visible', side_effect=[True, False, True] if confirmation else [False, True]))
                stack.enter_context(patch.object(quick, 'close_army', return_value=True))
                stack.enter_context(patch.object(smart_train, 'tap'))
                stack.enter_context(patch.object(quick.time, 'sleep'))
                stack.enter_context(patch.object(main, '_check_stop', return_value=False))
                tap = stack.enter_context(patch.object(quick, 'tap_named'))
                self.assertTrue(quick.quick_train(1))
                expected = [call('recipes')] + ([call('recipe_confirm')] if confirmation else [])
                self.assertEqual(tap.call_args_list, expected)


if __name__ == '__main__':
    unittest.main()
