"""
Rotation Matrices & Fuel Water Line Visualization
===================================================
Manim scenes illustrating aircraft body-fixed rotations, how pitch/roll
affect fuel probe readings, and the bilinear interpolation scheme used in
fuel_vol_tank_combo.m (04_matlab_models/).

Render any scene with:
    manim -pql rotation_waterline.py <SceneName>
"""

from manim import *
import numpy as np

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
C_RED = "#E74C3C"
C_GREEN = "#2ECC71"
C_BLUE = "#3498DB"
C_GOLD = "#F1C40F"
C_PURPLE = "#9B59B6"
C_ORANGE = "#E67E22"
C_TEAL = "#1ABC9C"
C_FUEL = "#2980B9"
C_FUEL_FILL = "#85C1E9"
C_TANK = "#7F8C8D"
C_GRID = "#BDC3C7"

# ---------------------------------------------------------------------------
# Helper: rotation matrices (standard aerospace body-fixed)
# ---------------------------------------------------------------------------

def Rx(phi):
    """Roll rotation about X-axis."""
    c, s = np.cos(phi), np.sin(phi)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(theta):
    """Pitch rotation about Y-axis."""
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(psi):
    """Yaw rotation about Z-axis."""
    c, s = np.cos(psi), np.sin(psi)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Scene 1 — Aircraft Coordinate System                                 ║
# ╚═════════════════════════════════════════════════════════════════════════╝

class AircraftCoordinateSystem(ThreeDScene):
    """3D body-fixed axes with a simplified aircraft shape."""

    def construct(self):
        self.set_camera_orientation(phi=70 * DEGREES, theta=-45 * DEGREES)

        # --- Axes -----------------------------------------------------------
        ax_len = 3.0
        x_arrow = Arrow3D(ORIGIN, ax_len * RIGHT, color=C_RED)
        y_arrow = Arrow3D(ORIGIN, ax_len * UP, color=C_GREEN)
        z_arrow = Arrow3D(ORIGIN, ax_len * OUT, color=C_BLUE)

        x_label = Text("X (fwd)", font_size=28, color=C_RED).move_to(
            ax_len * RIGHT + 0.5 * RIGHT
        )
        y_label = Text("Y (stbd)", font_size=28, color=C_GREEN).move_to(
            ax_len * UP + 0.5 * UP
        )
        z_label = Text("Z (down)", font_size=28, color=C_BLUE).move_to(
            ax_len * OUT + 0.5 * OUT
        )

        self.add_fixed_in_frame_mobjects(x_label, y_label, z_label)
        self.remove(x_label, y_label, z_label)

        # --- Aircraft shape -------------------------------------------------
        fuselage = Prism(dimensions=[3.0, 0.5, 0.5]).set_color(C_TANK).set_opacity(0.6)
        wings = Prism(dimensions=[0.6, 3.0, 0.1]).set_color(C_GRID).set_opacity(0.5)
        tail = Prism(dimensions=[0.1, 0.5, 0.6]).shift(1.4 * LEFT + 0.25 * OUT).set_color(C_GRID).set_opacity(0.5)
        aircraft = VGroup(fuselage, wings, tail)

        # --- Title -----------------------------------------------------------
        title = Text("Body-Fixed Coordinate System", font_size=36).to_edge(UP)
        self.add_fixed_in_frame_mobjects(title)

        # --- Animate ---------------------------------------------------------
        self.play(Create(x_arrow), Create(y_arrow), Create(z_arrow), run_time=1.5)
        self.play(FadeIn(x_label), FadeIn(y_label), FadeIn(z_label), run_time=1)
        self.play(FadeIn(aircraft), run_time=1.5)

        # Convention note
        note = Text(
            "Right-hand rule · X fwd · Y starboard · Z down",
            font_size=22,
            color=C_GOLD,
        ).to_edge(DOWN)
        self.add_fixed_in_frame_mobjects(note)
        self.play(FadeIn(note))

        # Slow ambient rotation
        self.begin_ambient_camera_rotation(rate=0.15)
        self.wait(6)
        self.stop_ambient_camera_rotation()
        self.wait(0.5)


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Scene 2 — Rotation Matrices                                          ║
# ╚═════════════════════════════════════════════════════════════════════════╝

class RotationMatrices(Scene):
    """Display the three fundamental rotation matrices with color-coded angles."""

    def construct(self):
        title = Text("Fundamental Rotation Matrices", font_size=40).to_edge(UP)

        # Roll — Rx(phi)
        roll_label = MathTex(
            r"R_x(\phi)", r"\;=\;", font_size=38
        ).set_color_by_tex(r"\phi", C_RED)
        roll_mat = MathTex(
            r"\begin{bmatrix}"
            r"1 & 0 & 0 \\"
            r"0 & \cos\phi & -\sin\phi \\"
            r"0 & \sin\phi & \cos\phi"
            r"\end{bmatrix}",
            font_size=38,
        )
        roll_mat.set_color_by_tex(r"\phi", C_RED)
        roll_row = VGroup(roll_label, roll_mat).arrange(RIGHT, buff=0.2)

        roll_desc = Text("Roll", font_size=26, color=C_RED)

        # Pitch — Ry(theta)
        pitch_label = MathTex(
            r"R_y(\theta)", r"\;=\;", font_size=38
        ).set_color_by_tex(r"\theta", C_GREEN)
        pitch_mat = MathTex(
            r"\begin{bmatrix}"
            r"\cos\theta & 0 & \sin\theta \\"
            r"0 & 1 & 0 \\"
            r"-\sin\theta & 0 & \cos\theta"
            r"\end{bmatrix}",
            font_size=38,
        )
        pitch_mat.set_color_by_tex(r"\theta", C_GREEN)
        pitch_row = VGroup(pitch_label, pitch_mat).arrange(RIGHT, buff=0.2)

        pitch_desc = Text("Pitch", font_size=26, color=C_GREEN)

        # Yaw — Rz(psi)
        yaw_label = MathTex(
            r"R_z(\psi)", r"\;=\;", font_size=38
        ).set_color_by_tex(r"\psi", C_BLUE)
        yaw_mat = MathTex(
            r"\begin{bmatrix}"
            r"\cos\psi & -\sin\psi & 0 \\"
            r"\sin\psi & \cos\psi & 0 \\"
            r"0 & 0 & 1"
            r"\end{bmatrix}",
            font_size=38,
        )
        yaw_mat.set_color_by_tex(r"\psi", C_BLUE)
        yaw_row = VGroup(yaw_label, yaw_mat).arrange(RIGHT, buff=0.2)

        yaw_desc = Text("Yaw", font_size=26, color=C_BLUE)

        # Stack vertically
        rows = VGroup(
            VGroup(roll_desc, roll_row).arrange(RIGHT, buff=0.6),
            VGroup(pitch_desc, pitch_row).arrange(RIGHT, buff=0.5),
            VGroup(yaw_desc, yaw_row).arrange(RIGHT, buff=0.55),
        ).arrange(DOWN, buff=0.7).next_to(title, DOWN, buff=0.5)

        # Animate sequentially
        self.play(Write(title))
        for row in rows:
            self.play(FadeIn(row, shift=RIGHT * 0.3), run_time=1.2)
            self.wait(0.4)

        self.wait(2)


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Scene 3 — Combined Rotation                                          ║
# ╚═════════════════════════════════════════════════════════════════════════╝

class CombinedRotation(ThreeDScene):
    """Show composition R = Rz·Ry·Rx simplified to R_tank = Ry(θ)·Rx(φ),
    then animate pitch and roll on a semi-transparent tank prism."""

    def construct(self):
        self.set_camera_orientation(phi=65 * DEGREES, theta=-50 * DEGREES)

        # --- Equation (fixed in frame) --------------------------------------
        eq_full = MathTex(
            r"R", r"=", r"R_z(\psi)", r"\cdot", r"R_y(\theta)", r"\cdot", r"R_x(\phi)",
            font_size=36,
        )
        eq_full.set_color_by_tex(r"\psi", C_BLUE)
        eq_full.set_color_by_tex(r"\theta", C_GREEN)
        eq_full.set_color_by_tex(r"\phi", C_RED)
        eq_full.to_corner(UL)

        eq_tank = MathTex(
            r"R_{\mathrm{tank}}", r"=", r"R_y(\theta)", r"\cdot", r"R_x(\phi)",
            r"\quad (\psi = 0)",
            font_size=36,
        )
        eq_tank.set_color_by_tex(r"\theta", C_GREEN)
        eq_tank.set_color_by_tex(r"\phi", C_RED)
        eq_tank.set_color_by_tex(r"\psi", C_BLUE)
        eq_tank.next_to(eq_full, DOWN, aligned_edge=LEFT, buff=0.3)

        self.add_fixed_in_frame_mobjects(eq_full, eq_tank)
        self.remove(eq_full, eq_tank)

        # --- Tank prism (original — ghost) -----------------------------------
        tank_ghost = Prism(dimensions=[2.5, 1.5, 1.0])
        tank_ghost.set_color(C_TANK)
        tank_ghost.set_opacity(0.15)
        tank_ghost.set_stroke(color=C_TANK, width=1, opacity=0.6)

        # --- Tank prism (rotated) --------------------------------------------
        tank = Prism(dimensions=[2.5, 1.5, 1.0])
        tank.set_color(C_FUEL)
        tank.set_opacity(0.45)

        # --- Angle labels (fixed in frame) -----------------------------------
        pitch_text = MathTex(r"\theta = 5°", font_size=30, color=C_GREEN).to_corner(DR)
        roll_text = MathTex(r"\phi = 15°", font_size=30, color=C_RED).next_to(
            pitch_text, UP, buff=0.25
        )
        self.add_fixed_in_frame_mobjects(pitch_text, roll_text)
        self.remove(pitch_text, roll_text)

        # --- Animate ---------------------------------------------------------
        self.play(FadeIn(tank_ghost), FadeIn(tank), run_time=1)
        self.play(Write(eq_full), run_time=1.2)
        self.wait(0.5)
        self.play(Write(eq_tank), run_time=1.2)
        self.wait(0.5)

        # Apply roll (15°) then pitch (5°)
        phi = 15 * DEGREES
        theta = 5 * DEGREES

        self.play(
            Rotate(tank, angle=phi, axis=RIGHT, about_point=ORIGIN),
            FadeIn(roll_text),
            run_time=2,
        )
        self.wait(0.3)
        self.play(
            Rotate(tank, angle=theta, axis=UP, about_point=ORIGIN),
            FadeIn(pitch_text),
            run_time=2,
        )

        self.begin_ambient_camera_rotation(rate=0.12)
        self.wait(5)
        self.stop_ambient_camera_rotation()
        self.wait(0.5)


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Scene 4 — Fuel Water Line (key scene)                                ║
# ╚═════════════════════════════════════════════════════════════════════════╝

class FuelWaterLine(Scene):
    """Rectangular tank cross-section with animated tilting fuel surface
    as pitch changes, showing probe height measurement."""

    def construct(self):
        title = Text("Fuel Water Line & Probe Height", font_size=36).to_edge(UP)
        self.play(Write(title))

        # --- Parameters ------------------------------------------------------
        tank_w = 6.0        # tank width (x-direction)
        tank_h = 3.5        # tank height
        base_fill = 0.60    # 60 % fill fraction
        h0 = base_fill * tank_h   # static fuel height
        probe_x_frac = 0.3  # probe at 30 % from left edge
        probe_x = -tank_w / 2 + probe_x_frac * tank_w  # x-coord of probe

        tank_origin = DOWN * 0.3  # shift everything down slightly

        # ValueTracker for pitch angle in degrees
        pitch_deg = ValueTracker(0)

        # --- Tank outline ----------------------------------------------------
        tank_rect = Rectangle(
            width=tank_w, height=tank_h,
            stroke_color=C_TANK, stroke_width=3, fill_opacity=0,
        ).move_to(tank_origin)

        # Tank labels
        tank_label = Text("Tank cross-section", font_size=20, color=C_TANK).next_to(
            tank_rect, DOWN, buff=0.15
        )

        # --- Fuel polygon (always_redraw) ------------------------------------
        def get_fuel_polygon():
            theta = pitch_deg.get_value() * DEGREES
            # Fuel surface tilts: h(x) = h0 + x * tan(theta)
            # x measured from tank center
            left_x = -tank_w / 2
            right_x = tank_w / 2
            left_h = h0 + left_x * np.tan(theta)
            right_h = h0 + right_x * np.tan(theta)

            # Clamp to tank bounds
            left_h = np.clip(left_h, 0, tank_h)
            right_h = np.clip(right_h, 0, tank_h)

            # Corners: bottom-left, bottom-right, top-right(fuel), top-left(fuel)
            bl = tank_origin + np.array([-tank_w / 2, -tank_h / 2, 0])
            br = tank_origin + np.array([tank_w / 2, -tank_h / 2, 0])
            tr = tank_origin + np.array([tank_w / 2, -tank_h / 2 + right_h, 0])
            tl = tank_origin + np.array([-tank_w / 2, -tank_h / 2 + left_h, 0])

            return Polygon(
                bl, br, tr, tl,
                fill_color=C_FUEL_FILL, fill_opacity=0.55,
                stroke_color=C_FUEL, stroke_width=2,
            )

        fuel = always_redraw(get_fuel_polygon)

        # --- Probe line (dashed) ---------------------------------------------
        def get_probe_group():
            theta = pitch_deg.get_value() * DEGREES
            h_at_probe = h0 + probe_x * np.tan(theta)
            h_at_probe = np.clip(h_at_probe, 0, tank_h)

            base_y = tank_origin[1] - tank_h / 2
            top_y = tank_origin[1] + tank_h / 2

            probe_line = DashedLine(
                start=np.array([probe_x, base_y, 0]),
                end=np.array([probe_x, top_y, 0]),
                color=C_ORANGE, stroke_width=2, dash_length=0.1,
            )

            # Measurement arrow from tank bottom to fuel surface at probe
            fuel_y = base_y + h_at_probe
            arrow = DoubleArrow(
                start=np.array([probe_x + 0.25, base_y, 0]),
                end=np.array([probe_x + 0.25, fuel_y, 0]),
                color=C_GOLD, stroke_width=2, tip_length=0.15,
                buff=0,
            )

            return VGroup(probe_line, arrow)

        probe_group = always_redraw(get_probe_group)

        # --- Probe reading (DecimalNumber) -----------------------------------
        probe_reading = always_redraw(
            lambda: DecimalNumber(
                h0 + probe_x * np.tan(pitch_deg.get_value() * DEGREES),
                num_decimal_places=2,
                font_size=30,
                color=C_GOLD,
            ).next_to(
                np.array([probe_x + 0.7, tank_origin[1] - 0.2, 0]), RIGHT, buff=0.15
            )
        )

        probe_label = always_redraw(
            lambda: MathTex(r"h_{\mathrm{probe}} =", font_size=30, color=C_GOLD).next_to(
                probe_reading, LEFT, buff=0.1
            )
        )

        probe_tag = Text("Probe", font_size=18, color=C_ORANGE).next_to(
            np.array([probe_x, tank_origin[1] + tank_h / 2, 0]), UP, buff=0.1
        )

        # --- Equation --------------------------------------------------------
        equation = MathTex(
            r"h_{\mathrm{probe}}", r"=", r"h_0", r"+", r"x", r"\cdot", r"\tan(\theta)",
            font_size=34,
        )
        equation.set_color_by_tex(r"h_0", C_FUEL)
        equation.set_color_by_tex(r"\theta", C_GREEN)
        equation.set_color_by_tex(r"h_{\mathrm{probe}}", C_GOLD)
        equation.to_edge(DOWN, buff=0.4)

        # --- Pitch readout ---------------------------------------------------
        pitch_readout = always_redraw(
            lambda: MathTex(
                r"\theta = " + f"{pitch_deg.get_value():.1f}" + r"°",
                font_size=30,
                color=C_GREEN,
            ).to_corner(UR, buff=0.5)
        )

        # --- Explanation text ------------------------------------------------
        explain = Text(
            "As pitch changes, the fuel surface tilts\n"
            "and the probe reads a different height.",
            font_size=20,
            color=GREY_B,
            line_spacing=1.2,
        ).next_to(equation, UP, buff=0.3)

        # --- Build scene -----------------------------------------------------
        self.play(FadeIn(tank_rect), FadeIn(tank_label), run_time=0.8)
        self.play(FadeIn(fuel), run_time=0.8)
        self.play(
            FadeIn(probe_group), FadeIn(probe_tag),
            FadeIn(probe_reading), FadeIn(probe_label),
            run_time=1,
        )
        self.play(Write(equation), FadeIn(explain), FadeIn(pitch_readout), run_time=1.2)
        self.wait(0.5)

        # --- Animate pitch 0 → 8° -------------------------------------------
        self.play(pitch_deg.animate.set_value(8), run_time=4, rate_func=smooth)
        self.wait(1)

        # Sweep back
        self.play(pitch_deg.animate.set_value(-4), run_time=3, rate_func=smooth)
        self.wait(0.5)
        self.play(pitch_deg.animate.set_value(0), run_time=2, rate_func=smooth)
        self.wait(1)

        # --- Why interpolation is needed ------------------------------------
        why_text = Text(
            "Real tanks are complex shapes → bilinear interpolation needed",
            font_size=22,
            color=C_TEAL,
        ).to_edge(DOWN, buff=0.15)
        self.play(FadeOut(equation), FadeOut(explain))
        self.play(FadeIn(why_text))
        self.wait(2)


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Scene 5 — Interpolation Grid                                         ║
# ╚═════════════════════════════════════════════════════════════════════════╝

class InterpolationGrid(Scene):
    """Visualize the bilinear interpolation scheme from fuel_vol_tank_combo.m.
    A query point moves within a grid cell while corner weights update live."""

    def construct(self):
        title = Text("Bilinear Interpolation Grid", font_size=36).to_edge(UP)
        self.play(Write(title))

        # --- Axes: Pitch vs Roll --------------------------------------------
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-15, 15, 5],
            x_length=6,
            y_length=5,
            axis_config={"include_numbers": True, "font_size": 22},
            x_axis_config={"numbers_to_include": list(range(-3, 4))},
            y_axis_config={"numbers_to_include": list(range(-15, 20, 5))},
        ).shift(LEFT * 1.2 + DOWN * 0.2)

        x_lab = axes.get_x_axis_label(
            MathTex(r"\theta\;(°)", font_size=28, color=C_GREEN), edge=DOWN, direction=DOWN
        )
        y_lab = axes.get_y_axis_label(
            MathTex(r"\phi\;(°)", font_size=28, color=C_RED), edge=LEFT, direction=LEFT
        )

        self.play(Create(axes), FadeIn(x_lab), FadeIn(y_lab), run_time=1.2)

        # --- Grid dots -------------------------------------------------------
        pitch_vals = list(range(-3, 4))
        roll_vals = list(range(-15, 20, 5))
        grid_dots = VGroup()
        for p in pitch_vals:
            for r in roll_vals:
                dot = Dot(axes.c2p(p, r), radius=0.04, color=C_GRID)
                grid_dots.add(dot)

        self.play(FadeIn(grid_dots), run_time=0.8)

        # --- Highlight one cell: pitch [0,1], roll [0,5] --------------------
        cell_bl = axes.c2p(0, 0)
        cell_br = axes.c2p(1, 0)
        cell_tl = axes.c2p(0, 5)
        cell_tr = axes.c2p(1, 5)

        cell_rect = Polygon(
            cell_bl, cell_br, cell_tr, cell_tl,
            stroke_color=C_GOLD, stroke_width=2.5, fill_color=C_GOLD, fill_opacity=0.1,
        )
        self.play(Create(cell_rect), run_time=0.8)

        # --- Corner dots (will scale with weight) ----------------------------
        # Corners: f11 = (0,0), f21 = (1,0), f12 = (0,5), f22 = (1,5)
        corner_positions = {
            "f11": axes.c2p(0, 0),
            "f21": axes.c2p(1, 0),
            "f12": axes.c2p(0, 5),
            "f22": axes.c2p(1, 5),
        }
        corner_labels_text = {
            "f11": r"f_{11}",
            "f21": r"f_{21}",
            "f12": r"f_{12}",
            "f22": r"f_{22}",
        }
        corner_label_dirs = {
            "f11": DL,
            "f21": DR,
            "f12": UL,
            "f22": UR,
        }

        # ValueTrackers for query point position (normalised 0-1 within cell)
        w_theta = ValueTracker(0.3)   # weight along pitch axis
        w_phi = ValueTracker(0.4)     # weight along roll axis

        # Query point
        query_dot = always_redraw(
            lambda: Dot(
                axes.c2p(
                    0 + w_theta.get_value() * 1,
                    0 + w_phi.get_value() * 5,
                ),
                radius=0.1,
                color=C_RED,
            )
        )

        # Corner dots that scale with their bilinear weight
        def make_corner_dot(key, w_t_func, w_p_func):
            def updater():
                wt = w_t_func()
                wp = w_p_func()
                radius = max(0.05, 0.22 * wt * wp + 0.04)
                return Dot(
                    corner_positions[key],
                    radius=radius,
                    color=C_PURPLE,
                )
            return always_redraw(updater)

        # Weight functions for each corner
        cdots = {
            "f11": make_corner_dot(
                "f11",
                lambda: 1 - w_theta.get_value(),
                lambda: 1 - w_phi.get_value(),
            ),
            "f21": make_corner_dot(
                "f21",
                lambda: w_theta.get_value(),
                lambda: 1 - w_phi.get_value(),
            ),
            "f12": make_corner_dot(
                "f12",
                lambda: 1 - w_theta.get_value(),
                lambda: w_phi.get_value(),
            ),
            "f22": make_corner_dot(
                "f22",
                lambda: w_theta.get_value(),
                lambda: w_phi.get_value(),
            ),
        }

        corner_labels = {}
        for key in corner_positions:
            lab = MathTex(corner_labels_text[key], font_size=24, color=C_PURPLE).next_to(
                corner_positions[key], corner_label_dirs[key], buff=0.12
            )
            corner_labels[key] = lab

        self.play(
            *[FadeIn(d) for d in cdots.values()],
            *[FadeIn(l) for l in corner_labels.values()],
            FadeIn(query_dot),
            run_time=1,
        )

        # --- Live weight readouts (right panel) ------------------------------
        def weight_display():
            wt = w_theta.get_value()
            wp = w_phi.get_value()
            lines = VGroup(
                MathTex(
                    r"w_\theta = " + f"{wt:.2f}",
                    font_size=26, color=C_GREEN,
                ),
                MathTex(
                    r"w_\phi = " + f"{wp:.2f}",
                    font_size=26, color=C_RED,
                ),
                MathTex(
                    r"(1{-}w_\theta)(1{-}w_\phi) = " + f"{(1-wt)*(1-wp):.3f}",
                    font_size=22, color=WHITE,
                ),
                MathTex(
                    r"w_\theta(1{-}w_\phi) = " + f"{wt*(1-wp):.3f}",
                    font_size=22, color=WHITE,
                ),
                MathTex(
                    r"(1{-}w_\theta)\,w_\phi = " + f"{(1-wt)*wp:.3f}",
                    font_size=22, color=WHITE,
                ),
                MathTex(
                    r"w_\theta\,w_\phi = " + f"{wt*wp:.3f}",
                    font_size=22, color=WHITE,
                ),
            ).arrange(DOWN, aligned_edge=LEFT, buff=0.18).to_corner(UR, buff=0.4).shift(DOWN * 0.5)
            return lines

        weight_panel = always_redraw(weight_display)
        self.play(FadeIn(weight_panel), run_time=0.6)

        # --- Bilinear formula (bottom) ---------------------------------------
        formula = MathTex(
            r"f(\theta,\phi) = ",
            r"(1{-}w_\theta)(1{-}w_\phi)\,f_{11}",
            r"+ w_\theta(1{-}w_\phi)\,f_{21}",
            r"+ (1{-}w_\theta)\,w_\phi\,f_{12}",
            r"+ w_\theta\,w_\phi\,f_{22}",
            font_size=24,
        ).to_edge(DOWN, buff=0.35)
        self.play(Write(formula), run_time=1.5)
        self.wait(0.5)

        # --- Animate query point moving around the cell ----------------------
        self.play(
            w_theta.animate.set_value(0.8),
            w_phi.animate.set_value(0.2),
            run_time=3,
            rate_func=smooth,
        )
        self.wait(0.5)

        self.play(
            w_theta.animate.set_value(0.1),
            w_phi.animate.set_value(0.9),
            run_time=3,
            rate_func=smooth,
        )
        self.wait(0.5)

        self.play(
            w_theta.animate.set_value(0.5),
            w_phi.animate.set_value(0.5),
            run_time=2.5,
            rate_func=smooth,
        )
        self.wait(0.5)

        # Move to a corner to show dominance
        self.play(
            w_theta.animate.set_value(0.95),
            w_phi.animate.set_value(0.95),
            run_time=2.5,
            rate_func=smooth,
        )
        self.wait(1)

        # --- Reference to MATLAB code ----------------------------------------
        ref = Text(
            "Maps to fuel_vol_tank_combo.m lines 37-41",
            font_size=20,
            color=C_TEAL,
        ).next_to(formula, UP, buff=0.2)
        self.play(FadeIn(ref))
        self.wait(2)
