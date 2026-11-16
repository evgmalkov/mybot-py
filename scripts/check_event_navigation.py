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
import ensure_home_base as home
import boot_recovery as recovery
import numpy as np


class EventNavigation(unittest.TestCase):
    def test_pending_treasure_uses_reward_handler(self):
        with patch.object(main, '_check_stop', return_value=False), \
                patch.object(ui, 'treasure_reward_visible', return_value=True), \
                patch.object(ui, 'collect_treasure_rewards', return_value=True) as collect:
            self.assertTrue(ui.dismiss_pending_rewards())
            collect.assert_called_once()

    def test_pending_legacy_cards_are_processed(self):
        with patch.object(main, '_check_stop', return_value=False), \
                patch.object(ui, 'treasure_reward_visible', return_value=False), \
                patch.object(main, 'event_reward_present', side_effect=[True, False]), \
                patch.object(main, 'claim_event_cards') as collect:
            self.assertTrue(ui.dismiss_pending_rewards())
            collect.assert_called_once()

    def test_home_handles_delayed_reward_before_detection(self):
        actions = []
        with patch.object(ui, 'dismiss_welcome'), \
                patch.object(ui, 'dismiss_pending_rewards', side_effect=lambda: actions.append('reward') or True), \
                patch.object(home, 'detect_home_base', side_effect=lambda: actions.append('home') or actions.count('home') == 2), \
                patch.object(main.stop_event, 'wait', return_value=False), \
                patch.object(main, '_check_stop', return_value=False), patch.object(home, 'boot_recovery') as reboot:
            self.assertTrue(home.ensure_home_base())
            self.assertEqual(actions, ['reward', 'home', 'reward', 'home'])
            reboot.assert_not_called()

    def test_failed_reward_does_not_restart_game(self):
        with patch.object(ui, 'dismiss_welcome'), patch.object(ui, 'dismiss_pending_rewards', return_value=False), \
                patch.object(main, '_check_stop', return_value=False), patch.object(home, 'boot_recovery') as reboot:
            self.assertFalse(home.ensure_home_base())
            reboot.assert_not_called()

    def test_unknown_screen_has_bounded_restarts(self):
        with patch.object(home, 'boot_recovery', return_value=True) as reboot:
            self.assertFalse(home.ensure_home_base(max_wait=0))
            self.assertEqual(reboot.call_count, ui.UI['home_recovery']['max_restarts'])

    def test_recovery_cannot_reenter_itself(self):
        with patch.object(main, '_check_stop', return_value=False), \
                patch.object(recovery, '_boot_recovery', side_effect=recovery.boot_recovery) as restart:
            self.assertFalse(recovery.boot_recovery())
            restart.assert_called_once()
            self.assertFalse(recovery._recovering)

    def test_restart_processes_pending_rewards(self):
        with patch.object(main, 'host', 'test-device'), patch.object(main, '_check_stop', return_value=False), \
                patch.object(recovery, '_device_online', return_value=True), \
                patch.object(recovery, '_screencap_alive', return_value=True), \
                patch.object(recovery.subprocess, 'run'), patch('app_launch.launch_app'), \
                patch.object(main, 'rsleep'), patch.object(ui, 'dismiss_welcome'), \
                patch.object(ui, 'dismiss_pending_rewards', return_value=True) as rewards:
            self.assertTrue(recovery.boot_recovery())
            rewards.assert_called_once()

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
