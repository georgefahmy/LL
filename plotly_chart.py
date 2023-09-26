from collections import OrderedDict

from plotly.graph_objects import Figure, Scatterpolar


def plotly_chart(player_1, player_2):
    fig = Figure()
    config = {
        "displaylogo": False,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "toImageButtonOptions": {
            "format": "png",
            "filename": f"{player_1.formatted_username}_{player_2.formatted_username}_similarity",
        },
    }
    player_1_categories = OrderedDict(sorted(player_1.category_metrics.items()))
    player_2_categories = OrderedDict(sorted(player_2.category_metrics.items()))

    fig.add_trace(
        Scatterpolar(
            r=[category.percent * 100 for category in player_1_categories.values()],
            theta=[category for category in player_1_categories.keys()],
            fill="toself",
            name=player_1.formatted_username,
            hovertemplate=("Category: %{theta}<br>% Correct: %{r:.1f}%"),
            hoveron="points",
        )
    )
    fig.add_trace(
        Scatterpolar(
            r=[category.percent * 100 for category in player_2_categories.values()],
            theta=[category for category in player_2_categories.keys()],
            fill="toself",
            name=player_2.formatted_username,
            hovertemplate=("Category: %{theta}<br>% Correct: %{r:.1f}%"),
            hoveron="points",
        )
    )
    fig.update_layout(
        title_text="Learned League Similarity",
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100]),
        ),
        showlegend=True,
    )
    fig.show(config=config)
