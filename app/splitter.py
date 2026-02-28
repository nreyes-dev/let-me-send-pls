from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

SAFETY_FRACTION = 0.92
DEFAULT_AUDIO_KBPS = 128

ProgressCallback = Callable[[float, str], None]


@dataclass
class SplitPart:
    path: Path
    thumbnail: Optional[Path] = None
    size_bytes: int = 0


@dataclass
class SplitResult:
    parts: list[SplitPart] = field(default_factory=list)
    error: Optional[str] = None


class Splitter(ABC):
    """Base class for file splitters. Subclass to support new file types."""

    @staticmethod
    @abstractmethod
    def supported_extensions() -> set[str]: ...

    @abstractmethod
    def split(
        self,
        input_path: Path,
        output_dir: Path,
        max_size_mb: float,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SplitResult: ...


class VideoSplitter(Splitter):
    THUMB_SIZE = 180

    @staticmethod
    def supported_extensions() -> set[str]:
        return {
            ".mp4", ".mov", ".avi", ".mkv", ".webm",
            ".flv", ".wmv", ".m4v", ".ts", ".mts",
        }

    @staticmethod
    def _probe(path: Path) -> dict:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(r.stdout)

    @classmethod
    def _thumbnail(cls, video: Path, out: Path) -> None:
        s = cls.THUMB_SIZE
        out.parent.mkdir(parents=True, exist_ok=True)
        vf = (
            f"scale={s}:{s}:force_original_aspect_ratio=decrease,"
            f"pad={s}:{s}:(ow-iw)/2:(oh-ih)/2:color=#1e1e2e"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", "0.5",
                "-i", str(video),
                "-vframes", "1", "-vf", vf, "-q:v", "3",
                str(out),
            ],
            capture_output=True, check=False,
        )

    def split(
        self,
        input_path: Path,
        output_dir: Path,
        max_size_mb: float,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SplitResult:
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            info = self._probe(input_path)
        except Exception as exc:
            return SplitResult(error=f"Cannot read video: {exc}")

        fmt = info.get("format", {})
        duration = float(fmt.get("duration", 0))
        file_size = int(fmt.get("size", 0))

        if duration <= 0 or file_size <= 0:
            return SplitResult(error="Cannot determine video duration or file size.")

        target_bytes = int(max_size_mb * 1024 * 1024)

        if file_size <= target_bytes:
            dest = output_dir / f"{input_path.stem}_part000.mp4"
            shutil.copy2(input_path, dest)
            thumb = output_dir / ".thumbs" / f"{dest.stem}.jpg"
            self._thumbnail(dest, thumb)
            return SplitResult(parts=[
                SplitPart(path=dest, thumbnail=thumb, size_bytes=dest.stat().st_size),
            ])

        n_parts = math.ceil(file_size / target_bytes)
        seg_dur = duration / n_parts
        audio_kbps = DEFAULT_AUDIO_KBPS
        total_kbps = max(200.0, (target_bytes * 8 / seg_dur) / 1000 * SAFETY_FRACTION)
        video_kbps = max(100.0, total_kbps - audio_kbps - 64)

        prefix = input_path.stem
        pattern = str(output_dir / f"{prefix}_part%03d.mp4")

        cmd = [
            "ffmpeg", "-hide_banner", "-y",
            "-i", str(input_path),
            "-c:v", "libx264", "-preset", "veryfast",
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-b:v", f"{video_kbps:.0f}k",
            "-maxrate", f"{video_kbps:.0f}k",
            "-bufsize", f"{int(video_kbps * 2)}k",
            "-g", "48", "-keyint_min", "48", "-sc_threshold", "0",
            "-force_key_frames", f"expr:gte(t,n_forced*{seg_dur})",
            "-c:a", "aac", "-b:a", f"{audio_kbps}k", "-ac", "2",
            "-movflags", "+faststart",
            "-f", "segment", "-segment_time", str(seg_dur),
            "-reset_timestamps", "1",
            "-progress", "pipe:1",
            pattern,
        ]

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

        time_re = re.compile(r"out_time_us=(\d+)")
        if proc.stdout:
            for line in proc.stdout:
                m = time_re.search(line)
                if m and duration > 0:
                    us = int(m.group(1))
                    pct = min(us / (duration * 1_000_000), 0.95)
                    if on_progress:
                        on_progress(pct, f"Encoding\u2026 {pct * 100:.0f}%")

        proc.wait()

        if proc.returncode != 0:
            err = proc.stderr.read() if proc.stderr else ""
            return SplitResult(
                error=f"ffmpeg failed (code {proc.returncode}):\n{err[-800:]}"
            )

        parts = sorted(output_dir.glob(f"{prefix}_part*.mp4"))
        if not parts:
            return SplitResult(error="ffmpeg produced no output files.")

        if on_progress:
            on_progress(0.97, "Generating previews\u2026")

        result_parts: list[SplitPart] = []
        for p in parts:
            thumb = output_dir / ".thumbs" / f"{p.stem}.jpg"
            self._thumbnail(p, thumb)
            result_parts.append(SplitPart(
                path=p,
                thumbnail=thumb if thumb.exists() else None,
                size_bytes=p.stat().st_size,
            ))

        if on_progress:
            on_progress(1.0, "Done!")

        return SplitResult(parts=result_parts)


# Registry — extend this list when adding support for new file types.
_SPLITTERS: list[type[Splitter]] = [VideoSplitter]


def get_splitter(path: Path) -> Optional[Splitter]:
    ext = path.suffix.lower()
    for cls in _SPLITTERS:
        if ext in cls.supported_extensions():
            return cls()
    return None
