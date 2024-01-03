#!/usr/bin/env python3
"""Tools to display live progress of ATable instances based on the rich library.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2024/01/01"

import shutil
import math
import rich
import rich.progress
import rich.panel
import rich.layout
import rich.console

from .config import options

class ProgressTracker(rich.live.Live):
    """Keep track of the progress of an ATable's (incl. Experiments') get_df.
    """
    def __init__(self, atable, row_count : int, chunk_size : int):
        """
        :param atable: ATable subclass instance for which the progress is to be tracked
        :param row_count: total number of rows that need to be computed
        :param chunk_size: chunk size (any non-positive number
          is also interpreted as a chunk size equal to row_count)
        """
        self.atable = atable
        self.row_count = row_count
        self.chunk_size = min(row_count, chunk_size if chunk_size > 0 else row_count)

        self.progress = rich.progress.Progress(
            rich.progress.SpinnerColumn(),
            rich.progress.TextColumn(
                f"[progress.description]{{task.description:7s}}"),
            rich.progress.MofNCompleteColumn(),
            SpeedColumn(),
            RemainingTimeColumn(),
            rich.progress.BarColumn(bar_width=None),
            expand=True)

        if self.chunk_count > 1:
            self.chunk_task_id = self.progress.add_task(f"Chunks", total=math.ceil(self.row_count / self.chunk_size))
            self.chunk_task = [t for t in self.progress.tasks if t.id == self.chunk_task_id][0]
        else:
            self.chunk_task_id = None
            self.chunk_task = None

        self.row_task_id = self.progress.add_task("Rows", total=self.row_count)
        self.row_task = [t for t in self.progress.tasks if t.id == self.row_task_id][0]

        self.panel = rich.panel.Panel(
            self.progress,
            title=f"[bold]{atable.__class__.__name__}[/bold]",
            title_align="left", expand=True)

        super().__init__(self.panel, transient=options.verbose < 2)

    def complete_chunk(self):
        """Add 1 to the number of completed chunks if a chunk task has been defined.
        """
        if self.chunk_task_id is not None:
            self.progress.advance(self.chunk_task_id)

    def update_chunk_completed_rows(self, chunk_completed_rows):
        """Set the number of rows completed for the current chunk.
        """
        previously_completed = self.chunk_task.completed * self.chunk_size \
            if self.chunk_task is not None else 0
        self.progress.update(
            self.row_task_id,
            completed= previously_completed + chunk_completed_rows)

    @property
    def chunk_count(self):
        return math.ceil(self.row_count / self.chunk_size)

class SpeedColumn(rich.progress.TextColumn):
    """Column to display the number of elements processed per second.
    """
    def __init__(self, *args):
        super().__init__("")

    def render(self, task):
        if task.remaining:
            speed = task.speed or 0
            return rich.progress.Text(f"{speed:02.2f}/s")
        else:
            return rich.progress.Text("")


class RemainingTimeColumn(rich.progress.TextColumn):
    """Column to display the number of remaining elements.
    """
    def __init__(self, *args):
        super().__init__("")

    def render(self, task):
        if task.remaining:
            if task.time_remaining:
                time_str = f"~{task.time_remaining // 60:02d}m{task.time_remaining % 60:02d}s"
            else:
                time_str = f"~??m??s"
        else:
            time_str = ""
        return rich.progress.Text(f"{time_str}")

def is_progress_enabled():
    """Return True if and only if all conditions for displaying progress are met:
    - verbose being level 1 (verbose) or 2 (info)
    - disable_progress_bar is set to False
    """
    return options.verbose in (1,2) and not options.disable_progress_bar