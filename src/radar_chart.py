import math
import os
from collections import OrderedDict

import matplotlib.pyplot as plt

# import numpy as np
import PySimpleGUI as sg
from matplotlib import use
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import Circle
from matplotlib.path import Path
from matplotlib.projections import register_projection
from matplotlib.projections.polar import PolarAxes
from numpy import append, degrees, linspace, pi

from .constants import CATEGORIES

use("TkAgg")


def radar_factory(num_vars, frame="circle"):
    """
    Create a radar chart with `num_vars` axes.

    This function creates a RadarAxes projection and registers it.

    Parameters
    ----------
    num_vars : int
        Number of variables for radar chart.
    frame : {'circle', 'polygon'}
        Shape of frame surrounding axes.

    """
    # calculate evenly-spaced axis angles
    theta = linspace(0, 2 * pi, num_vars, endpoint=False)

    class RadarTransform(PolarAxes.PolarTransform):
        def transform_path_non_affine(self, path):
            # Paths with non-unit interpolation steps correspond to gridlines,
            # in which case we force interpolation (to defeat PolarTransform's
            # autoconversion to circular arcs).
            if path._interpolation_steps > 1:
                path = path.interpolated(num_vars)
            return Path(self.transform(path.vertices), path.codes)

    class RadarAxes(PolarAxes):
        name = "radar"
        PolarTransform = RadarTransform

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # rotate plot such that the first axis is at the top
            self.set_theta_zero_location("E")

        def fill(self, *args, closed=True, **kwargs):
            """Override fill so that line is closed by default"""
            return super().fill(closed=closed, *args, **kwargs)

        def plot(self, *args, **kwargs):
            """Override plot so that line is closed by default"""
            lines = super().plot(*args, **kwargs)
            for line in lines:
                self._close_line(line)

        def _close_line(self, line):
            x, y = line.get_data()
            # FIXME: markers at x[0], y[0] get doubled-up
            if x[0] != x[-1]:
                x = append(x, x[0])
                y = append(y, y[0])
                line.set_data(x, y)

        def set_varlabels(self, labels):
            self.set_thetagrids(degrees(theta), labels)

        def _gen_axes_patch(self):
            # The Axes patch must be centered at (0.5, 0.5) and of radius 0.5
            # in axes coordinates.
            return Circle((0.5, 0.5), 0.5)

        def _gen_axes_spines(self):
            return super()._gen_axes_spines()

    register_projection(RadarAxes)
    return theta


class Toolbar(NavigationToolbar2Tk):
    def __init__(self, *args, **kwargs):
        super(Toolbar, self).__init__(*args, **kwargs)


def format_coord(category, percent):
    category_value = CATEGORIES[min(17, int(round((degrees(category)) / 20, 0)))]
    return f"Category: {category_value}, Percentage: {percent:.1f}%"


def draw_figure_w_toolbar(canvas, fig, canvas_toolbar):
    if canvas.children:
        for child in canvas.winfo_children():
            child.destroy()
    if canvas_toolbar.children:
        for child in canvas_toolbar.winfo_children():
            child.destroy()
    figure_canvas_agg = FigureCanvasTkAgg(fig, master=canvas)
    figure_canvas_agg.draw()
    toolbar = Toolbar(figure_canvas_agg, canvas_toolbar)
    toolbar.update()
    figure_canvas_agg.get_tk_widget().pack(side="right", fill="both", expand=1)


def roundup(x):
    return math.ceil(x / 10.0) * 10


def radar_similarity(player_1, player_2):
    player_1_categories = OrderedDict(sorted(player_1.category_metrics.items()))
    player_2_categories = OrderedDict(sorted(player_2.category_metrics.items()))
    theta = radar_factory(len(list(player_1_categories.keys())))
    data = [
        [category.percent * 100 for category in player_1_categories.values()],
        [category.percent * 100 for category in player_2_categories.values()],
    ]
    fig, ax = plt.subplots(
        figsize=(9, 9),
        subplot_kw=dict(projection="radar"),
    )
    labels = list(player_1_categories.keys())
    colors = ["b", "r"]
    # max_val = roundup(max(list(map(max, data))))
    # max_count = int(max_val / 10 + 1)
    # ax_vals = list(map(int, np.linspace(0, max_val, max_count)))
    # # ax.set_rgrids(ax_vals)
    ax.set_rgrids([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])

    sc1 = ax.scatter(theta, data[0], color=colors[0])
    ax.fill(theta, data[0], facecolor=colors[0], alpha=0.15, label="_nolegend_")

    sc2 = ax.scatter(theta, data[1], color=colors[1])
    ax.fill(theta, data[1], facecolor=colors[1], alpha=0.15, label="_nolegend_")

    ax.set_varlabels(labels)
    # ax.set_ylim(0, max_val)
    ax.set_ylim(0, 100)

    annot = ax.annotate(
        "",
        xy=(0, 0),
        xytext=(20, 20),
        textcoords="offset points",
        bbox=dict(boxstyle="round", fc="w"),
        arrowprops=dict(arrowstyle="->"),
    )
    annot.set_visible(False)

    def update_annot(ind, sc, fc, c, name):
        n = ind["ind"][0]
        cat = labels[n]
        perc = sc.get_offsets()[n][1]
        text = f"{name}\n{cat}: {perc:.1f}%"

        annot.xy = sc.get_offsets()[n]
        annot.set(text=text, color=c, bbox=dict(boxstyle="round", fc=fc, edgecolor="k"))

    def hover(event):
        vis = annot.get_visible()
        if event.inaxes == ax:
            cont1, ind1 = sc1.contains(event)
            cont2, ind2 = sc2.contains(event)
            if cont1:
                update_annot(ind1, sc1, "blue", "w", player_1.formatted_username)
                annot.set_visible(True)
                fig.canvas.draw_idle()
            elif cont2:
                update_annot(ind2, sc2, "red", "k", player_2.formatted_username)
                annot.set_visible(True)
                fig.canvas.draw_idle()
            else:
                if vis:
                    annot.set_visible(False)
                    fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", hover)

    # add legend relative to top-left plot
    ax.legend(
        (player_1.formatted_username, player_2.formatted_username),
        loc=(0.9, 0.95),
        labelspacing=0.1,
        fontsize="small",
    )
    ax.format_coord = format_coord

    if not os.path.isdir(
        os.path.expanduser("~") + "/.LearnedLeague/similarity_charts/"
    ):
        os.mkdir(os.path.expanduser("~") + "/.LearnedLeague/similarity_charts/")

    fig.savefig(
        os.path.expanduser("~")
        + f"/.LearnedLeague/similarity_charts/{player_1.formatted_username}_{player_2.formatted_username}_similarity.png"
    )
    layout = [
        [sg.Text("Player Similarity", font=("Arial Bold", 18))],
        [
            sg.Column(
                layout=[
                    [
                        sg.Canvas(
                            key="fig_cv",
                            size=(800, 800),
                            expand_x=True,
                            expand_y=True,
                        )
                    ]
                ],
                pad=(0, 0),
            )
        ],
        [sg.Canvas(key="controls_cv", expand_x=True)],
    ]

    window = sg.Window(
        "Learned League Similarity",
        layout,
        finalize=True,
        resizable=True,
        font=("Arial", 14),
        element_justification="c",
        metadata="similarity_chart_window",
    )
    DPI = fig.get_dpi()
    fig.set_size_inches(804 / float(DPI), 804 / float(DPI))
    draw_figure_w_toolbar(
        window["fig_cv"].TKCanvas, fig, window["controls_cv"].TKCanvas
    )
    return window
