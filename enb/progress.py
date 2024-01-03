#!/usr/bin/env python3
"""Tools to display live progress of ATable instances based on the rich library.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2024/01/01"

import math
import rich
import rich.progress
import rich.panel
import rich.layout
import rich.console
import rich.progress_bar

from .config import options


def is_progress_enabled():
    """Return True if and only if all conditions for displaying progress are met:
    - verbose being level 1 (verbose) or 2 (info)
    - disable_progress_bar is set to False
    """
    return options.verbose in (1, 2) and not options.disable_progress_bar


class ProgressTracker(rich.live.Live):
    """Keep track of the progress of an ATable's (incl. Experiments') get_df.
    """

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
            rich.progress.SpinnerColumn(),
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
        first_column_width = max(len(row_progress_column.get_render_str()),
                                 len(chunk_progress_column.get_render_str()))
        row_progress_column.width = first_column_width
        chunk_progress_column.width = first_column_width

        # Display the progress rows one above the other
        self.group = rich.console.Group(self.upper_progress, self.lower_progress)
        self.panel = rich.panel.Panel(
            self.group,
            title=f"[bold]{atable.__class__.__name__}[/bold]",
            title_align="left", expand=True)
        super().__init__(self.panel, transient=options.verbose < 1)

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
        return math.ceil(self.row_count / self.chunk_size)


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
        return rich.progress.Text(f"{{:{self.width}s}}".format(self.get_render_str()))

    def get_render_str(self) -> str:
        raise NotImplemented

    def seconds_to_time_str(self, seconds: float, decimals=0) -> str:
        """Convert the passed number of seconds to an HH:MM:SS format.
        :param seconds: the number of seconds (can be fractional)
        :param decimals: the number of decimals to which the number of seconds
          is rounded to.
        """
        seconds = round(seconds, decimals)
        second_fraction = seconds - int(seconds)
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return ((f"{hours:02d}h " if hours else "")
                + (f"{minutes:02d}m " if minutes else "")
                + (f"{seconds:02d}s" if minutes or hours else f"{seconds}s")
                + (f".{second_fraction}" if decimals > 0 else ""))


class _RowProgressColumn(_ProgressTextColumn):
    """Display the row completion progress and the speed, if available.
    """

    def get_render_str(self) -> str:
        # Add the completed and total number of rows
        total_row_digits = len(str(self.row_task.total))
        row_count_formatter = f"{{:0{total_row_digits}d}}"
        speed_formatter = "{:>11s}"
        render_str = (f"Rows  : {row_count_formatter.format(self.row_task.completed)}"
                      f"/{self.row_task.total} ")

        # Add extra spaces so that any row count up to 5 digits generates the same width
        render_str += " " * 2 * (5 - total_row_digits)

        # Add speed if available
        if self.row_task.speed:
            render_str += speed_formatter.format(
                f"{'+' if not self.row_task.finished else ' '}{self.row_task.speed:.2f}/s")
        else:
            render_str += speed_formatter.format("")

        return render_str


class _ChunkProgressColumn(_ProgressTextColumn):
    """Displays the chunk completion, size and row completion percentage.
    """

    def get_render_str(self) -> str:
        # Calculate the completed/total chunk string
        self.chunk_count_format = f"{{:0{len(str(self.chunk_count))}d}}"
        render_str = (f"Chunks: "
                      f"{self.chunk_count_format.format(self.chunk_task.completed)}"
                      f"/{self.chunk_count_format.format(self.chunk_task.total)}")

        # Add extra spaces so that any row count up to 5 digits generates the same width
        render_str += " " * 2 * (5 - len(str(self.chunk_count)))

        # Add extra spaces to align with the speed string
        render_str += " " * 6

        # Add a fixed-length, right-aligned percentage meter to align with the speed
        render_str += "{:>6s}".format(f"{100 * self.row_task.completed / self.row_task.total:.1f}%")

        return render_str


class _ElapsedAndExpectedColumn(_ProgressTextColumn):
    """Display the total elapsed and expected times.
    """

    def get_render_str(self) -> str:
        render_str = f"{self.seconds_to_time_str(self.chunk_task.elapsed)}"
        if self.row_task.time_remaining:
            render_str += f" +~ {self.seconds_to_time_str(self.row_task.time_remaining)}"
        return render_str


class _RowProgressBar(rich.progress.BarColumn):
    """Display a progress bar based on the current row completion and total row count.
    """

    def __init__(self, progress_tracker: ProgressTracker):
        super().__init__(bar_width=None)
        self.progress_tracker = progress_tracker

    def render(self, task):
        return super().render(self.progress_tracker.row_task)


class _SeparatorColumn(_ProgressTextColumn):
    """Display an empty string.
    """

    def get_render_str(self) -> str:
        return ""
