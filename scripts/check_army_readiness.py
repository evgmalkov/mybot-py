"""Регрессия неполной вместимости армии без подключения к эмулятору."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd()))
from paths import BASE_DIR
for layer in ('core', 'emu', 'vision', 'train', 'villages', 'ui'):
    sys.path.insert(0, str(BASE_DIR / layer))
import main
import numpy as np
import smart_train as s


class ArmyReadiness(unittest.TestCase):
    def test_housing_boundaries(self):
        for spec in s.ARMY_SETS.values():
            for used, capacity, expected in (
                (350, 352, True), (340, 340, True), (350, 350, True),
                (345, 352, False), (340, 352, False), (0, 352, False),
                (353, 352, False), (350, 3521, False), (None, 352, False),
                (350, None, False), (1, 1, False),
            ):
                with self.subTest(used=used, capacity=capacity, spec=spec['main']):
                    self.assertEqual(s._troop_space_ready(used, capacity, spec), expected)

    def test_missing_troops_still_block_attack(self):
        shot = np.zeros((900, 1600, 3), dtype=np.uint8)
        with patch.object(s, 'take_screenshot'), patch.object(s, 'imread_unicode', return_value=shot), \
                patch.object(s, '_read_fraction', return_value=(350, 352)), \
                patch.object(s, '_match', return_value=(False, 0, (0, 0))):
            self.assertFalse(s._validate_troops({'attack': 'ElectroDragon_Attack'}))

    def test_ready_army_is_not_rebuilt(self):
        # Реальные шаблоны состава, но без ADB: ошибочный повтор тренировки вызовет tap.
        shot = np.zeros((900, 1600, 3), dtype=np.uint8)
        for i, name in enumerate(('electro_dragon', 'balloon')):
            template = s.imread_unicode(str(Path(s.ARMY_TROOPS_DIR) / (name + '.png')))
            h, w = template.shape[:2]
            x, y = s.ARMY_ROI[0] + i * 200, s.ARMY_ROI[1]
            shot[y:y + h, x:x + w] = template
        with patch.object(s.digit_ocr, 'read_fraction', return_value=(350, 352)), \
                patch.object(s, 'tap') as tap, patch.object(s, '_clear_if_trash') as clear:
            s.train_troops({'attack': 'ElectroDragon_Attack'}, shot)
            tap.assert_not_called()
            clear.assert_not_called()


if __name__ == '__main__':
    unittest.main()
