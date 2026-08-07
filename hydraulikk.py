import math
import numpy as np


def beregn_hastighet(q, d):
    """
    v = Q / A
    A = pi*d^2/4
    """
    areal = math.pi * d**2 / 4.0
    return q / areal


def beregn_reynolds(v, d, nu):
    """
    Re = v*d/nu
    """
    return v * d / nu


def colebrook_white(Re, k, d, tol=1e-10, maks_iter=100):
    """
    Løser Colebrook-White iterativt.
    Returnerer Darcy friksjonsfaktor f.
    """
    if Re <= 0 or d <= 0:
        return np.nan

    if Re < 2300:
        return 64.0 / Re

    f = 0.25 / (math.log10(k / (3.7 * d) + 5.74 / (Re**0.9)) ** 2)

    for _ in range(maks_iter):
        hoyre_side = -2.0 * math.log10(
            (k / d) / 3.7 + 2.51 / (Re * math.sqrt(f))
        )

        f_ny = 1.0 / hoyre_side**2

        if abs(f_ny - f) < tol:
            return f_ny

        f = f_ny

    return f


def beregn_friksjonstap(f, L, v, d, g):
    """
    Hf = f * L/D * v^2/(2g)
    """
    return f * L / d * v**2 / (2.0 * g)


def beregn_singulaertap(Tk, v, g):
    """
    St = Tk * v^2/(2g)
    """
    return Tk * v**2 / (2.0 * g)


def beregn_skjaerspenning(gamma, d, Hf, L):
    """
    Tau = gamma * d * Hf / (4L)
    """
    return gamma * d * Hf / (4.0 * L)


def beregn_indre_diameter(DN_mm, SDR):
    """
    Beregner innvendig diameter fra DN/OD og SDR.
    Returnerer diameter i mm.
    """
    return DN_mm * (1.0 - 2.0 / SDR)


def beregn_tillatt_trykk_bar(SDR, sigma_mpa):
    """
    Tillatt innvendig trykk for et rør med gitt SDR:

        p = 2*sigma / (SDR - 1)

    Der sigma er dimensjonerende ringspenning/materialspenning i MPa.
    Returnerer tillatt trykk i bar (1 MPa = 10 bar).
    """
    p_mpa = 2.0 * sigma_mpa / (SDR - 1.0)
    return p_mpa * 10.0


def beregn_trykk_fra_lofte(H_total_m, gamma_n_m3):
    """
    Konverterer total løftehøyde/tap [m vannsøyle] til trykk [bar].
    1 bar = 100 000 Pa.
    """
    p_pa = gamma_n_m3 * H_total_m
    return p_pa / 100_000.0