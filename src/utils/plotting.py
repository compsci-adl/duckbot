import io

from cgitb import grey
import matplotlib.pyplot as plt
from typing import List, Tuple


Y_CLIP = 20  # maximum height of plot that can be displayed for readability purposes
GREY = (0.5, 0.5, 0.5, 1)
WHITE = (1, 1, 1, 1)


def get_histogram_image(data: List[Tuple], highlight=-1):
    """Generates an image based on histogram data
    Data is a list histogram data in the form of (x,y), where:
    - x is the 'count' or 'bucket'
    - y is the frequency

    highlight is a selector variable for the two skullboard functions which use it.
    When it is defined with a non negative value, it will draw a vertical line at entry x, and modify the x/y labels
    """
    # Unzip the data into x and y values
    x, y = zip(*data)

    # Create the figure and axis
    fig, ax = plt.subplots()

    # Plot the bar chart
    bars = ax.bar(x, y, tick_label=x, color=WHITE)

    # Add text annotations to the top of the bars
    bar_color = bars[0].get_facecolor()
    for bar in bars:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            min(bar.get_height(), Y_CLIP) + 0.1,
            round(bar.get_height(), 1),
            horizontalalignment="center",
            color=GREY,
            weight="bold",
        )

    # add a vertical line to the plot if selected
    if highlight > 0:
        plt.axvline(x=highlight, ymin=0, linewidth=3, color="r", linestyle="--")

    # set x/y labels
    xlabel = "Reactions" if highlight == -1 else "Posts"
    ylabel = "Posts" if highlight == -1 else "Users"
    ax.set_xlabel(f"Number of {xlabel}", color=WHITE)
    ax.set_ylabel(f"Number of {ylabel}", color=WHITE)

    # set visibilities of borders
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GREY)

    # add horizontal grid lines
    ax.yaxis.grid(True, color=GREY)
    ax.xaxis.grid(False)

    # Modify x/y ticks
    ax.tick_params(bottom=False, left=False)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", colors=WHITE)
    ax.tick_params(axis="y", colors=WHITE)

    # add transparency
    fig.patch.set_alpha(0)
    ax.set_facecolor((0, 0, 0, 0))

    # Set y-axis limits
    ax.set_ylim(bottom=0, top=min(Y_CLIP, max(y))+1)

    # layout configurations
    ax.set_aspect(aspect="auto", adjustable="datalim")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf
