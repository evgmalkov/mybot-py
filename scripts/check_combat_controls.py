"""Регрессии боевого управления без подключения к эмулятору. Запуск из корня."""
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd()))
from paths import BASE_DIR
for layer in ('core', 'emu', 'vision', 'train', 'villages', 'ui'):
    sys.path.insert(0, str(BASE_DIR / layer))
import main
import cv2
import numpy as np
from attacks import attacks as a


class CombatControls(unittest.TestCase):
    def setUp(self):
        self.shot = np.zeros((900, 1600, 3), dtype=np.uint8)
        a.TABS = {'rc': (797, 790)}
        a._deployed_at = {'rc': time.time() - 5}
        a._hero_last_activate.clear()
        a._hero_dead_count.clear()
        a._hero_monitor_done = False
        a._deploy_phase = False

    def test_health_colors_and_empty(self):
        # BGR заливки из живых кадров: жёлтая и красная не означают смерть.
        for color in ((20, 220, 80), (20, 146, 220), (6, 17, 255)):
            self.shot[:] = 0
            self.shot[718:724, 751:774] = color
            self.assertAlmostEqual(a._hero_hp_fraction(self.shot, 797, a._load_hero_cfg()), .25)
        self.shot[:] = 0
        self.assertEqual(a._hero_hp_fraction(self.shot, 797, a._load_hero_cfg()), 0)

    def test_activation_guards(self):
        with patch.object(a, 'run_adb', return_value=True) as tap, patch.object(a, 'human_delay'), patch.object(a, '_hero_hp_fraction', return_value=.16):
            a.monitor_hero_hp(self.shot)
            a.monitor_hero_hp(self.shot)
            self.assertEqual(tap.call_count, 1)
            a._hero_last_activate.clear()
            a._hero_monitor_done = False
            a._deployed_at.clear()
            a.monitor_hero_hp(self.shot)
            self.assertEqual(tap.call_count, 1)

    def test_timer_and_dead_hero(self):
        a._deployed_at['rc'] = time.time() - 30
        with patch.object(a, 'run_adb', return_value=True) as tap, patch.object(a, 'human_delay'):
            with patch.object(a, '_hero_hp_fraction', return_value=.95):
                a.monitor_hero_hp(self.shot)
            self.assertEqual(tap.call_count, 1)
            a._hero_last_activate.clear()
            a._hero_monitor_done = False
            with patch.object(a, '_hero_hp_fraction', return_value=0):
                a.monitor_hero_hp(self.shot)
            self.assertEqual(tap.call_count, 1)

    def test_rightmost_slot_and_dark_background(self):
        self.shot[745:835] = (0, 50, 0)
        self.shot[745:835, 1400:1500] = (0, 220, 0)
        self.assertEqual(a._colored_slot_centers(self.shot), [1450])

    def test_monitor_after_speed_up(self):
        with patch.object(a, 'capture_array', return_value=self.shot), patch.object(a, '_ensure_active'), patch.object(a, '_sync_tab_positions'), patch.object(a, '_handle_connection_lost', return_value=False), patch('game_ui.visible', return_value=False), patch.object(a, 'monitor_hero_hp') as hp, patch.object(a, '_maybe_deploy_all_heroes'), patch.object(a, '_speed_button_position', side_effect=[None, (1535, 439), (1535, 439)]), patch.object(a, 'run_adb', return_value=True) as tap, patch.object(a, 'human_delay'), patch.object(main, 'battle_ended', side_effect=[False, False, True]):
            a.speed_up()
            self.assertEqual(hp.call_count, 3)
            self.assertEqual(tap.call_count, 1)

    def test_speed_button_localization(self):
        tpl = cv2.imread(str(BASE_DIR / 'Templates' / 'speed_button_1x.png'))
        h, w = tpl.shape[:2]
        self.assertIsNone(a._speed_button_position(self.shot))
        # Кнопка сместилась внутри области поиска: тап обязан следовать за ней.
        self.shot[425:425+h, 1510:1510+w] = tpl
        self.assertEqual(a._speed_button_position(self.shot), (1510+w//2, 425+h//2))


if __name__ == '__main__':
    unittest.main()
