#!/usr/bin/env python3
"""Tools to display live progress of ATable instances based on the rich library.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2024/01/01"

import os
import math
import inspect
import collections
import rich
import rich.progress
import rich.panel
import rich.layout
import rich.console
import rich.progress_bar

import enb.experiment
from .config import options
from .config.aini import managed_attributes


def is_progress_enabled():
    """Return True if and only if all conditions for displaying progress are met:
    - verbose being level 1 (verbose) or 2 (info)
    - disable_progress_bar is set to False
    """
    return options.verbose in (1, 2) and not options.disable_progress_bar


@managed_attributes
class ProgressTracker(rich.live.Live):
    """Keep track of the progress of an ATable's (incl. Experiments') get_df.
    """
    # Style for the panel border surrounding each progress track
    style_border = "#adadad bold"

    # Style for the completed portion of the progress bar while it's being filled
    style_bar_complete = "#9b5ccb bold"
    # Style for the incomplete portion of the progress bar
    style_bar_incomplete = "#252525"
    # Style for the bar once the task is finished
    style_bar_finished = "#f3ac05"

    # Style for the panel title when the instance being tracked is an enb.sets.FilePropertiesTable subclass
    style_title_dataset = "#45e193"
    # Style for the panel title when the instance being tracked is an enb.experiment.Experiment subclass
    style_title_experiment = "#13bf00"
    # Style for the panel title when the instance being tracked is an enb.aanalysis.Analyzer subclass
    style_title_analyzer = "#1990ff"
    # Style for the panel title when the instance being tracked is an enb.aanalysis.AnalyzerSummary subclass
    style_title_summary = "#23cfff"
    # Style for the panel title when the instance being tracked is any other type of enb.atable.ATable instance
    style_title_atable = "#9b59ff"
    # Style for the panel title when the instance being tracked is not an enb.atable.ATable subclass
    style_title_other = "#cdabff"

    # Style for the text labels (e.g., "Rows", "Chunks")
    style_text_label = "#787878"
    # Style for the text separators (e.g., ":", "/")
    style_text_separator = "#505050"
    # Style for the text indicating units or scale (e.g., "s", "%")
    style_text_unit = "#707070"
    # Style for the text displaying the number of completed elements
    style_text_completed = "#bcbcbc bold"
    # Style for the text displaying the total number of elements
    style_text_total = "#bcbcbc"
    # Style for the text displaying speed
    style_text_speed = "#bcbcbc"
    # Style for the text displaying completion percentage
    style_text_percentage = "#bcbcbc"
    # Style for text displaying time values (not units)
    style_text_time = "#bcbcbc"

    # Style for the spinner
    style_spinner = "#9b5ccb bold"

    # Keep references to the current ProgressTracker instances in a LIFO
    _current_instance_stack = collections.deque()

    def __init__(self, atable, row_count: int, chunk_size: int):
        """
        :param atable: ATable subclass instance for which the progress is to be tracked
        :param row_count: total number of rows that need to be computed
        :param chunk_size: chunk size (any non-positive number
          is also interpreted as a chunk size equal to row_count)
        """
        self.atable = atable
        self.row_count = row_count
        self.chunk_size = min(row_count, chunk_size if chunk_size > 0 else row_count)

        row_progress_column = _RowProgressColumn(self)
        elapsed_and_expected_column = _ElapsedAndExpectedColumn(self)
        chunk_progress_column = _ChunkProgressColumn(self)
        self.row_progress_bar = _RowProgressBar(self)

        # Define the upper and lower progress rows
        self.upper_progress = rich.progress.Progress(
            rich.progress.SpinnerColumn(style=self.style_spinner),
            row_progress_column,
            _SeparatorColumn(self, width=1),
            elapsed_and_expected_column,
        )
        self.lower_progress = rich.progress.Progress(
            _SeparatorColumn(self, width=1),
            chunk_progress_column,
            _SeparatorColumn(self, width=1),
            self.row_progress_bar,
        )

        # Create the tasks that keep track of the completed rows and chunks
        self.row_task_id = self.upper_progress.add_task("Rows", total=self.row_count, pulse=False)
        self.row_task = [t for t in self.upper_progress.tasks if t.id == self.row_task_id][0]
        self.chunk_task_id = self.lower_progress.add_task(f"Chunk", total=math.ceil(
            self.row_count / self.chunk_size))
        self.chunk_task = [t for t in self.lower_progress.tasks if t.id == self.chunk_task_id][0]

        # Fix some column widths for a visually pleasant distribution
        first_column_width = max(
            len(rich.text.Text.from_markup(row_progress_column.get_render_str()).plain),
            len(rich.text.Text.from_markup(chunk_progress_column.get_render_str()).plain))
        row_progress_column.width = first_column_width
        chunk_progress_column.width = first_column_width

        # Display the progress rows one above the other
        self.group = rich.console.Group(self.upper_progress, self.lower_progress)

        title = (f"[{self._instance_to_title_style(atable)}]"
                 f"{atable.__class__.__name__}"
                 f"[/{self._instance_to_title_style(atable)}]")

        # Display the caller information for info and higher verbose level
        if enb.logger.level_active(enb.logger.level_info.name):
            for record in inspect.stack():
                if os.path.dirname(record.filename).startswith(os.path.dirname(__file__)):
                    continue
                title += (f"[not bold][{enb.logger.style_info}]"
                          f" < {os.path.basename(record.filename)}:{record.lineno}"
                          f"[/{enb.logger.style_info}][/not bold]")
                break

        self.panel = rich.panel.Panel(
            self.group,
            title=title,
            title_align="left",
            expand=True,
            border_style=self.style_border)
        super().__init__(self.panel)

        # Keep track of current instances so that the console of the most recent progress can be employed
        ProgressTracker._current_instance_stack.append(self)

    def complete_chunk(self):
        """Add 1 to the number of completed chunks if a chunk task has been defined.
        """
        if self.chunk_task_id is not None:
            self.lower_progress.advance(self.chunk_task_id)

    def update_chunk_completed_rows(self, chunk_completed_rows):
        """Set the number of rows completed for the current chunk.
        """
        previously_completed = self.chunk_task.completed * self.chunk_size \
            if self.chunk_task is not None else 0
        self.upper_progress.update(
            self.row_task_id,
            completed=previously_completed + chunk_completed_rows)
        self.row_progress_bar.total = self.row_count
        self.row_progress_bar.completed = self.row_task.completed

    @property
    def chunk_count(self):
        """Get the number of chunks defined for this progress tracking stage.
        """
        return math.ceil(self.row_count / self.chunk_size)

    @classmethod
    @property
    def console(cls):
        """Return the console instance for the current instance (the only live instance) of ProgressTracker,
        or None if none are available.
        """
        try:
            return ProgressTracker._current_instance_stack[-1].console
        except IndexError:
            return None

    def _instance_to_title_style(self, instance):
        """Return the current configured title style for the
        type of the instance whose progress is being tracked.
        """
        if isinstance(instance, enb.experiment.Experiment):
            return self.style_title_experiment
        if isinstance(instance, enb.sets.FilePropertiesTable):
            return self.style_title_dataset
        if isinstance(instance, enb.aanalysis.Analyzer):
            return self.style_title_analyzer
        if isinstance(instance, enb.aanalysis.AnalyzerSummary):
            return self.style_title_summary
        if isinstance(instance, enb.atable.ATable):
            return self.style_title_atable
        return self.style_title_other

    def __del__(self):
        last = ProgressTracker._current_instance_stack.pop()
        if last is not self:
            enb.logger.warn(
                "Warning! The ProgressTracker instance stack seems not not be in the right order.")


class _ProgressColumn:
    """Base class for progress columns that can consider both the row and the chunk progress.
    """

    def __init__(self, progress_tracker: ProgressTracker):
        super().__init__()
        self.progress_tracker = progress_tracker

    @property
    def chunk_task(self):
        return self.progress_tracker.chunk_task

    @property
    def row_task(self):
        return self.progress_tracker.row_task

    @property
    def chunk_size(self):
        return self.progress_tracker.chunk_size

    @property
    def chunk_count(self):
        return self.progress_tracker.chunk_count


class _ProgressTextColumn(_ProgressColumn, rich.progress.TextColumn):
    """Base class for progress columns that display text.
    """

    def __init__(self, progress_tracker: ProgressTracker, width: int = 0):
        rich.progress.TextColumn.__init__(self, "")
        self.progress_tracker = progress_tracker
        self.width = width

    def render(self, task):
        return rich.progress.Text.from_markup(f"{{:{self.width}s}}".format(self.get_render_str()))

    def get_render_str(self) -> str:
        raise NotImplemented

    def seconds_to_time_str(self, seconds: float, decimals=1, markup=True) -> str:
        """Convert the passed number of seconds to an HH:MM:SS format.
        :param seconds: the number of seconds (can be fractional)
        :param decimals: the number of decimals to which the number of seconds
          is rounded to.
        :param markup: if True, the values and units are surrounded by style markup tags.
        """
        seconds = round(seconds, decimals)
        second_fraction = seconds - int(seconds)
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)

        if markup is True:
            value_tag_start = f"[{self.progress_tracker.style_text_time}]"
            value_tag_end = f"[/{self.progress_tracker.style_text_time}]"
            unit_tag_start = f"[{self.progress_tracker.style_text_unit}]"
            unit_tag_end = f"[/{self.progress_tracker.style_text_unit}]"
        else:
            value_tag_start = ""
            value_tag_end = ""
            unit_tag_start = ""
            unit_tag_end = ""

        second_fraction_formatter = f"{{:.{decimals}f}}"

        return ((f"{value_tag_start}{hours:02d}{value_tag_end}{unit_tag_start}h{unit_tag_end} "
                 if hours else "")
                + (f"{value_tag_start}{minutes:02d}{value_tag_end}{unit_tag_start}m{unit_tag_end} "
                   if minutes else "")
                + (f"{value_tag_start}{seconds:02d}{value_tag_end}{unit_tag_start}s{unit_tag_end}"
                   if minutes or hours else
                   (f"{value_tag_start}{seconds}{value_tag_end}"
                    + (f"{unit_tag_start}s{unit_tag_end}" if decimals <= 0 else "")
                    + ((f"{value_tag_start}."
                        f"{second_fraction_formatter.format(second_fraction)[2:]}"
                        f"{value_tag_end}"
                        f"{unit_tag_start}s{unit_tag_end}")
                       if decimals > 0 else "")
                    ))
                )


class _RowProgressColumn(_ProgressTextColumn):
    """Display the row completion progress and the speed, if available.
    """

    def get_render_str(self) -> str:
        # Add the completed and total number of rows
        total_row_digits = len(str(self.row_task.total))
        row_count_formatter = f"{{:0{total_row_digits}d}}"
        speed_formatter = "{:>11s}"
        render_str = (f"[{self.progress_tracker.style_text_label}]"
                      f"Rows[/{self.progress_tracker.style_text_label}]"
                      f"  [{self.progress_tracker.style_text_separator}]"
                      f":[/{self.progress_tracker.style_text_separator}] "
                      f"[{self.progress_tracker.style_text_completed}]"
                      f"{row_count_formatter.format(self.row_task.completed)}"
                      f"[/{self.progress_tracker.style_text_completed}]"
                      f"[{self.progress_tracker.style_text_separator}]"
                      f"/[/{self.progress_tracker.style_text_separator}]"
                      f"[{self.progress_tracker.style_text_total}]"
                      f"{self.row_task.total}[/{self.progress_tracker.style_text_total}]"
                      f" ")

        # Add extra spaces so that any row count up to 5 digits generates the same width
        render_str += " " * 2 * (5 - total_row_digits)

        # Add speed if available
        if self.row_task.speed:
            # Padding needs to take into account the markup to maintain alignment
            formatted_length = (
                    11
                    + (2 * len(self.progress_tracker.style_text_unit) + len("[][/]")
                       if not self.row_task.finished else 0)
                    + 2 * len(self.progress_tracker.style_text_speed) + len("[][/]")
                    + 2 * len(self.progress_tracker.style_text_unit) + len("[][/]")
            )
            speed_formatter = f"{{:>{formatted_length}s}}"
            render_str += speed_formatter.format(
                (f"[{self.progress_tracker.style_text_unit}]"
                 f"+[/{self.progress_tracker.style_text_unit}]"
                 if not self.row_task.finished else ' ') +
                f"[{self.progress_tracker.style_text_speed}]"
                f"{self.row_task.speed:.2f}[/{self.progress_tracker.style_text_speed}]"
                f"[{self.progress_tracker.style_text_unit}]"
                f"/s[/{self.progress_tracker.style_text_unit}]")
        else:
            speed_formatter = "{:>11s}"
            render_str += speed_formatter.format("")

        return render_str


class _ElapsedAndExpectedColumn(_ProgressTextColumn):
    """Display the total elapsed and expected times.
    """

    def get_render_str(self) -> str:
        render_str = (f"[{self.progress_tracker.style_text_total}]"
                      f"{self.seconds_to_time_str(self.chunk_task.elapsed, markup=True)}"
                      f"[/{self.progress_tracker.style_text_total}]")
        if self.row_task.time_remaining:
            render_str += (f" [{self.progress_tracker.style_text_separator}]"
                           f"+~[/{self.progress_tracker.style_text_separator}] "
                           f"[{self.progress_tracker.style_text_total}]"
                           f"{self.seconds_to_time_str(self.row_task.time_remaining, markup=True)}"
                           f"[/{self.progress_tracker.style_text_total}]")
        return render_str


class _ChunkProgressColumn(_ProgressTextColumn):
    """Displays the chunk completion, size and row completion percentage.
    """

    def get_render_str(self) -> str:
        # Calculate the completed/total chunk string
        self.chunk_count_format = f"{{:0{len(str(self.chunk_count))}d}}"
        render_str = (f"[{self.progress_tracker.style_text_label}]Chunks"
                      f"[/{self.progress_tracker.style_text_label}]"
                      f"[{self.progress_tracker.style_text_separator}]"
                      f":[/{self.progress_tracker.style_text_separator}] "
                      f"[{self.progress_tracker.style_text_completed}]"
                      f"{self.chunk_count_format.format(self.chunk_task.completed)}"
                      f"[/{self.progress_tracker.style_text_completed}]"
                      f"[{self.progress_tracker.style_text_separator}]"
                      f"/[/{self.progress_tracker.style_text_separator}]"
                      f"[{self.progress_tracker.style_text_total}]"
                      f"{self.chunk_count_format.format(self.chunk_task.total)}"
                      f"[/{self.progress_tracker.style_text_total}]")

        # Add extra spaces so that any row count up to 5 digits generates the same width
        render_str += " " * 2 * (5 - len(str(self.chunk_count)))

        # Add extra spaces to align with the speed string
        render_str += " " * 6

        # Add a fixed-length, right-aligned percentage meter to align with the speed
        formatter_length = (
                6
                + 2 * len(self.progress_tracker.style_text_total) + len("[][/]")
                + 2 * len(self.progress_tracker.style_text_unit) + len("[][/]")
        )
        formatter = f"{{:>{formatter_length}s}}"
        render_str += formatter.format(
            f"[{self.progress_tracker.style_text_total}]"
            f"{100 * self.row_task.completed / self.row_task.total:.1f}"
            f"[/{self.progress_tracker.style_text_total}]"
            f"[{self.progress_tracker.style_text_unit}]"
            f"%[/{self.progress_tracker.style_text_unit}]")

        return render_str


class _RowProgressBar(rich.progress.BarColumn):
    """Display a progress bar based on the current row completion and total row count.
    """

    def __init__(self, progress_tracker: ProgressTracker):
        super().__init__(bar_width=None)
        self.progress_tracker = progress_tracker
        self.complete_style = progress_tracker.style_bar_complete
        self.finished_style = progress_tracker.style_bar_finished
        self.style = progress_tracker.style_bar_incomplete
        self.pulse_style = "#0000ff"

    def render(self, task):
        return super().render(self.progress_tracker.row_task)


class _SeparatorColumn(_ProgressTextColumn):
    """Display an empty string.
    """

    def get_render_str(self) -> str:
        return ""
