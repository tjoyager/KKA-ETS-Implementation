"""Warehouse Legend HUD component.

Displays warehouse items, vehicles, terrain, locations, and exploration heatmap legend
with 1:1 natural aspect ratio, uniform fonts, and dark theme consistency.
"""
from ursina import Entity, Text, Vec3, camera, color, window
from ursina.shaders import unlit_shader
from src.communication.visual_theme import rounded_surface


class WarehouseLegend:
    BG = color.rgba32(19, 28, 35, 248)
    EDGE = color.rgba32(67, 92, 103, 220)
    LINE = color.rgba32(66, 86, 97, 150)
    TEXT = color.rgb32(234, 242, 243)
    MUTED = color.rgb32(151, 171, 181)
    CYAN = color.rgb32(93, 201, 189)
    AMBER = color.rgb32(231, 177, 101)
    GREEN = color.rgb32(130, 198, 156)
    REG = "assets/fonts/Roboto-Regular.ttf"
    BOLD = "assets/fonts/Roboto-Bold.ttf"

    ICON_ASPECTS = {
        "alpha": 1.98,
        "beta": 1.98,
        "forklift": 1.67,
        "kardus": 1.04,
        "oli": 2.19,
        "boost": 2.62,
        "charger": 1.41,
        "rak": 1.33,
        "rak_jemput": 1.76,
        "rak_antar": 1.76,
        "goal": 1.88,
        "gerbang": 1.44,
    }

    def __init__(self):
        self.container = Entity(parent=camera.ui, scale=1, enabled=True)
        self.panel_w = 0.320
        self.panel_h = 0.400
        self._last_aspect = -1.0

        # Background and borders (sibling children in z-depth behind text)
        self.bg = Entity(parent=self.container, model="quad", shader=unlit_shader, color=self.BG)
        self.edge = Entity(parent=self.container, model="quad", shader=unlit_shader, color=self.EDGE)
        self.top_rule = Entity(parent=self.container, model="quad", shader=unlit_shader, color=self.CYAN)

        # Title
        self.title = Text(
            parent=self.container,
            text="Legenda gudang",
            scale=0.56,
            color=self.TEXT,
            font=self.BOLD,
            origin=(-0.5, 0),
        )

        # Section 1: Kendaraan
        self.sec1_title = Text(
            parent=self.container,
            text="Kendaraan",
            scale=0.42,
            color=self.CYAN,
            font=self.BOLD,
            origin=(-0.5, 0),
        )
        self.sec1_rule = Entity(parent=self.container, model="quad", shader=unlit_shader, color=self.LINE)

        # Section 2: Medan & rintangan
        self.sec2_title = Text(
            parent=self.container,
            text="Medan & rintangan",
            scale=0.42,
            color=self.CYAN,
            font=self.BOLD,
            origin=(-0.5, 0),
        )
        self.sec2_rule = Entity(parent=self.container, model="quad", shader=unlit_shader, color=self.LINE)

        # Section 3: Lokasi
        self.sec3_title = Text(
            parent=self.container,
            text="Lokasi",
            scale=0.42,
            color=self.CYAN,
            font=self.BOLD,
            origin=(-0.5, 0),
        )
        self.sec3_rule = Entity(parent=self.container, model="quad", shader=unlit_shader, color=self.LINE)

        # Section 4: Petak yang dieksplorasi
        self.sec4_title = Text(
            parent=self.container,
            text="Petak yang dieksplorasi",
            scale=0.42,
            color=self.CYAN,
            font=self.BOLD,
            origin=(-0.5, 0),
        )
        self.sec4_rule = Entity(parent=self.container, model="quad", shader=unlit_shader, color=self.LINE)

        # 12 Legend item rows
        self.items_data = [
            # (sec_idx, icon_name, label_text, label_color, is_bold, desc_text)
            (1, "alpha", "Alpha · A*", self.CYAN, True, "Jejak hijau"),
            (1, "beta", "Beta · GBFS", self.AMBER, True, "Jejak merah"),
            (1, "forklift", "Forklift", self.TEXT, True, "Rintangan bergerak"),
            (2, "kardus", "Kardus [1]", self.TEXT, True, "Menutup jalur"),
            (2, "oli", "Oli [2]", self.TEXT, True, "Memperlambat"),
            (2, "boost", "Boost [3]", self.TEXT, True, "Mempercepat"),
            (3, "charger", "Charger", self.TEXT, True, "Isi daya"),
            (3, "rak", "Rak", self.TEXT, True, "Simpan kargo"),
            (3, "rak_jemput", "Rak jemput", self.TEXT, True, "Ambil kargo"),
            (3, "rak_antar", "Rak antar", self.TEXT, True, "Taruh kargo"),
            (3, "goal", "Goal station", self.TEXT, True, "Titik tujuan"),
            (3, "gerbang", "Gerbang", self.TEXT, True, "Pindah zona"),
        ]

        self.item_entities = []
        for _, icon_name, label, tint, bold, desc in self.items_data:
            icon_path = f"assets/ui/icons/{icon_name}.png"
            icon_ent = Entity(
                parent=self.container,
                model="quad",
                shader=unlit_shader,
                texture=icon_path,
                color=color.white,
            )
            label_ent = Text(
                parent=self.container,
                text=label,
                scale=0.41,
                color=tint,
                font=self.BOLD if bold else self.REG,
                origin=(-0.5, 0),
            )
            desc_ent = Text(
                parent=self.container,
                text=desc,
                scale=0.39,
                color=self.MUTED,
                font=self.REG,
                origin=(0.5, 0),
            )
            self.item_entities.append((icon_ent, label_ent, desc_ent, icon_name))

        # Exploration heatmap swatches: A*, GBFS, Keduanya
        self.swatch_a_box = Entity(
            parent=self.container,
            model="quad",
            shader=unlit_shader,
            color=color.rgb32(245, 65, 120),
        )
        self.swatch_a_txt = Text(
            parent=self.container,
            text="A*",
            scale=0.40,
            color=self.TEXT,
            font=self.BOLD,
            origin=(-0.5, 0),
        )

        self.swatch_b_box = Entity(
            parent=self.container,
            model="quad",
            shader=unlit_shader,
            color=color.rgb32(0, 205, 255),
        )
        self.swatch_b_txt = Text(
            parent=self.container,
            text="GBFS",
            scale=0.40,
            color=self.TEXT,
            font=self.BOLD,
            origin=(-0.5, 0),
        )

        self.swatch_both_box = Entity(
            parent=self.container,
            model="quad",
            shader=unlit_shader,
            color=color.rgb32(195, 75, 255),
        )
        self.swatch_both_txt = Text(
            parent=self.container,
            text="Keduanya",
            scale=0.40,
            color=self.TEXT,
            font=self.BOLD,
            origin=(-0.5, 0),
        )

        self.update_layout()

    def update_layout(self, top_y=0.043, panel_w=None):
        aspect = max(1.0, float(window.aspect_ratio))
        if panel_w is None:
            panel_w = 0.320 if aspect >= 1.55 else (0.295 if aspect >= 1.25 else 0.270)
        self.panel_w = panel_w

        w = self.panel_w
        h = self.panel_h

        # Position root container with 1:1 scale
        self.container.scale = Vec3(1, 1, 1)
        self.container.position = Vec3(-aspect / 2 + 0.018, top_y, 0)

        # Background quad as sibling child behind text
        self.bg.position = Vec3(w / 2, -h / 2, 0.036)
        self.bg.scale = Vec3(w, h, 1)
        self.bg.texture = rounded_surface(w, h)

        self.edge.position = Vec3(w / 2, -h / 2, 0.037)
        self.edge.scale = Vec3(w + 0.003, h + 0.003, 1)
        self.edge.texture = rounded_surface(w + 0.003, h + 0.003)

        left = 0.014
        inner = w - 0.028
        right_edge = left + inner

        # Top pill rule
        self.top_rule.position = Vec3(left + 0.030, -0.006, 0.018)
        self.top_rule.scale = Vec3(0.060, 0.0022, 1)

        # Title
        self.title.position = Vec3(left, -0.021, 0.012)

        # Section 1: Kendaraan
        sec1_y = -0.042
        self.sec1_title.position = Vec3(left, sec1_y, 0.012)
        sub1_end = left + 0.066
        rule1_w = max(0.02, right_edge - sub1_end - 0.004)
        self.sec1_rule.position = Vec3(sub1_end + rule1_w / 2, sec1_y, 0.018)
        self.sec1_rule.scale = Vec3(rule1_w, 0.001, 1)

        # Rows 0, 1, 2
        row_step = 0.020
        y_cursor = sec1_y - 0.021
        for idx in range(3):
            icon_ent, label_ent, desc_ent, icon_name = self.item_entities[idx]
            self._position_row(icon_ent, label_ent, desc_ent, icon_name, left, inner, y_cursor)
            y_cursor -= row_step

        # Section 2: Medan & rintangan
        sec2_y = y_cursor - 0.004
        self.sec2_title.position = Vec3(left, sec2_y, 0.012)
        sub2_end = left + 0.116
        rule2_w = max(0.02, right_edge - sub2_end - 0.004)
        self.sec2_rule.position = Vec3(sub2_end + rule2_w / 2, sec2_y, 0.018)
        self.sec2_rule.scale = Vec3(rule2_w, 0.001, 1)

        # Rows 3, 4, 5
        y_cursor = sec2_y - 0.021
        for idx in range(3, 6):
            icon_ent, label_ent, desc_ent, icon_name = self.item_entities[idx]
            self._position_row(icon_ent, label_ent, desc_ent, icon_name, left, inner, y_cursor)
            y_cursor -= row_step

        # Section 3: Lokasi
        sec3_y = y_cursor - 0.004
        self.sec3_title.position = Vec3(left, sec3_y, 0.012)
        sub3_end = left + 0.046
        rule3_w = max(0.02, right_edge - sub3_end - 0.004)
        self.sec3_rule.position = Vec3(sub3_end + rule3_w / 2, sec3_y, 0.018)
        self.sec3_rule.scale = Vec3(rule3_w, 0.001, 1)

        # Rows 6 to 11
        y_cursor = sec3_y - 0.021
        for idx in range(6, 12):
            icon_ent, label_ent, desc_ent, icon_name = self.item_entities[idx]
            self._position_row(icon_ent, label_ent, desc_ent, icon_name, left, inner, y_cursor)
            y_cursor -= row_step

        # Section 4: Petak yang dieksplorasi
        sec4_y = y_cursor - 0.004
        self.sec4_title.position = Vec3(left, sec4_y, 0.012)
        sub4_end = left + 0.144
        rule4_w = max(0.02, right_edge - sub4_end - 0.004)
        self.sec4_rule.position = Vec3(sub4_end + rule4_w / 2, sec4_y, 0.018)
        self.sec4_rule.scale = Vec3(rule4_w, 0.001, 1)

        # Swatches row
        swatch_y = sec4_y - 0.021
        box_sz = 0.009

        # A* swatch
        self.swatch_a_box.position = Vec3(left + 0.006, swatch_y, 0.015)
        self.swatch_a_box.scale = Vec3(box_sz, box_sz, 1)
        self.swatch_a_txt.position = Vec3(left + 0.016, swatch_y, 0.012)

        # GBFS swatch
        gbfs_x = left + inner * 0.32
        self.swatch_b_box.position = Vec3(gbfs_x + 0.006, swatch_y, 0.015)
        self.swatch_b_box.scale = Vec3(box_sz, box_sz, 1)
        self.swatch_b_txt.position = Vec3(gbfs_x + 0.016, swatch_y, 0.012)

        # Keduanya swatch
        both_x = left + inner * 0.64
        self.swatch_both_box.position = Vec3(both_x + 0.006, swatch_y, 0.015)
        self.swatch_both_box.scale = Vec3(box_sz, box_sz, 1)
        self.swatch_both_txt.position = Vec3(both_x + 0.016, swatch_y, 0.012)

    def _position_row(self, icon_ent, label_ent, desc_ent, icon_name, left, inner, y):
        aspect = self.ICON_ASPECTS.get(icon_name, 1.5)
        max_w = 0.022
        max_h = 0.012
        if max_w / aspect <= max_h:
            icon_w = max_w
            icon_h = icon_w / aspect
        else:
            icon_h = max_h
            icon_w = icon_h * aspect

        icon_center_x = left + 0.011
        icon_ent.position = Vec3(icon_center_x, y, 0.015)
        icon_ent.scale = Vec3(icon_w, icon_h, 1)

        label_ent.position = Vec3(left + 0.025, y, 0.012)
        desc_ent.position = Vec3(left + inner, y, 0.012)

    def set_visible(self, visible: bool):
        self.container.enabled = visible
