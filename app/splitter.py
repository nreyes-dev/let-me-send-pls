from __future__ import annotations

import json
import re
import subprocess
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

SAFETY_FRACTION = 0.92
AUDIO_KBPS = 128
KEYFRAME_SEC = 2

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
    _encoder: Optional[tuple[str, int]] = None

    @staticmethod
    def supported_extensions() -> set[str]:
        return {
            ".mp4", ".mov", ".avi", ".mkv", ".webm",
            ".flv", ".wmv", ".m4v", ".ts", ".mts",
        }

    @classmethod
    def _pick_encoder(cls) -> tuple[str, int]:
        """Return (encoder, crf). Prefer H.265 for ~40-50% better compression."""
        if cls._encoder is None:
            r = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True,
            )
            if "libx265" in r.stdout:
                cls._encoder = ("libx265", 28)
            else:
                cls._encoder = ("libx264", 23)
        return cls._encoder

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

    # ------------------------------------------------------------------

    def _compress(
        self,
        src: Path,
        dst: Path,
        duration: float,
        on_progress: Optional[ProgressCallback],
    ) -> Optional[str]:
        """Compress video to H.265 (or H.264 fallback) MP4 with CRF.

        Returns None on success, or an error string.
        """
        encoder, crf = self._pick_encoder()
        codec_label = encoder.replace("lib", "").upper()
        tag_args = ["-tag:v", "hvc1"] if encoder == "libx265" else []
        extra = ["-x265-params", "log-level=error"] if encoder == "libx265" else []

        cmd = [
            "ffmpeg", "-hide_banner", "-y",
            "-i", str(src),
            "-c:v", encoder, "-crf", str(crf),
            "-preset", "medium", "-pix_fmt", "yuv420p",
            *tag_args, *extra,
            "-force_key_frames",
            f"expr:gte(t,n_forced*{KEYFRAME_SEC})",
            "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-ac", "2",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            str(dst),
        ]

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

        # Drain stderr in a background thread to prevent the OS pipe
        # buffer from filling up and deadlocking ffmpeg.
        stderr_chunks: list[str] = []

        def _drain_stderr():
            assert proc.stderr is not None
            for line in proc.stderr:
                stderr_chunks.append(line)

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        time_re = re.compile(r"out_time_us=(\d+)")
        if proc.stdout:
            for line in proc.stdout:
                m = time_re.search(line)
                if m and duration > 0 and on_progress:
                    raw = min(int(m.group(1)) / (duration * 1e6), 1.0)
                    pct = raw * 0.88
                    on_progress(
                        pct,
                        f"Compressing ({codec_label})\u2026 {raw * 100:.0f}%",
                    )

        proc.wait()
        stderr_thread.join(timeout=5)

        if proc.returncode != 0:
            return "".join(stderr_chunks)[-800:]
        return None

    @staticmethod
    def _keyframe_positions(src: Path) -> list[tuple[float, int]]:
        """Return [(timestamp, byte_offset)] for every video keyframe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-skip_frame", "nokey",
            "-show_entries", "frame=pts_time,pkt_pos",
            "-of", "csv=p=0",
            str(src),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        result: list[tuple[float, int]] = []
        for line in r.stdout.strip().split("\n"):
            if not line:
                continue
            cols = line.split(",")
            if len(cols) >= 2:
                try:
                    result.append((float(cols[0]), int(cols[1])))
                except (ValueError, IndexError):
                    continue
        return result

    @staticmethod
    def _split_at_times(
        src: Path, output_dir: Path, prefix: str, times: list[float],
    ) -> Optional[str]:
        """Stream-copy split at the given timestamps (fast, no re-encode)."""
        pattern = str(output_dir / f"{prefix}_part%03d.mp4")
        times_str = ",".join(f"{t:.6f}" for t in times)
        cmd = [
            "ffmpeg", "-hide_banner", "-y",
            "-i", str(src),
            "-c", "copy",
            "-f", "segment",
            "-segment_times", times_str,
            "-reset_timestamps", "1",
            pattern,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return r.stderr[-800:]
        return None

    def _compute_split_times(
        self, src: Path, target_bytes: int,
    ) -> list[float]:
        """Analyze keyframe byte offsets and find where to cut so each
        segment stays within *target_bytes* (with a small margin for
        per-segment container overhead)."""
        keyframes = self._keyframe_positions(src)
        if len(keyframes) < 2:
            return []

        budget = int(target_bytes * 0.98)  # 2 % margin for moov overhead
        split_times: list[float] = []
        last_split_pos = keyframes[0][1]
        prev_kf = keyframes[0]

        for ts, pos in keyframes[1:]:
            if pos - last_split_pos >= budget:
                if prev_kf[1] > last_split_pos:
                    split_times.append(prev_kf[0])
                    last_split_pos = prev_kf[1]
                else:
                    # Single GOP exceeds budget — accept the oversized segment
                    split_times.append(ts)
                    last_split_pos = pos
            prev_kf = (ts, pos)

        return split_times

    # ------------------------------------------------------------------

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

        if duration <= 0:
            return SplitResult(error="Cannot determine video duration.")

        target_bytes = int(max_size_mb * 1024 * 1024)
        prefix = input_path.stem

        # Phase 1 — compress to the most efficient format (CRF = best
        # quality-per-byte; H.265 when available, H.264 fallback).
        compressed = output_dir / f".{prefix}_compressed.mp4"
        if on_progress:
            on_progress(0.0, "Compressing\u2026")

        err = self._compress(input_path, compressed, duration, on_progress)
        if err is not None:
            compressed.unlink(missing_ok=True)
            return SplitResult(error=f"Compression failed:\n{err}")

        comp_size = compressed.stat().st_size

        # Phase 2a — already fits in a single part after compression.
        if comp_size <= target_bytes:
            dest = output_dir / f"{prefix}_part000.mp4"
            compressed.rename(dest)
            if on_progress:
                on_progress(0.95, "Generating preview\u2026")
            thumb = output_dir / ".thumbs" / f"{dest.stem}.jpg"
            self._thumbnail(dest, thumb)
            if on_progress:
                on_progress(1.0, "Done \u2014 fits in 1 part!")
            return SplitResult(parts=[
                SplitPart(
                    path=dest,
                    thumbnail=thumb if thumb.exists() else None,
                    size_bytes=dest.stat().st_size,
                ),
            ])

        # Phase 2b — analyze keyframe byte positions and split by size.
        if on_progress:
            on_progress(0.89, "Analyzing\u2026")

        split_times = self._compute_split_times(compressed, target_bytes)
        n_parts = len(split_times) + 1

        if on_progress:
            on_progress(0.90, f"Splitting into {n_parts} parts\u2026")

        err = self._split_at_times(
            compressed, output_dir, prefix, split_times,
        )
        compressed.unlink(missing_ok=True)
        if err is not None:
            return SplitResult(error=f"Split failed:\n{err}")

        parts = sorted(output_dir.glob(f"{prefix}_part*.mp4"))
        if not parts:
            return SplitResult(error="No output files produced.")

        # Phase 3 — thumbnails.
        if on_progress:
            on_progress(0.95, "Generating previews\u2026")

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
