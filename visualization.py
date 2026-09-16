import os
import matplotlib.pyplot as plt
import pandas as pd


REQUIRED_COLUMNS = [
    "time",
    "altitude",
    "airspeed",
    "vertical_speed",
    "roll",
    "pitch",
    "aileron",
    "elevator",
    "rudder",
    "throttle_left",
    "throttle_right",
]


def _find_failure_time(df, failure_time):
    """Return an explicitly supplied or automatically detected failure time."""
    if failure_time is not None:
        return float(failure_time)

    if "event" in df.columns:
        failure_rows = df[df["event"] == "LEFT_ENGINE_FAILURE"]
        if not failure_rows.empty:
            return float(failure_rows["time"].iloc[0])

    if "left_engine_fail" in df.columns:
        failed = (
            df["left_engine_fail"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin({"true", "1", "yes"})
        )
        if failed.any():
            return float(df.loc[failed, "time"].iloc[0])

    return None


def _style_axis(ax, title, ylabel):
    """Apply the common style used by every telemetry subplot."""
    ax.set_title(title, fontsize=11, fontweight="semibold", pad=7)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, linestyle=":", linewidth=0.9, alpha=0.75)
    ax.margins(x=0)
    ax.tick_params(axis="both", labelsize=9)


def _plot_signal(ax, df, column, color, title, ylabel, label):
    ax.plot(
        df["time"],
        df[column],
        color=color,
        linewidth=2,
        label=label,
    )
    _style_axis(ax, title, ylabel)
    ax.legend(loc="best", fontsize=8, framealpha=0.9)


def visualize_flight_data(data_file, failure_time=None):
    """Read a telemetry CSV file and create a ten-signal flight dashboard.

    The left-engine failure time is read from the event/left_engine_fail column
    when possible. It can still be supplied explicitly for legacy log files.
    """
    if not os.path.exists(data_file):
        print(f"File does not exist: {data_file}")
        return

    try:
        df = pd.read_csv(data_file)
        if df.empty:
            print("Telemetry log is empty.")
            return

        missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            print(f"Telemetry log is missing columns: {', '.join(missing)}")
            return

        failure_time = _find_failure_time(df, failure_time)

        # Balanced 3x3 dashboard:
        # performance / attitude + propulsion / control surfaces.
        fig, subplot_grid = plt.subplots(
            3,
            3,
            figsize=(18, 13),
            sharex=True,
        )

        altitude_ax = subplot_grid[0, 0]
        axes = {
            "altitude": altitude_ax,
            "airspeed": subplot_grid[0, 1],
            "vertical_speed": subplot_grid[0, 2],
            "roll": subplot_grid[1, 0],
            "pitch": subplot_grid[1, 1],
            "throttle": subplot_grid[1, 2],
            "aileron": subplot_grid[2, 0],
            "elevator": subplot_grid[2, 1],
            "rudder": subplot_grid[2, 2],
        }

        fig.suptitle(
            "Flight Simulation Telemetry (De Havilland Beaver)",
            fontsize=18,
            fontweight="bold",
            y=0.975,
        )
        fig.subplots_adjust(
            left=0.055,
            right=0.985,
            bottom=0.065,
            top=0.92,
            hspace=0.42,
            wspace=0.30,
        )

        # Flight performance.
        _plot_signal(
            axes["altitude"],
            df,
            "altitude",
            "blue",
            "Altitude Profile",
            "Altitude (m)",
            "Current Altitude",
        )
        _plot_signal(
            axes["airspeed"],
            df,
            "airspeed",
            "green",
            "Airspeed Profile",
            "Airspeed (m/s)",
            "Airspeed",
        )
        _plot_signal(
            axes["vertical_speed"],
            df,
            "vertical_speed",
            "purple",
            "Vertical Speed Profile",
            "Vertical Speed (m/s)",
            "Vertical Speed",
        )
        axes["vertical_speed"].axhline(
            0, color="gray", linestyle="--", linewidth=1, alpha=0.7
        )
        axes["vertical_speed"].fill_between(
            df["time"],
            df["vertical_speed"],
            0,
            where=df["vertical_speed"] < 0,
            color="purple",
            alpha=0.10,
            label="Descending",
        )
        axes["vertical_speed"].legend(
            loc="best", fontsize=8, framealpha=0.9
        )

        # Aircraft attitude.
        _plot_signal(
            axes["roll"],
            df,
            "roll",
            "darkorange",
            "Roll Angle Profile (Negative = Left Bank)",
            "Roll (rad)",
            "Roll Angle",
        )
        axes["roll"].axhline(
            0, color="gray", linestyle="--", linewidth=1, alpha=0.7
        )
        axes["roll"].fill_between(
            df["time"],
            df["roll"],
            0,
            where=df["roll"] < 0,
            color="blue",
            alpha=0.10,
            label="Left Bank",
        )
        axes["roll"].fill_between(
            df["time"],
            df["roll"],
            0,
            where=df["roll"] > 0,
            color="red",
            alpha=0.10,
            label="Right Bank",
        )
        axes["roll"].legend(loc="best", fontsize=8, framealpha=0.9, ncol=3)

        _plot_signal(
            axes["pitch"],
            df,
            "pitch",
            "teal",
            "Pitch Angle Profile",
            "Pitch (rad)",
            "Pitch Angle",
        )
        axes["pitch"].axhline(
            0, color="gray", linestyle="--", linewidth=1, alpha=0.7
        )

        # Control surfaces.
        control_specs = [
            ("aileron", "royalblue", "Aileron Command", "Aileron"),
            ("elevator", "crimson", "Elevator Command", "Elevator"),
            ("rudder", "darkviolet", "Rudder Command", "Rudder"),
        ]
        for column, color, title, label in control_specs:
            _plot_signal(
                axes[column],
                df,
                column,
                color,
                title,
                "Normalized Command",
                label,
            )
            axes[column].axhline(
                0, color="gray", linestyle="--", linewidth=1, alpha=0.7
            )

        # Engine throttles.
        axes["throttle"].plot(
            df["time"],
            df["throttle_left"],
            color="firebrick",
            linewidth=2,
            label="Left Throttle",
        )
        axes["throttle"].plot(
            df["time"],
            df["throttle_right"],
            color="seagreen",
            linewidth=2,
            label="Right Throttle",
        )
        _style_axis(
            axes["throttle"],
            "Left- and Right-Engine Throttle",
            "Throttle Command",
        )
        axes["throttle"].set_ylim(-0.03, 1.03)
        axes["throttle"].legend(
            loc="best", fontsize=8, framealpha=0.9, ncol=2
        )

        # Mark the engine-failure transition consistently on every subplot.
        if failure_time is not None:
            for index, ax in enumerate(axes.values()):
                ax.axvline(
                    failure_time,
                    color="red",
                    linestyle="--",
                    linewidth=1.6,
                    alpha=0.9,
                    label="Left Engine Failure" if index == 0 else None,
                )

            axes["altitude"].annotate(
                f"Left Engine Failure\n(t={failure_time:.2f}s)",
                xy=(failure_time, 1.0),
                xycoords=("data", "axes fraction"),
                xytext=(8, -12),
                textcoords="offset points",
                ha="left",
                va="top",
                color="red",
                fontweight="bold",
                fontsize=9,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="yellow",
                    edgecolor="red",
                    alpha=0.75,
                ),
                arrowprops=dict(arrowstyle="->", color="red"),
            )
            axes["altitude"].legend(
                loc="best", fontsize=8, framealpha=0.9
            )

        # Keep the time scale visible on every subplot for standalone reading.
        for ax in axes.values():
            ax.tick_params(labelbottom=True)
            ax.set_xlabel("Time (s)", fontsize=10)

        output_dir = os.path.dirname(os.path.abspath(data_file))
        output_img = os.path.join(output_dir, "flight_analysis_plot.png")
        fig.savefig(
            output_img,
            dpi=300,
            bbox_inches="tight",
            facecolor="white",
        )
        print(f"Plot saved to {output_img}")
        plt.close(fig)

    except Exception as exc:
        print(f"An error occurred: {exc}")


if __name__ == "__main__":
    # The current telemetry format contains an event column, so the engine
    # failure marker is detected automatically.
    visualize_flight_data("./state_logs/flight_telemetry_log.csv")
