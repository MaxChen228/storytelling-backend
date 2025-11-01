#!/usr/bin/env python3
"""Montreal Forced Aligner (MFA) helpers for word-level subtitles."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, Tuple, List

from pydub import AudioSegment
from praatio import textgrid

TOKEN_RE = re.compile(r"[A-Za-z']+")


class MfaAlignmentError(RuntimeError):
    """Raised when MFA alignment fails."""


@dataclass
class MfaConfig:
    """Configuration for running MFA alignment."""

    micromamba_bin: str = "micromamba"
    env_name: str = "aligner"
    dictionary: str = "english_mfa"
    acoustic_model: str = "english_mfa"
    temp_root: Path = Path("./.mfa_work")
    keep_workdir: bool = False
    keep_intermediate: bool = False
    transcript_suffix: str = "_mfa.txt"
    extra_args: Sequence[str] = field(default_factory=tuple)

    def ensure_temp_root(self) -> Path:
        self.temp_root.mkdir(parents=True, exist_ok=True)
        return self.temp_root


@dataclass
class AlignmentResult:
    """Information about a completed MFA alignment."""

    srt_path: Path
    textgrid_path: Path | None
    transcript_path: Path | None
    matched_tokens: int
    missing_tokens: int
    total_tokens: int

    def as_metadata(self) -> dict:
        return {
            "alignment_mode": "mfa",
            "alignment_srt": str(self.srt_path),
            "alignment_textgrid": str(self.textgrid_path) if self.textgrid_path else None,
            "alignment_transcript": str(self.transcript_path) if self.transcript_path else None,
            "alignment_matched": self.matched_tokens,
            "alignment_missing": self.missing_tokens,
            "alignment_total_tokens": self.total_tokens,
        }


def build_config_from_dict(config: Mapping[str, Any] | None) -> MfaConfig:
    """Create :class:`MfaConfig` from a nested configuration dictionary."""

    base = MfaConfig()
    alignment_cfg: Mapping[str, Any] | None = None
    if isinstance(config, Mapping):
        alignment_cfg = config.get("alignment") if isinstance(config.get("alignment"), Mapping) else None

    mfa_cfg: Mapping[str, Any] | None = None
    if alignment_cfg and isinstance(alignment_cfg.get("mfa"), Mapping):
        mfa_cfg = alignment_cfg.get("mfa")  # type: ignore[assignment]

    if not isinstance(mfa_cfg, Mapping):
        mfa_cfg = {}

    temp_root_value = mfa_cfg.get("temp_root", base.temp_root)
    if isinstance(temp_root_value, (str, Path)):
        temp_root = Path(temp_root_value).expanduser()
    else:
        temp_root = base.temp_root

    extra_args_value = mfa_cfg.get("extra_args", base.extra_args)
    if isinstance(extra_args_value, str):
        extra_args = (extra_args_value,)
    elif isinstance(extra_args_value, Iterable):
        extra_args = tuple(str(item) for item in extra_args_value)
    else:
        extra_args = base.extra_args

    return MfaConfig(
        micromamba_bin=str(mfa_cfg.get("micromamba_bin", base.micromamba_bin)),
        env_name=str(mfa_cfg.get("env_name", base.env_name)),
        dictionary=str(mfa_cfg.get("dictionary", base.dictionary)),
        acoustic_model=str(mfa_cfg.get("acoustic_model", base.acoustic_model)),
        temp_root=temp_root,
        keep_workdir=bool(mfa_cfg.get("keep_workdir", base.keep_workdir)),
        keep_intermediate=bool(mfa_cfg.get("keep_intermediate", base.keep_intermediate)),
        transcript_suffix=str(mfa_cfg.get("transcript_suffix", base.transcript_suffix)),
        extra_args=extra_args,
    )


def clean_script_for_alignment(script_text: str) -> str:
    """Remove stage directions and non-speech annotations to improve alignment."""

    text = re.sub(r"\(pause\)", " ", script_text)
    text = re.sub(r"\([^)]*[\u4e00-\u9fff][^)]*\)", " ", text)
    text = re.sub(r"\([^)]*[A-Z]{3,}[^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\{[^}]*\}", " ", text)
    text = text.replace("—", ".").replace("...", ". ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def prepare_transcript_text(script_path: Path, output_path: Path) -> Path:
    """Create a cleaned transcript suitable for MFA."""

    raw = script_path.read_text(encoding="utf-8")
    cleaned = clean_script_for_alignment(raw)
    if not cleaned:
        raise MfaAlignmentError(f"Script is empty after cleaning: {script_path}")
    # MFA prefers shorter lines; add soft breaks after periods.
    cleaned = cleaned.replace(". ", ".\n")
    output_path.write_text(cleaned + "\n", encoding="utf-8")
    return output_path


def _copy_audio_for_alignment(audio_path: Path, destination: Path) -> None:
    if audio_path.suffix.lower() == ".wav":
        shutil.copy2(audio_path, destination)
        return

    audio = AudioSegment.from_file(audio_path)
    audio.export(destination, format="wav")


def _audio_duration_seconds(audio_path: Path) -> float:
    with wave.open(str(audio_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate() or 1
    return frames / max(rate, 1)


def _has_manual_beam(args: Sequence[str]) -> bool:
    for raw in args:
        option = raw.split("=", 1)[0]
        if option in {"--beam", "--retry_beam"}:
            return True
    return False


def _beam_settings_for_duration(seconds: float) -> Tuple[int, int]:
    if seconds <= 360:
        return 10, 40
    if seconds <= 600:
        return 60, 200
    return 100, 400


def _run_mfa_align(
    corpus_dir: Path,
    output_dir: Path,
    config: MfaConfig,
    extra_args: Sequence[str] | None = None,
) -> None:
    command: List[str] = [
        config.micromamba_bin,
        "run",
        "-n",
        config.env_name,
        "mfa",
        "align",
        str(corpus_dir),
        config.dictionary,
        config.acoustic_model,
        str(output_dir),
    ]

    combined_args: List[str] = list(config.extra_args) if config.extra_args else []
    if extra_args:
        combined_args.extend(str(arg) for arg in extra_args)
    if combined_args:
        command.extend(combined_args)
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise MfaAlignmentError(f"Unable to locate '{config.micromamba_bin}' in PATH.") from exc
    except subprocess.CalledProcessError as exc:  # pragma: no cover - external process
        raise MfaAlignmentError(
            f"MFA align command failed with exit code {exc.returncode}: {exc.stderr.decode('utf-8', errors='ignore')}"
        ) from exc


def _tokenize_transcript(transcript_path: Path) -> List[Tuple[str, str]]:
    tokens: List[Tuple[str, str]] = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        for raw in line.split():
            normalized = "".join(ch.lower() for ch in raw if ch.isalpha() or ch == "'")
            tokens.append((raw, normalized))
    return tokens


def _extract_interval_tokens(textgrid_path: Path, tier_name: str = "words") -> List[Tuple[str, float, float]]:
    grid = textgrid.openTextgrid(str(textgrid_path), includeEmptyIntervals=True)
    try:
        words_tier = grid.getTier(tier_name)
    except KeyError as exc:
        raise MfaAlignmentError(f"TextGrid missing tier '{tier_name}'") from exc

    tokens: List[Tuple[str, float, float]] = []
    for interval in words_tier.entries:
        label = interval.label.strip()
        if not label or (label.startswith("[") and label.endswith("]")):
            continue
        parts = TOKEN_RE.findall(label)
        if not parts:
            continue
        for part in parts:
            tokens.append((part.lower(), interval.start, interval.end))
    return tokens


def _align_sequences(
    reference: Sequence[str],
    hypothesis: Sequence[str],
) -> List[Tuple[int | None, int | None]]:
    n, m = len(reference), len(hypothesis)
    gap_cost = 1

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back = [[(0, 0)] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i * gap_cost
        back[i][0] = (i - 1, 0)
    for j in range(1, m + 1):
        dp[0][j] = j * gap_cost
        back[0][j] = (0, j - 1)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub_cost = dp[i - 1][j - 1] + (0 if reference[i - 1] == hypothesis[j - 1] else 1)
            del_cost = dp[i - 1][j] + gap_cost
            ins_cost = dp[i][j - 1] + gap_cost
            best_cost = sub_cost
            move = (i - 1, j - 1)
            if del_cost < best_cost:
                best_cost = del_cost
                move = (i - 1, j)
            if ins_cost < best_cost:
                best_cost = ins_cost
                move = (i, j - 1)
            dp[i][j] = best_cost
            back[i][j] = move

    alignment: List[Tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        prev_i, prev_j = back[i][j]
        if prev_i == i - 1 and prev_j == j - 1:
            alignment.append((i - 1, j - 1))
        elif prev_i == i - 1 and prev_j == j:
            alignment.append((i - 1, None))
        else:
            alignment.append((None, j - 1))
        i, j = prev_i, prev_j

    alignment.reverse()
    return alignment


def _format_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        millis = 0
        secs += 1
    if secs == 60:
        secs = 0
        minutes += 1
    if minutes == 60:
        minutes = 0
        hours += 1
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _write_srt(
    script_tokens: Sequence[Tuple[str, str]],
    interval_tokens: Sequence[Tuple[str, float, float]],
    alignment: Sequence[Tuple[int | None, int | None]],
    output_path: Path,
) -> Tuple[int, int]:
    word_indices = [idx for idx, (_, normalized) in enumerate(script_tokens) if normalized]

    matched = 0
    missing = 0
    mapped_intervals: List[int | None] = [None] * len(script_tokens)

    for ref_idx, hyp_idx in alignment:
        if ref_idx is None:
            continue
        script_idx = word_indices[ref_idx]
        if hyp_idx is None:
            missing += 1
        else:
            mapped_intervals[script_idx] = hyp_idx
            matched += 1

    last_interval: int | None = None
    for idx, (original, normalized) in enumerate(script_tokens):
        interval_idx = mapped_intervals[idx]
        if interval_idx is not None:
            last_interval = interval_idx
        elif not normalized and last_interval is not None:
            mapped_intervals[idx] = last_interval

    entries: List[str] = []
    counter = 1
    for idx, (original, normalized) in enumerate(script_tokens):
        interval_idx = mapped_intervals[idx]
        if interval_idx is None:
            continue
        start = _format_timestamp(interval_tokens[interval_idx][1])
        end = _format_timestamp(interval_tokens[interval_idx][2])
        entries.append("\n".join([str(counter), f"{start} --> {end}", original, ""]))
        counter += 1

    output_path.write_text("\n".join(entries).strip() + "\n", encoding="utf-8")
    return matched, missing


def generate_word_level_srt(
    textgrid_path: Path,
    transcript_path: Path,
    output_path: Path,
) -> Tuple[int, int, int]:
    script_tokens = _tokenize_transcript(transcript_path)
    interval_tokens = _extract_interval_tokens(textgrid_path)
    if not interval_tokens:
        raise MfaAlignmentError("No aligned intervals found in TextGrid.")

    reference = [normalized for _, normalized in script_tokens if normalized]
    hypothesis = [token for token, _, _ in interval_tokens]
    alignment = _align_sequences(reference, hypothesis)

    matched, missing = _write_srt(script_tokens, interval_tokens, alignment, output_path)

    total_tokens = sum(1 for _, normalized in script_tokens if normalized)
    return matched, missing, total_tokens


def align_chapter_with_mfa(
    chapter_dir: Path,
    config: MfaConfig | None = None,
    audio_path: Path | None = None,
) -> AlignmentResult:
    """Run MFA against a chapter directory that already contains audio and script."""

    cfg = config or MfaConfig()
    chapter_dir = chapter_dir.resolve()
    script_path = chapter_dir / "podcast_script.txt"
    audio_source = audio_path or chapter_dir / "podcast.wav"
    if not script_path.exists():
        raise MfaAlignmentError(f"Missing script: {script_path}")
    if not audio_source.exists():
        mp3_path = chapter_dir / "podcast.mp3"
        if mp3_path.exists() and audio_path is None:
            audio_source = mp3_path
        else:
            raise MfaAlignmentError(f"Missing audio for chapter: {chapter_dir}")

    transcript_path = chapter_dir / f"{script_path.stem}{cfg.transcript_suffix}"
    prepare_transcript_text(script_path, transcript_path)

    work_root = Path(tempfile.mkdtemp(prefix=f"mfa_{chapter_dir.name}_", dir=str(cfg.ensure_temp_root())))
    corpus_dir = work_root / "corpus"
    aligned_dir = work_root / "aligned"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    aligned_dir.mkdir(parents=True, exist_ok=True)

    base_name = chapter_dir.name
    corpus_audio = corpus_dir / f"{base_name}.wav"
    corpus_text = corpus_dir / f"{base_name}.txt"
    _copy_audio_for_alignment(audio_source, corpus_audio)
    shutil.copy2(transcript_path, corpus_text)

    dynamic_args: List[str] = []
    base_extra_args = list(cfg.extra_args) if cfg.extra_args else []
    if not _has_manual_beam(base_extra_args):
        duration_seconds = _audio_duration_seconds(corpus_audio)
        beam, retry = _beam_settings_for_duration(duration_seconds)
        dynamic_args.extend(["--beam", str(beam), "--retry_beam", str(retry)])
        print(
            f"   Auto-adjusted MFA beam={beam} retry={retry} "
            f"(duration {duration_seconds/60:.2f} min)"
        )

    _run_mfa_align(corpus_dir, aligned_dir, cfg, extra_args=dynamic_args)

    textgrid_path = aligned_dir / f"{base_name}.TextGrid"
    if not textgrid_path.exists():
        raise MfaAlignmentError(f"MFA did not produce TextGrid: {textgrid_path}")

    output_textgrid = chapter_dir / "alignment.TextGrid"
    shutil.copy2(textgrid_path, output_textgrid)

    srt_path = chapter_dir / "subtitles.srt"
    matched, missing, total_tokens = generate_word_level_srt(output_textgrid, transcript_path, srt_path)

    if not cfg.keep_workdir:
        shutil.rmtree(work_root, ignore_errors=True)
    else:
        (chapter_dir / "mfa_workdir.json").write_text(
            json.dumps(
                {
                    "workdir": str(work_root),
                    "corpus_audio": str(corpus_audio),
                    "corpus_text": str(corpus_text),
                    "aligned_dir": str(aligned_dir),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    textgrid_result: Path | None = output_textgrid
    transcript_result: Path | None = transcript_path

    if not cfg.keep_intermediate:
        try:
            output_textgrid.unlink()
        except FileNotFoundError:
            pass
        else:
            textgrid_result = None
        try:
            transcript_path.unlink()
        except FileNotFoundError:
            pass
        else:
            transcript_result = None

    return AlignmentResult(
        srt_path=srt_path,
        textgrid_path=textgrid_result,
        transcript_path=transcript_result,
        matched_tokens=matched,
        missing_tokens=missing,
        total_tokens=total_tokens,
    )
