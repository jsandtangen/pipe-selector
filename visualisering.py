"""Plotly-spesifikasjoner fra eksisterende resultater og kurveberegninger.

Ingen kravkontroll, rangering eller hydrauliske formler endres her.
"""

import numpy as np

from plotting import beregn_ledningskarakteristikk_data, finn_krysning_q


FARGER = ["#1764c0", "#a05b24", "#287b65", "#7756a3", "#b34f68", "#477b91", "#777126"]


def _navn(r):
    return f"DN{r.dn_od_mm:g} {r.sdr_navn}"


def _layout(x, y, xmax=None, ymax=None):
    return {
        "font": {"family": "Segoe UI, sans-serif", "size": 12, "color": "#202327"},
        "paper_bgcolor": "white", "plot_bgcolor": "white", "dragmode": "pan", "separators": ", ",
        "hovermode": "closest", "margin": {"l": 76, "r": 30, "t": 30, "b": 100, "autoexpand": False},
        "xaxis": {"title": {"text": x}, "gridcolor": "#edf0f3", "zeroline": False,
                  **({"range": [0, xmax]} if xmax else {})},
        "yaxis": {"title": {"text": y}, "gridcolor": "#edf0f3", "zeroline": False,
                  **({"range": [0, ymax]} if ymax else {})},
        "legend": {"orientation": "h", "y": -0.2, "groupclick": "togglegroup"},
        "annotations": [], "shapes": [],
    }


def _kurvegraf(ror, parametere, samlet, fargekart):
    xmax = 450 if samlet else 400
    data, annotations, shapes = [], [], []
    ymax = parametere.maks_totalt_tap_m
    for r in ror:
        navn, gruppe = _navn(r), f"{r.dn_od_mm:g}-{r.sdr:g}"
        farge = fargekart[gruppe]
        q, v, h, tau = beregn_ledningskarakteristikk_data(
            r.dn_od_mm, r.sdr, parametere, q_min=1, q_maks=xmax, antall=xmax,
        )
        q, v, h, tau = [np.asarray(a) for a in (q, v, h, tau)]
        ymax = max(ymax, float(max(h)))
        custom = np.column_stack([v, tau]).tolist()
        hover = ("Q = %{x:.2f} l/s<br>Total løftehøyde = %{y:.2f} m"
                 "<br>v = %{customdata[0]:.3f} m/s<br>τ = %{customdata[1]:.3f} Pa<extra>%{fullData.name}</extra>")
        data.append({"type": "scatter", "mode": "lines", "name": navn, "legendgroup": gruppe,
                     "x": q.tolist(), "y": h.tolist(), "customdata": custom,
                     "line": {"color": farge, "width": 1.5 if samlet else 3},
                     "opacity": 0.35 if samlet else 1, "hovertemplate": hover})
        qt = finn_krysning_q(q, tau, parametere.min_skjaerspenning_pa)
        qh = finn_krysning_q(q, h, parametere.maks_totalt_tap_m)
        if samlet and qt is not None and qh is not None and qt < qh:
            mask = (q >= qt) & (q <= qh)
            data.append({"type": "scatter", "mode": "lines", "name": navn, "legendgroup": gruppe,
                         "showlegend": False, "x": q[mask].tolist(), "y": h[mask].tolist(),
                         "customdata": np.column_stack([v[mask], tau[mask]]).tolist(),
                         "line": {"color": farge, "width": 4.5}, "hovertemplate": hover})
        punkter = []
        if samlet:
            if qt is not None:
                punkter.append((qt, f"τ = {parametere.min_skjaerspenning_pa:g} Pa"))
                shapes.append({"type": "line", "x0": qt, "x1": qt, "y0": 0, "y1": 1,
                               "yref": "paper", "name": gruppe, "line": {"color": farge, "dash": "dot", "width": 1}})
            if qh is not None:
                punkter.append((qh, f"H = {parametere.maks_totalt_tap_m:g} m"))
        else:
            punkter = [(150, "Referanse"), (300, "Referanse")]
        for x, beskrivelse in punkter:
            y, speed, shear = [float(np.interp(x, q, a)) for a in (h, v, tau)]
            data.append({"type": "scatter", "mode": "markers", "name": navn, "legendgroup": gruppe,
                         "showlegend": False, "x": [float(x)], "y": [y],
                         "marker": {"color": farge, "size": 8}, "customdata": [[speed, shear]], "hovertemplate": hover})
            annotations.append({"x": float(x), "y": y, "xref": "x", "yref": "y",
                                "axref": "pixel", "ayref": "pixel", "ax": 0, "ay": -80,
                                "text": f"{navn} · {beskrivelse}<br>Q = {x:.1f} l/s · H = {y:.2f} m<br>v = {speed:.3f} m/s · τ = {shear:.3f} Pa",
                                "showarrow": True, "arrowhead": 0, "arrowwidth": 1,
                                "arrowcolor": farge, "bordercolor": "#dce0e5", "borderwidth": 1,
                                "borderpad": 8, "bgcolor": "white", "font": {"size": 11},
                                "xanchor": "center", "yanchor": "middle", "align": "left",
                                "name": gruppe})
            if not samlet:
                shapes.extend([
                    {"type": "line", "x0": x, "x1": x, "y0": 0, "y1": y, "line": {"color": "#aab2bd", "dash": "dot", "width": 1}},
                    {"type": "line", "x0": 0, "x1": x, "y0": y, "y1": y, "line": {"color": "#aab2bd", "dash": "dot", "width": 1}},
                ])
    layout = _layout("Vannmengde Q [l/s]", "Total løftehøyde [m]", xmax, ymax * 1.08)
    if samlet:
        shapes.append({"type": "line", "x0": 0, "x1": xmax, "y0": parametere.maks_totalt_tap_m,
                       "y1": parametere.maks_totalt_tap_m, "line": {"color": "#616973", "dash": "dash", "width": 1.5}})
    layout.update(annotations=annotations, shapes=shapes)
    return {"id": "samlet" if samlet else f"ror-{ror[0].dn_od_mm:g}-{ror[0].sdr:g}",
            "tittel": "Samlet ledningskarakteristikk" if samlet else f"Ledningskarakteristikk {_navn(ror[0])}",
            "beskrivelse": (f"Tykk linje: τ ≥ {parametere.min_skjaerspenning_pa:g} Pa og totalt tap ≤ {parametere.maks_totalt_tap_m:g} m. "
                            "Dette markerer disse to kurvegrensene; øvrige prosjektkrav vurderes i resultatene.") if samlet else "Referansepunkter ved 150 og 300 l/s, som i opprinnelig graf.",
            "data": data, "layout": layout}


def lag_interaktive_grafer(resultat, valgte_ror=None, vis_prisgraf=True):
    godkjente = {(r.dn_od_mm, r.sdr): r for r in resultat.godkjente}
    valgt = list(godkjente.values()) if valgte_ror is None else []
    if valgte_ror is not None:
        for r in valgte_ror:
            key = (r.dn_od_mm, r.sdr)
            if key not in godkjente:
                raise ValueError("Bare godkjente rør kan velges til grafene.")
            if godkjente[key] not in valgt:
                valgt.append(godkjente[key])
    farger = {key: FARGER[i % len(FARGER)] for i, key in enumerate(f"{r.dn_od_mm:g}-{r.sdr:g}" for r in resultat.godkjente)}
    grafer = []
    if vis_prisgraf:
        traces = []
        for r in (resultat.godkjente or resultat.alle_resultater):
            traces.append({"type": "scatter", "mode": "markers", "name": _navn(r),
                           "legendgroup": f"{r.dn_od_mm:g}-{r.sdr:g}",
                           "x": [r.pris_mnok], "y": [r.skjaerspenning_pa],
                           "marker": {"size": max(6, min(32, r.vannhastighet_m_s * 10)), "color": farger.get(f"{r.dn_od_mm:g}-{r.sdr:g}", "#616973")},
                           "text": [_navn(r)],
                           "customdata": [[r.totalt_tap_m, r.vannhastighet_m_s]],
                           "hovertemplate": "%{text}<br>Pris = %{x:.2f} MNOK<br>τ = %{y:.3f} Pa<br>H = %{customdata[0]:.2f} m<br>v = %{customdata[1]:.3f} m/s<extra></extra>"})
        layout = _layout("Materialpris [MNOK]", "Skjærspenning τ [Pa]")
        layout["shapes"].append({"type": "line", "xref": "paper", "x0": 0, "x1": 1,
                                  "y0": resultat.input.min_skjaerspenning_pa, "y1": resultat.input.min_skjaerspenning_pa,
                                  "line": {"color": "#616973", "dash": "dash", "width": 1}})
        grafer.append({"id": "pris", "tittel": "Pris mot skjærspenning",
                       "beskrivelse": ("Godkjente alternativer. " if resultat.godkjente else "Ingen godkjente alternativer; viser alle beregnede rør. ") + "Størrelse viser hastighet. Hold pekeren over et punkt for løftehøyde og alle nøkkeltall. Stiplet linje viser minstekrav til skjærspenning.",
                       "data": traces, "layout": layout})
    if valgt:
        grafer.append(_kurvegraf(valgt, resultat.input, True, farger))
        grafer.extend(_kurvegraf([r], resultat.input, False, farger) for r in valgt)
    return grafer
