"""
Contains the LivePlotter class, a subclass of BasePlotter. This class plots incoming data in real time
according to properties defined in RobotPlot.
"""

import time
import traceback
import asyncio

from atlasbuggy.ui.plotters.baseplotter import BasePlotter
from atlasbuggy.ui.plotters.plot import RobotPlot
from atlasbuggy.ui.plotters.collection import RobotPlotCollection


class LivePlotter(BasePlotter):
    initialized = False

    def __init__(self, num_columns, *robot_plots, enabled=True, draw_legend=True, legend_args=None, lag_cap=0.005,
                 skip_count=0, matplotlib_events=None, active_window_resizing=True):
        """
        Only one LivePlotter instance can run at one time. Multiple interactive matplotlib
        windows don't behave well. This also conserves CPU usage.

        :param num_columns: Configure how the subplots are arranged
        :param robot_plots: RobotPlot or RobotPlotCollection instances. Each one will be a subplot
        :param legend_args: dictionary of arguments to pass to plt.legend
        :param lag_cap: Constrains how out of sync the plot can be with incoming packets. If the plot
            is causing a time difference greater than the one specified, skip plotting the incoming data
            until the plotter comes back in sync.
        :param skip_count: only plot every nth value
        :param matplotlib_events: dictionary of matplotlib callback events
        """
        if LivePlotter.initialized:
            raise Exception("Can't have multiple plotter instances!")
        LivePlotter.initialized = True

        super(LivePlotter, self).__init__(
            num_columns, legend_args, draw_legend, matplotlib_events, enabled, False, True, *robot_plots
        )

        self.time0 = None
        self.lag_cap = lag_cap
        self.plot_skip_count = skip_count
        self.skip_counter = 0
        self.is_closed = False
        self.is_paused = False
        self.active_window_resizing = active_window_resizing

        if self.enabled:
            # create a plot line for each RobotPlot or RobotPlotCollection.
            for plot in self.robot_plots:
                self._create_lines(plot)

            # define a clean close event
            self.fig.canvas.mpl_connect('close_event', lambda event: self.close())
            self.init_legend()
            self.plt.show(block=False)

    def update_collection(self, plot):
        if plot.name not in self.lines:
            self.lines[plot.name] = {}

        if plot.flat:
            for subplot in plot.plots:
                if subplot.name not in self.lines[plot.name]:
                    self.lines[plot.name][subplot.name] = \
                        self.axes[plot.name].plot([], [], **subplot.properties)[0]
        else:
            for subplot in plot.plots:
                if subplot.name not in self.lines[plot.name]:
                    self.lines[plot.name][subplot.name] = \
                        self.axes[plot.name].plot([], [], [], **subplot.properties)[0]

    def _create_lines(self, plot):
        if isinstance(plot, RobotPlot):
            if plot.name not in self.lines:
                if plot.flat:  # if the plot is 2D
                    self.lines[plot.name] = self.axes[plot.name].plot([], [], **plot.properties)[0]
                else:
                    self.lines[plot.name] = self.axes[plot.name].plot([], [], [], **plot.properties)[0]
        elif isinstance(plot, RobotPlotCollection):  # similar to RobotPlot initialization except there are subplots
            self.update_collection(plot)

    def add_plots(self, *robot_plots, num_columns=None):
        self.add_subplots(*robot_plots, num_columns=num_columns)
        for plot in self.robot_plots:
            self._create_lines(plot)

    def set_time(self, time0=None):
        """
        Supply a start time. This keeps all timers in sync

        :param time0: a value supplied by time.time()
        :return: None
        """
        if time0 is None:
            time0 = time.time()
        self.time0 = time0

    def should_update(self, dt):
        """
        Signal whether or not the plot should update using self.lag_cap.
        If the packet_timestamp - current_time is greater than self.lag_cap, return False

        :param dt: current time since program start
        :return: True or False whether the plot should update or not
        """
        if not self.enabled:
            return False

        if self.time0 is not None and dt is not None:
            current_time = time.time() - self.time0

            lag_status = abs(dt - current_time) < self.lag_cap
        else:
            lag_status = True

        self.skip_counter += 1
        if self.plot_skip_count > 0:
            skip_status = self.skip_counter % self.plot_skip_count == 0
        else:
            skip_status = True
        return lag_status and skip_status

    async def run(self):
        """
        Update plot using data supplied to the robot plot objects
        :return: True or False if the plotting operation was successful
        """

        while self.all_running():
            if self.is_closed:
                self.exit()
                return

            if not self.enabled:  # or not self.should_update(timestamp):
                continue

            if self.is_paused:
                self.plt.pause(0.005)
                await asyncio.sleep(0.05)
                continue

            for plot in self.robot_plots:
                if isinstance(plot, RobotPlot):
                    self.lines[plot.name].set_xdata(plot.data[0])
                    self.lines[plot.name].set_ydata(plot.data[1])
                    if not plot.flat:
                        self.lines[plot.name].set_3d_properties(plot.data[2])

                    if len(plot.changed_properties) > 0:
                        self.lines[plot.name].set(**plot.changed_properties)
                        plot.changed_properties = {}

                elif isinstance(plot, RobotPlotCollection):
                    for subplot in plot.plots:
                        # print(subplot.name, subplot.data[0][-1], subplot.data[1][-1])
                        self.lines[plot.name][subplot.name].set_xdata(subplot.data[0])
                        self.lines[plot.name][subplot.name].set_ydata(subplot.data[1])
                        if not plot.flat:
                            self.lines[plot.name][subplot.name].set_3d_properties(subplot.data[2])

                        if len(subplot.changed_properties) > 0:
                            self.lines[plot.name][subplot.name].set(**subplot.changed_properties)
                            subplot.changed_properties = {}

                if self.active_window_resizing and plot.window_resizing:
                    if plot.flat:
                        self.axes[plot.name].set_xlim(plot.x_range)
                        self.axes[plot.name].set_ylim(plot.y_range)
                    else:
                        self.axes[plot.name].set_xlim3d(plot.x_range)
                        self.axes[plot.name].set_ylim3d(plot.y_range)
                        self.axes[plot.name].set_zlim3d(plot.z_range)

            try:
                self.fig.canvas.draw()
                self.plt.pause(0.005)  # can't be less than ~0.005
                await asyncio.sleep(0.005)

            except BaseException as error:
                traceback.print_exc()
                self.exit()

    def pause(self):
        self.is_paused = True

    def unpause(self):
        self.is_paused = False

    def toggle_pause(self):
        self.is_paused = not self.is_paused

    def plot(self):
        """
        Turn of live plotting and freeze the plot in place
        """
        if self.enabled:
            self.plt.ioff()
            self.plt.gcf()
            self.plt.show()

    def close(self):
        """
        Close the plot safely
        """
        if self.enabled and not self.is_closed:
            self.is_closed = True
            self.plt.ioff()
            self.plt.gcf()
            self.plt.close('all')
