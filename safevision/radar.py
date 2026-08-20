"""
24 GHz FMCW radar front-end model and signal-processing chain.

This is the working core of SafeVision: it takes the raw ADC beat signal of an
FMCW (Frequency Modulated Continuous Wave) radar and turns it into a list of
detected targets with range and radial velocity.

Chain:  ADC cube -> Range FFT -> Doppler FFT -> CA-CFAR -> peak grouping

Everything is pure Python (standard library only) so it can be executed on any
machine, and so it maps 1:1 onto the fixed-point implementation that runs on the
vehicle-side MCU.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from typing import List, Sequence

SPEED_OF_LIGHT = 299_792_458.0  # m/s


@dataclass(frozen=True)
class RadarConfig:
    """Parameters of the 24 GHz FMCW sensor used by SafeVision."""

    center_frequency: float = 24.125e9  # Hz  (24 GHz ISM band)
    bandwidth: float = 250e6            # Hz  sweep bandwidth
    chirp_duration: float = 64e-6       # s   up-sweep time
    sample_rate: float = 4.0e6          # Hz  ADC sample rate
    samples_per_chirp: int = 256
    chirps_per_frame: int = 64

    @property
    def wavelength(self) -> float:
        return SPEED_OF_LIGHT / self.center_frequency

    @property
    def range_resolution(self) -> float:
        """Smallest separation between two distinguishable targets, in metres."""
        return SPEED_OF_LIGHT / (2.0 * self.bandwidth)

    @property
    def max_range(self) -> float:
        """Unambiguous range given the ADC sample rate, in metres."""
        return self.range_resolution * self.samples_per_chirp / 2.0

    @property
    def velocity_resolution(self) -> float:
        """Smallest distinguishable radial velocity difference, in m/s."""
        frame_time = self.chirp_duration * self.chirps_per_frame
        return self.wavelength / (2.0 * frame_time)

    @property
    def max_velocity(self) -> float:
        """Unambiguous radial velocity (+/-), in m/s."""
        return self.wavelength / (4.0 * self.chirp_duration)

    @property
    def sweep_slope(self) -> float:
        """Chirp slope in Hz/s."""
        return self.bandwidth / self.chirp_duration


@dataclass(frozen=True)
class Detection:
    """One target found in a single radar frame."""

    range_m: float
    velocity_mps: float  # negative = closing on the sensor
    snr_db: float

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.range_m:6.1f} m  {self.velocity_mps:+6.1f} m/s  {self.snr_db:5.1f} dB"


def _dft(samples: Sequence[complex]) -> List[complex]:
    """Discrete Fourier transform.

    Radix-2 Cooley-Tukey when the length is a power of two (the case for every
    real frame), with a direct DFT fallback so the function stays total.
    """
    n = len(samples)
    if n <= 1:
        return list(samples)
    if n & (n - 1) == 0:
        even = _dft(samples[0::2])
        odd = _dft(samples[1::2])
        out = [0j] * n
        for k in range(n // 2):
            twiddle = cmath.exp(-2j * math.pi * k / n) * odd[k]
            out[k] = even[k] + twiddle
            out[k + n // 2] = even[k] - twiddle
        return out
    return [
        sum(samples[t] * cmath.exp(-2j * math.pi * k * t / n) for t in range(n))
        for k in range(n)
    ]


def _hann(n: int) -> List[float]:
    """Hann window - suppresses spectral leakage from strong nearby clutter."""
    if n == 1:
        return [1.0]
    return [0.5 * (1.0 - math.cos(2.0 * math.pi * i / (n - 1))) for i in range(n)]


def range_doppler_map(frame: Sequence[Sequence[complex]], cfg: RadarConfig) -> List[List[float]]:
    """Build the range-Doppler power map from one ADC frame.

    ``frame`` is indexed ``[chirp][sample]``. The result is indexed
    ``[range_bin][doppler_bin]`` and holds linear power values.
    """
    n_chirps = len(frame)
    n_samples = len(frame[0])

    range_window = _hann(n_samples)
    # Range FFT: one transform per chirp, keep the positive-frequency half.
    range_spectra = [
        _dft([s * w for s, w in zip(chirp, range_window)])[: n_samples // 2]
        for chirp in frame
    ]

    doppler_window = _hann(n_chirps)
    rd_map: List[List[float]] = []
    for range_bin in range(n_samples // 2):
        column = [range_spectra[c][range_bin] * doppler_window[c] for c in range(n_chirps)]
        spectrum = _dft(column)
        # fftshift so that index 0 is the most-negative (closing) velocity.
        half = n_chirps // 2
        shifted = spectrum[half:] + spectrum[:half]
        rd_map.append([abs(v) ** 2 for v in shifted])
    return rd_map


def ca_cfar(
    rd_map: Sequence[Sequence[float]],
    guard: int = 2,
    training: int = 6,
    threshold_db: float = 18.0,
) -> List[Detection]:
    """Cell-Averaging CFAR over the range dimension.

    For every cell the noise floor is estimated from the training cells on both
    sides (skipping the guard cells that would be polluted by the target's own
    energy). A cell is a detection when it exceeds that floor by
    ``threshold_db``. This keeps the false-alarm rate constant as road clutter
    changes, which is what makes the detector usable at highway speed.
    """
    cells: List[tuple] = []
    n_range = len(rd_map)
    n_doppler = len(rd_map[0])

    for doppler_bin in range(n_doppler):
        column = [rd_map[r][doppler_bin] for r in range(n_range)]
        for r in range(n_range):
            lo = max(0, r - guard - training)
            hi = min(n_range, r + guard + training + 1)
            noise = [
                column[i]
                for i in range(lo, hi)
                if abs(i - r) > guard
            ]
            if not noise:
                continue
            noise_floor = sum(noise) / len(noise)
            if noise_floor <= 0.0:
                continue
            snr_db = 10.0 * math.log10(column[r] / noise_floor) if column[r] > 0 else -math.inf
            if snr_db >= threshold_db:
                cells.append((r, doppler_bin, snr_db))
    return cells  # type: ignore[return-value]


def detect(frame: Sequence[Sequence[complex]], cfg: RadarConfig, threshold_db: float = 18.0) -> List[Detection]:
    """Full front-end: raw ADC frame in, physical detections out."""
    rd_map = range_doppler_map(frame, cfg)
    raw_cells = ca_cfar(rd_map, threshold_db=threshold_db)
    if not raw_cells:
        return []

    # Group neighbouring CFAR cells that belong to the same physical object and
    # keep the strongest cell of each group as its representative.
    raw_cells.sort(key=lambda c: c[2], reverse=True)
    peaks: List[tuple] = []
    for range_bin, doppler_bin, snr_db in raw_cells:
        # One road hazard occupies one range gate; sidelobes leak into the
        # neighbouring range and Doppler bins, so keep only the strongest cell
        # in that neighbourhood.
        if any(abs(range_bin - pr) <= 2 for pr, _, _ in peaks):
            continue
        peaks.append((range_bin, doppler_bin, snr_db))

    n_doppler = cfg.chirps_per_frame
    detections = [
        Detection(
            range_m=range_bin * cfg.range_resolution,
            velocity_mps=(doppler_bin - n_doppler // 2) * cfg.velocity_resolution,
            snr_db=snr_db,
        )
        for range_bin, doppler_bin, snr_db in peaks
    ]
    detections.sort(key=lambda d: d.range_m)
    return detections
