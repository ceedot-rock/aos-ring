"""
Free-space optical memory channel simulator.

Architecture (Corey's 2026-09-27 2am design, address space extended same
night): data pages are bit arrays carried as sustained free-space
interference patterns. Each page lives at an
(angle, color, freq, pol) address:
  - angle: mirror position sets where the pattern forms (detector region)
  - color: coarse wavelength band (e.g. 405/450/520/650 nm diode colors)
  - freq:  fine DWDM-style channels within each band (e.g. 100 GHz grid)
  - pol:   polarization, H/V (nearly free via polarizing beamsplitter)
  - oam:   orbital angular momentum modes, l = -4..+4 (9 modes),
           sorted by a log-polar mode sorter (imperfect: modeled)
Readout = detector array thresholding fringe intensity. Associative mode
("optical autonomous dictionary"): correlate a noisy partial query against
all live entries simultaneously; winner-take-all picks the best match.

NOTE on color vs freq: same physics (c = lambda*nu). "Color" = widely
separated coarse bands (cheap diodes/filters); "freq" = finely spaced
channels inside each band. Two-level hierarchy (band x channel), NOT double
counting. See SIM_NOTES.md.

This module simulates the channel math, not per-photon wave propagation.
Every physical assumption is documented in SIM_NOTES.md.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Default physical-ish parameters. See SIM_NOTES.md for justification.
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    page_shape=(64, 64),        # pixels per page (bits per page = 4096)
    wavelengths_nm=(405.0, 450.0, 520.0, 650.0),  # coarse color bands
    angle_spacing_deg=2.0,      # angular separation between angle channels
    beam_width_deg=0.77,        # 1/e^2 angular radius of a page beam
                                # (spacing/width = 2.6 -> adjacent crosstalk ~1.2e-3)
    color_leakage=1e-3,         # coarse-band leakage into other bands
                                # (dichroic / detector spectral imperfection)
    freq_leakage=3e-3,          # leakage into ADJACENT fine freq channels
                                # (~25 dB adjacent-channel isolation, 100 GHz DWDM)
    pol_leakage=1e-3,           # cross-polarization leakage H<->V
                                # (PBS extinction ~1000:1)
    oam_leakage=2e-2,            # ADJACENT OAM-mode sorter crosstalk (~-17 dB;
                                # good log-polar sorters do -15 to -20 dB).
                                # Non-adjacent modes get oam_leakage/10
                                # (approximate falloff; see SIM_NOTES.md).
    photons_per_bit=1e4,        # detected photons per bright pixel per readout
    jitter_sigma=0.05,          # phase-jitter (vibration) amplitude noise,
                                # in units of signal (bright pixel = 1.0)
    drift_sigma_deg=0.05,       # thermal angle wander std per page beam
    threshold=0.5,              # detector decision threshold
)


def angle_weights(n_angles, spacing_deg=DEFAULTS["angle_spacing_deg"],
                  beam_width_deg=DEFAULTS["beam_width_deg"],
                  drift_sigma_deg=0.0, rng=None):
    """Crosstalk weight matrix W where W[i, j] = fraction of page j's beam
    intensity landing in detector region i.

    Beam j is centered at j*spacing + drift_j (drift = thermal wander;
    detector regions are fixed). Gaussian beam profile:
        W[i,j] = exp(-(sep / beam_width)^2),  sep = (j-i)*spacing + drift_j
    Diagonal is ~1 (self), slightly reduced if the beam drifted off-center.
    """
    rng = np.random.default_rng(rng)
    if drift_sigma_deg > 0:
        drift = rng.normal(0.0, drift_sigma_deg, size=n_angles)
    else:
        drift = np.zeros(n_angles)
    i = np.arange(n_angles)[:, None].astype(float)
    j = np.arange(n_angles)[None, :].astype(float)
    sep = (j - i) * spacing_deg + drift[None, :]
    return np.exp(-((sep / beam_width_deg) ** 2))


def channel_matrix(n_angles, n_colors, n_freq, n_pol, n_oam=1, p=None, rng=None):
    """Full product-space crosstalk matrix, shape (N_CH, N_CH).

    Channel index ravel order: ((((angle*C + color)*F + freq)*P + pol)*L + oam),
    i.e. angle slowest, OAM fastest. The full matrix is the Kronecker product
    W_angle (x) W_color (x) W_freq (x) W_pol (x) W_oam:
      - W_angle: Gaussian beam tails (angle_weights above)
      - W_color: 1 on diagonal, color_leakage off-diagonal (all pairs;
                 coarse bands are far apart, leakage is filter-limited)
      - W_freq:  1 on diagonal, freq_leakage on ADJACENT fine channels only
      - W_pol:   1 on diagonal, pol_leakage off-diagonal (H<->V)
      - W_oam:   1 on diagonal, oam_leakage on ADJACENT l modes,
                 oam_leakage/10 on non-adjacent (mode-sorter imperfection;
                 strongest between adjacent l, see SIM_NOTES.md)
    """
    p = dict(DEFAULTS) if p is None else p
    Wa = angle_weights(n_angles, p["angle_spacing_deg"], p["beam_width_deg"],
                       p["drift_sigma_deg"], rng=rng)
    Wc = np.full((n_colors, n_colors), p["color_leakage"])
    np.fill_diagonal(Wc, 1.0)
    Wf = np.eye(n_freq)
    if n_freq > 1 and p["freq_leakage"] > 0:
        Wf = Wf + p["freq_leakage"] * (np.eye(n_freq, k=1) + np.eye(n_freq, k=-1))
    Wp = np.full((n_pol, n_pol), p["pol_leakage"])
    np.fill_diagonal(Wp, 1.0)
    Wo = np.eye(n_oam)
    if n_oam > 1 and p["oam_leakage"] > 0:
        adj = np.eye(n_oam, k=1) + np.eye(n_oam, k=-1)
        nonadj = np.ones((n_oam, n_oam)) - np.eye(n_oam) - adj
        Wo = Wo + p["oam_leakage"] * adj + (p["oam_leakage"] / 10.0) * nonadj
    Wfull = Wa
    for Wx in (Wc, Wf, Wp, Wo):
        Wfull = np.kron(Wfull, Wx)
    return Wfull


def simulate_readout(pages_bits, rng=None, **overrides):
    """Push pages through the simulated optics.

    pages_bits: uint8 array, (A, C, H, W) [legacy: F=P=L=1],
        (A, C, F, P, H, W) [legacy: L=1], or (A, C, F, P, L, H, W),
        values {0,1}.
    Returns (values, decisions):
        values    - float detector readout per address pixel
        decisions - uint8 hard decisions after thresholding
    Channel: full product-space crosstalk (channel_matrix) + Gaussian noise
    (phase jitter + shot noise combined), then threshold at 0.5.
    """
    p = dict(DEFAULTS)
    p.update(overrides)
    rng = np.random.default_rng(rng)

    pb = np.asarray(pages_bits)
    if pb.ndim == 4:                      # (A, C, H, W) -> (A, C, 1, 1, 1, H, W)
        pb = pb[:, :, None, None, None, :, :]
    elif pb.ndim == 6:                    # (A, C, F, P, H, W) -> add L axis
        pb = pb[:, :, :, :, None, :, :]
    assert pb.ndim == 7, f"expected 4D, 6D or 7D pages, got {pb.ndim}D"
    s = pb.astype(float)
    n_a, n_c, n_f, n_p, n_l, h, wd = s.shape

    Wfull = channel_matrix(n_a, n_c, n_f, n_p, n_l, p, rng=rng)
    n_ch = n_a * n_c * n_f * n_p * n_l
    r = (Wfull @ s.reshape(n_ch, -1)).reshape(n_a, n_c, n_f, n_p, n_l, h, wd)

    # Noise: phase jitter (vibration -> fringe amplitude fluctuation,
    # linearized as additive) + shot noise (1/sqrt(N) in signal units).
    sigma = float(np.sqrt(p["jitter_sigma"] ** 2 +
                          1.0 / p["photons_per_bit"]))
    r = r + rng.normal(0.0, sigma, size=r.shape)

    decisions = (r > p["threshold"]).astype(np.uint8)
    return r, decisions


def ber(a, b):
    """Bit error rate between two uint8 {0,1} arrays."""
    a = np.asarray(a, dtype=np.uint8)
    b = np.asarray(b, dtype=np.uint8)
    return float(np.mean(a != b))


def qfunc(x):
    """Q-function via erfc, for theoretical BER of OOK at threshold 0.5."""
    from math import erfc, sqrt
    return 0.5 * erfc(x / sqrt(2.0))


def theory_ber(sigma):
    """Theoretical BER: r = s + N(0, sigma), s in {0,1}, threshold 0.5."""
    return qfunc(0.5 / sigma)


def bits_to_pages(data: bytes, page_shape=DEFAULTS["page_shape"]):
    """Pack bytes into (n_pages, H, W) uint8 bit arrays, MSB-first."""
    H, Wd = page_shape
    bits_per_page = H * Wd
    total_bits = len(data) * 8
    n_pages = (total_bits + bits_per_page - 1) // bits_per_page
    arr = np.zeros(n_pages * bits_per_page, dtype=np.uint8)
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    arr[:total_bits] = bits
    return arr.reshape(n_pages, H, Wd)


def pages_to_bits(pages):
    """Unpack (n_pages, H, W) uint8 bit arrays back to bytes."""
    flat = np.asarray(pages, dtype=np.uint8).reshape(-1)
    # trim to whole bytes
    n_bytes = flat.size // 8
    return np.packbits(flat[:n_bytes * 8]).tobytes()


# ---------------------------------------------------------------------------
# aOs tube geometry helpers (M5/M6)
# ---------------------------------------------------------------------------

def tube_orientations(n_tubes):
    """Diameter orientations in degrees for n_tubes laser tubes.

    Tube t sits at t*180/n_tubes degrees. Diameters are undirected lines,
    so orientations span 180 deg, not 360. Every diameter crosses at the
    center: the center is the Ring.
    """
    return np.array([t * 180.0 / n_tubes for t in range(n_tubes)])


def human_view(values):
    """The 'human view': total intensity integrated over every channel axis.

    values: (T, C, F, P, L, H, W) analog readout -> (H, W) glow image.
    This is what a bare sensor (or an eye) with NO spectral / angular /
    polarization / OAM (orbital angular momentum) decomposition optics sees:
    the information lives in the decomposition, so the glow alone cannot
    unmix the channels.
    """
    v = np.asarray(values, dtype=float)
    assert v.ndim == 7, f"expected 7D readout, got {v.ndim}D"
    return v.sum(axis=(0, 1, 2, 3, 4))
