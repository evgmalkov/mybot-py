"""MyBotPy — точка расширения (ваши правки живут здесь).

Стратегию атаки задают три места: меню GUI (bot_gui.MainWindow.attack_map),
наборы армии (smart_train.ARMY_SETS) и сама логика (attacks/attacks.py). Первые
два расширяются в рантайме отсюда — без правки самих модулей:

    bot_gui.MainWindow.attack_map   -- что предлагает выпадающий список GUI
    smart_train.ARMY_SETS           -- что тренируется под каждую стратегию

run_from_source.py импортирует этот модуль автоматически. Чтобы добавить стратегию:

    1. an entry in NEW_ARMY_SETS below
    2. an entry in NEW_ATTACK_CHOICES below
    3. a _my_sequence() function + an elif in run_attack() in attacks/attacks.py
    4. attacks/<Internal_Name>.txt   -- description shown in the GUI
       attacks/<Internal_Name>.png   -- preview image shown in the GUI
    5. Templates/Smart_Auto_train/to_train/<troop>.png for any troop not
       already covered (existing: balloon, dragon, electro_dragon, freeze,
       rage, slammer)
"""

# ── new army compositions ────────────────────────────────────────────────
# 'main' drives the army-space maths, so it also needs a SPACE_COST entry.
NEW_ARMY_SETS = {
    # "Duke_Attack": {
    #     "main":   "dragon",
    #     "troops": ["dragon", "balloon"],
    #     "spells": ["rage", "freeze"],
    #     "siege":  "slammer",
    # },
}

# housing space per unit — only needed for troops not already known
# (dragon 20, electro_dragon 30, balloon 5) and spells (rage 2, freeze 1)
NEW_SPACE_COST: dict[str, int] = {}
NEW_SPELL_COST: dict[str, int] = {}

# ── new GUI dropdown entries ─────────────────────────────────────────────
# "Label in the dropdown": "Internal_Name"
NEW_ATTACK_CHOICES = {
    # "Duke Attack": "Duke_Attack",
}


def apply():
    import smart_train

    smart_train.ARMY_SETS.update(NEW_ARMY_SETS)
    smart_train.SPACE_COST.update(NEW_SPACE_COST)
    smart_train.SPELL_COST.update(NEW_SPELL_COST)

    # #7 стратегии MyBot-MBR из strategies/*.csv — в выпадающий список атак.
    # Метка «[CSV] имя» → внутреннее «csv:имя» (роутится в attacks.run_attack).
    try:
        import mbr_csv
        for _name in mbr_csv.list_strategies():
            NEW_ATTACK_CHOICES[f"[CSV] {_name}"] = f"csv:{_name}"
    except Exception as _e:
        print(f"[mods] failed to load CSV strategies: {_e}")

    if not NEW_ATTACK_CHOICES:
        return

    import bot_gui

    original_init = bot_gui.MainWindow.__init__

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        for label, internal in NEW_ATTACK_CHOICES.items():
            if label in self.attack_map:
                continue
            self.attack_map[label] = internal
            self.attack_combo.addItem(label)

    bot_gui.MainWindow.__init__ = __init__
