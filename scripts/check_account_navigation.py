"""Проверка маршрута переключения ID без подключения к эмулятору."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, call

sys.path.insert(0, str(Path.cwd()))
from paths import BASE_DIR
for layer in ('core', 'emu', 'vision', 'train', 'villages', 'ui'):
    sys.path.insert(0, str(BASE_DIR / layer))
import main
import game_ui as ui
import ready_villages


class AccountNavigation(unittest.TestCase):
    def test_route_from_home(self):
        # Ни одного запроса к изображению или цвету ратуши.
        with patch.object(ui, 'visible', side_effect=[False, False, True]) as visible, patch.object(ui, 'wait_visible', return_value=True), patch.object(ui, 'tap_named') as tap:
            self.assertTrue(ui.open_account_switcher())
            self.assertEqual(visible.call_args_list, [call('account_settings'), call('profile_menu'), call('home')])
            self.assertEqual(tap.call_args_list, [call('player_profile'), call('profile_settings'), call('account_switch')])

    def test_missing_home(self):
        with patch.object(ui, 'visible', return_value=False), patch.object(ui, 'tap_named') as tap:
            self.assertFalse(ui.open_account_switcher())
            tap.assert_not_called()

    def test_missing_settings(self):
        with patch.object(ui, 'visible', side_effect=[False, True]), patch.object(ui, 'wait_visible', return_value=False), patch.object(ui, 'tap_named') as tap:
            self.assertFalse(ui.open_account_switcher())
            tap.assert_called_once_with('profile_settings')

    def test_failed_navigation_does_not_select_slot(self):
        with patch.object(ui, 'open_account_switcher', return_value=False), patch.object(ready_villages, 'tap') as tap:
            self.assertFalse(ready_villages.switch_to_village(1))
            tap.assert_not_called()


if __name__ == '__main__':
    unittest.main()
