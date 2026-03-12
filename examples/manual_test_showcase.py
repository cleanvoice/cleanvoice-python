#!/usr/bin/env python3
"""Run a small set of polished manual SDK scenarios and save outputs locally."""

from __future__ import annotations

import argparse
import json
import os
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from cleanvoice import Cleanvoice, ProcessResult

DEFAULT_AUDIO_URL = os.getenv(
    "CLEANVOICE_SAMPLE_AUDIO_URL",
    "https://www.gutenberg.org/files/26200/mp3/26200-01.mp3",
)
DEFAULT_VIDEO_URL = os.getenv(
    "CLEANVOICE_SAMPLE_VIDEO_URL",
    "https://download.samplelib.com/mp4/sample-5s.mp4",
)


@dataclass(frozen=True)
class Scenario:
    """Manual scenario definition."""

    name: str
    description: str
    file_input: str
    output_filename: str
    options: Dict[str, Any]


def _full_cleanup_options() -> Dict[str, Any]:
    """Return a rich editing preset for manual validation."""
    return {
        "remove_noise": True,
        "fillers": True,
        "long_silences": True,
        "stutters": True,
        "mouth_sounds": True,
        "hesitations": True,
        "muted": True,
        "breath": True,
        "normalize": True,
        "studio_sound": True,
        "transcription": True,
        "summarize": True,
        "export_timestamps": True,
    }


SCENARIOS: List[Scenario] = [
    Scenario(
        name="audio_defaults",
        description="Audio input with no explicit processing flags.",
        file_input=DEFAULT_AUDIO_URL,
        output_filename="audio_defaults.mp3",
        options={},
    ),
    Scenario(
        name="audio_studio_sound_only",
        description="Audio input with only studio_sound enabled.",
        file_input=DEFAULT_AUDIO_URL,
        output_filename="audio_studio_sound_only.wav",
        options={"studio_sound": True},
    ),
    Scenario(
        name="audio_all_inclusive",
        description="Audio input with noise removal, speech cleanup, and text outputs.",
        file_input=DEFAULT_AUDIO_URL,
        output_filename="audio_all_inclusive.wav",
        options=_full_cleanup_options(),
    ),
    Scenario(
        name="video_defaults",
        description="Video input with no explicit processing flags.",
        file_input=DEFAULT_VIDEO_URL,
        output_filename="video_defaults.mp4",
        options={},
    ),
    Scenario(
        name="video_studio_sound_only",
        description="Video input with only studio_sound enabled.",
        file_input=DEFAULT_VIDEO_URL,
        output_filename="video_studio_sound_only.mp4",
        options={"studio_sound": True},
    ),
    Scenario(
        name="video_all_inclusive",
        description="Video input with cleanup, transcripts, and summary generation.",
        file_input=DEFAULT_VIDEO_URL,
        output_filename="video_all_inclusive.mp4",
        options=_full_cleanup_options(),
    ),
]


def progress_callback(data: Dict[str, Any]) -> None:
    """Print concise progress updates."""
    result = data.get("result")
    done = None

    if isinstance(result, dict):
        done = result.get("done")
    elif hasattr(result, "done"):
        done = getattr(result, "done")

    suffix = f" ({done}%)" if done is not None else ""
    print(f"  - {data.get('status', 'UNKNOWN')}{suffix}")


def _select_scenarios(names: Iterable[str]) -> List[Scenario]:
    if not names:
        return SCENARIOS

    selected = []
    valid_names = {scenario.name for scenario in SCENARIOS}
    for name in names:
        if name not in valid_names:
            raise ValueError(
                f"Unknown scenario '{name}'. Choose from: {', '.join(sorted(valid_names))}"
            )
        selected.append(next(s for s in SCENARIOS if s.name == name))
    return selected


def _write_summary(
    scenario: Scenario, result: ProcessResult, saved_path: Path, summary_path: Path
) -> None:
    """Persist a small JSON summary next to the saved media."""
    transcript_preview = None
    summary_text = None

    if result.transcript:
        transcript_preview = result.transcript.text[:500]
        summary_text = result.transcript.summary

    payload = {
        "scenario": scenario.name,
        "description": scenario.description,
        "input": scenario.file_input,
        "options": scenario.options,
        "task_id": result.task_id,
        "is_video": result.is_video,
        "download_url": result.media.url,
        "filename": result.media.filename,
        "saved_path": str(saved_path),
        "statistics": result.media.statistics.model_dump(exclude_none=True),
        "transcript_preview": transcript_preview,
        "summary": summary_text,
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_error_summary(scenario: Scenario, summary_path: Path, error: Exception) -> None:
    """Persist scenario failures without stopping the full matrix."""
    payload = {
        "scenario": scenario.name,
        "description": scenario.description,
        "input": scenario.file_input,
        "options": scenario.options,
        "error": str(error),
        "traceback": traceback.format_exc(),
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_transcript_files(
    result: ProcessResult, transcript_path: Path, summary_text_path: Path
) -> None:
    """Persist optional transcript artifacts for richer manual review."""
    if not result.transcript:
        return

    transcript_path.write_text(result.transcript.text, encoding="utf-8")
    if result.transcript.summary:
        summary_text_path.write_text(result.transcript.summary, encoding="utf-8")


def run_scenario(client: Cleanvoice, scenario: Scenario, results_dir: Path) -> None:
    """Execute a scenario and save the output plus metadata."""
    summary_path = results_dir / f"{scenario.name}.json"
    transcript_path = results_dir / f"{scenario.name}_transcript.txt"
    summary_text_path = results_dir / f"{scenario.name}_summary.txt"

    print(f"\nRunning {scenario.name}")
    print(f"Input: {scenario.file_input}")
    print(f"Description: {scenario.description}")

    result = client.process(
        scenario.file_input,
        progress_callback=progress_callback,
        **scenario.options,
    )

    returned_suffix = Path(result.media.filename).suffix or Path(
        scenario.output_filename
    ).suffix
    saved_path = Path(
        result.download_media(str(results_dir / f"{scenario.name}{returned_suffix}"))
    )
    _write_summary(scenario, result, saved_path, summary_path)
    _write_transcript_files(result, transcript_path, summary_text_path)

    print(f"Saved asset: {saved_path}")
    print(f"Saved summary: {summary_path}")
    print(f"Returned media type: {'video' if result.is_video else 'audio'}")
    print(f"Download URL: {result.media.url}")


def build_parser() -> argparse.ArgumentParser:
    """Create a small CLI for selecting scenarios."""
    parser = argparse.ArgumentParser(
        description="Run manual Cleanvoice SDK scenarios and save outputs to results_test/."
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario name to run. Repeat to run multiple scenarios.",
    )
    parser.add_argument(
        "--results-dir",
        default="results_test",
        help="Directory used for saved media and JSON summaries.",
    )
    return parser


def main() -> None:
    """Run the selected scenarios."""
    parser = build_parser()
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    scenarios = _select_scenarios(args.scenario)
    client = Cleanvoice.from_env()

    try:
        for scenario in scenarios:
            try:
                run_scenario(client, scenario, results_dir)
            except Exception as error:
                summary_path = results_dir / f"{scenario.name}.json"
                _write_error_summary(scenario, summary_path, error)
                print(f"Scenario failed: {scenario.name}")
                print(f"Saved error summary: {summary_path}")
                print(f"Error: {error}")
    finally:
        client.close()

    print(f"\nFinished. Review artifacts in: {results_dir.resolve()}")


if __name__ == "__main__":
    main()
