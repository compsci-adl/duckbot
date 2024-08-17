import io
from cgitb import grey
from typing import List, Tuple

import matplotlib.pyplot as plt

GREY = (0.5, 0.5, 0.5, 1)
WHITE = (1, 1, 1, 1)

Y_LIM_DEFAULT = 20


def get_histogram_image(
    data: List[Tuple],
    xlabel: str = "Count",
    ylabel: str = "Frequency",
    vline: int = -1,
    y_clip: int = Y_LIM_DEFAULT,
) -> io.BytesIO:
    """Generates an image based on histogram data.

    Args:
        data: List of histogram data in the form of [(x,y),(x,y),...,], where:
            - x is the 'count' or 'bucket'
            - y is the frequency
        xlabel: Label for the x-axis (default is 'Count').
        ylabel: Label for the y-axis (default is 'Frequency').
        vline: X position to place a vertical line (default is -1, meaning no line).
        y_clip: Maximum height of the plot for readability (default is Y_LIM_DEFAULT).

    Returns:
        A BytesIO object containing the image.
    """

    # Unzip the data into x and y values
    x, y = zip(*data)

    # Create the figure and axis
    fig, ax = plt.subplots()

    # Plot the bar chart
    bars = ax.bar(x, y, tick_label=x, color=WHITE)

    # Add text annotations to the top of the bars
    for bar in bars:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            min(bar.get_height(), y_clip) + 0.1,
            round(bar.get_height(), 1),
            horizontalalignment="center",
            color=GREY,
            weight="bold",
        )

    # add a vertical line to the plot if selected
    if vline >= 0:
        plt.axvline(x=vline, ymin=0, linewidth=3, color="r", linestyle="--")

    # set x/y labels
    ax.set_xlabel(xlabel, color=WHITE)
    ax.set_ylabel(ylabel, color=WHITE)

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
    ax.set_ylim(bottom=0, top=min(y_clip, max(y)) + 1)

    # layout configurations
    ax.set_aspect(aspect="auto", adjustable="datalim")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf
