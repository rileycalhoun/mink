"""Cloud GPU orchestration for Mink.

Providers here manage the on-demand transcription engine: spin a GPU pod up
when the user needs it, tear it down when idle. Nothing in this package is
imported unless the corresponding API key is configured.
"""

from mink.cloud.runpod import RunPodClient, RunPodError

__all__ = ["RunPodClient", "RunPodError"]
