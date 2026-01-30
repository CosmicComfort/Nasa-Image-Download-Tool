"""
Adaptive throttling controller for managing download concurrency.
"""

import logging
import threading
from typing import Tuple

from ..core.config import MAX_WORKERS, MIN_WORKERS


class AdaptiveController:
    """
    Adaptive concurrency controller with throttle detection.

    Automatically adjusts the number of workers based on API response patterns:
    - Reduces workers when throttling (429) or high failure rates detected
    - Increases workers when success rates are high
    - Applies cooldown periods when needed
    """

    def __init__(
        self,
        min_workers: int = MIN_WORKERS,
        max_workers: int = MAX_WORKERS,
    ):
        """
        Initialize the adaptive controller.

        Args:
            min_workers: Minimum number of concurrent workers
            max_workers: Maximum number of concurrent workers
        """
        self.lock = threading.Lock()
        self.success = 0
        self.fail = 0
        self.throttle = 0
        self.total = 0
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)

    def report(self, status: str) -> None:
        """
        Report the result of a download operation.

        Args:
            status: One of "success", "throttle", or "fail"
        """
        with self.lock:
            self.total += 1
            if status == "success":
                self.success += 1
            elif status == "throttle":
                self.throttle += 1
            else:
                self.fail += 1

    def evaluate_and_adjust(self, current_workers: int) -> Tuple[int, float]:
        """
        Evaluate performance and adjust worker count.

        Args:
            current_workers: Current number of workers

        Returns:
            Tuple of (new_worker_count, cooldown_seconds)
        """
        with self.lock:
            total = self.total or 1
            throttle_rate = self.throttle / total
            fail_rate = (self.fail + self.throttle) / total
            success_rate = self.success / total

            # Reset counters
            self.success = self.fail = self.throttle = self.total = 0

        new_workers = current_workers
        cooldown = 0.0

        # High throttle rate - significant reduction
        if throttle_rate > 0.08:
            new_workers = max(self.min_workers, int(current_workers * 0.5))
            cooldown = min(60, 5 + int(throttle_rate * 200))
            self.logger.info(
                "Throttle detected (%.1f%%): reducing to %d workers, cooldown %ds",
                throttle_rate * 100,
                new_workers,
                cooldown,
            )

        # High failure rate - moderate reduction
        elif fail_rate > 0.25:
            new_workers = max(self.min_workers, int(current_workers * 0.7))
            cooldown = min(30, 3 + int(fail_rate * 40))
            self.logger.warning(
                "High failure rate (%.1f%%): reducing to %d workers",
                fail_rate * 100,
                new_workers,
            )

        # High success rate - gradual increase
        elif success_rate > 0.95 and current_workers < self.max_workers:
            new_workers = min(self.max_workers, current_workers + 1)
            self.logger.info(
                "Performance good (%.1f%% success): increasing to %d workers",
                success_rate * 100,
                new_workers,
            )

        return new_workers, cooldown

    def get_stats(self) -> dict:
        """
        Get current statistics.

        Returns:
            Dictionary with success, fail, throttle, and total counts
        """
        with self.lock:
            return {
                "success": self.success,
                "fail": self.fail,
                "throttle": self.throttle,
                "total": self.total,
            }
