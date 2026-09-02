
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def visualize_flight_data(data_file, failure_time=None):
    """读取保存的CSV日志文件，并绘制遥测曲线。

    支持通过参数指定或从数据列中自动提取左发失效时间点并进行标注。
    """
    if not os.path.exists(data_file):
        print("File does not exist")
        return

    try:
        # 读取数据
        df = pd.read_csv(data_file)
        print(df.head())
        if df.empty:
            print("Telemetry log is empty.")
            return

        # ----------------------------------------------------------------------
        # 1. 自动提取左发失效时间点（如果未手动指定 failure_time）
        # ----------------------------------------------------------------------
        if failure_time is None:
            if "left_engine_fail" in df.columns:
                fail_rows = df[df["left_engine_fail"] == True]
                if not fail_rows.empty:
                    failure_time = fail_rows["time"].iloc[0]
            elif "event" in df.columns:
                fail_rows = df[df["event"] == "LEFT_ENGINE_FAILURE"]
                if not fail_rows.empty:
                    failure_time = fail_rows["time"].iloc[0]

        # 创建包含 4 个子图的画布
        fig, axs = plt.subplots(4, 1, figsize=(10, 15), sharex=True)
        fig.suptitle(
            "Flight Simulation Telemetry (De Havilland Beaver)",
            fontsize=16,
            fontweight="bold",
        )

        # 1. 高度曲线
        axs[0].plot(
            df["time"],
            df["altitude"],
            color="blue",
            linewidth=2,
            label="Current Altitude",
        )
        axs[0].set_ylabel("Altitude (m)", fontsize=12)
        axs[0].grid(True, linestyle=":")
        axs[0].legend(loc="upper right")
        axs[0].set_title("Altitude Profile")

        # 2. 空速曲线
        axs[1].plot(
            df["time"],
            df["airspeed"],
            color="green",
            linewidth=2,
            label="Airspeed",
        )
        axs[1].set_ylabel("Airspeed (m/s)", fontsize=12)
        axs[1].grid(True, linestyle=":")
        axs[1].legend(loc="upper right")
        axs[1].set_title("Airspeed Profile")

        # 3. 垂直速度曲线
        axs[2].plot(
            df["time"],
            df["vertical_speed"],
            color="purple",
            linewidth=2,
            label="Vertical Speed (- is descent)",
        )
        axs[2].axhline(y=0, color="gray", linestyle="--", linewidth=1, alpha=0.7)
        axs[2].fill_between(
            df["time"],
            df["vertical_speed"],
            0,
            where=(df["vertical_speed"] < 0),
            color="purple",
            alpha=0.1,
            label="Descending",
        )
        axs[2].set_ylabel("Vertical Speed (m/s)", fontsize=12)
        axs[2].grid(True, linestyle=":")
        axs[2].legend(loc="lower left")
        axs[2].set_title("Vertical Speed Profile (Negative = Descent)")

        # 4. 滚转角 (Roll) 曲线
        axs[3].plot(
            df["time"],
            df["roll"],
            color="darkorange",
            linewidth=2,
            label="Roll Angle (rad)",
        )
        axs[3].axhline(
            y=0,
            color="gray",
            linestyle="--",
            linewidth=1,
            alpha=0.7,
            label="Level Flight (0 rad)",
        )
        axs[3].fill_between(
            df["time"],
            df["roll"],
            0,
            where=(df["roll"] < 0),
            color="blue",
            alpha=0.1,
            label="Left Roll (<0)",
        )
        axs[3].fill_between(
            df["time"],
            df["roll"],
            0,
            where=(df["roll"] > 0),
            color="red",
            alpha=0.1,
            label="Right Roll (>0)",
        )
        axs[3].set_xlabel("Time (s)", fontsize=12)
        axs[3].set_ylabel("Roll (rad)", fontsize=12)
        axs[3].grid(True, linestyle=":")
        axs[3].legend(loc="upper right")
        axs[3].set_title("Roll Angle Profile (Negative = Left Bank)")

        # ----------------------------------------------------------------------
        # 2. 在所有子图中叠加“左发失效”红虚线及文本标注
        # ----------------------------------------------------------------------
        if failure_time is not None:
            for i, ax in enumerate(axs):
                ax.axvline(
                    x=failure_time,
                    color="red",
                    linestyle="--",
                    linewidth=1.8,
                    alpha=0.9,
                    label="Left Engine Failure" if i == 0 else "",
                )

            # 在第一个子图上方添加文字标注框
            axs[0].annotate(
                f"Left Engine Failure (t={failure_time:.2f}s)",
                xy=(failure_time, axs[0].get_ylim()[1]),
                xytext=(failure_time + 0.5, axs[0].get_ylim()[1] * 0.95),
                color="red",
                fontweight="bold",
                fontsize=10,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="yellow",
                    edgecolor="red",
                    alpha=0.7,
                ),
                arrowprops=dict(
                    arrowstyle="->", color="red", connectionstyle="arc3,rad=0"
                ),
            )
            # 刷新第0个图的图例（加入红虚线）
            axs[0].legend(loc="upper right")

        plt.tight_layout()
        output_img = "./state_logs/flight_analysis_plot.png"
        plt.savefig(output_img, dpi=300)
        print(f"Plot saved to {output_img}")
        plt.close(fig)

    except Exception as e:
        print(f"An error occurred: {e}")


# 使用方式 1：如果 CSV 包含 `left_engine_fail` 或 `event` 列，可自动检测
# visualize_flight_data("flight_telemetry_log.csv")

# 使用方式 2：如果 CSV 未记录事件状态，可以直接传入失效发生的秒数（例如 10.5 秒）：
visualize_flight_data("./state_logs/flight_telemetry_log.csv", failure_time=23)