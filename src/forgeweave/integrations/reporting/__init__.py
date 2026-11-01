"""Local reporting integration boundaries."""

from .failure import FailureReport, FailureReportItem, LocalFailureReporter, build_failure_report

__all__ = ["FailureReport", "FailureReportItem", "LocalFailureReporter", "build_failure_report"]
