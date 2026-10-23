"""Plotly-spesifikasjoner fra eksisterende resultater og kurveberegninger.

Ingen kravkontroll, rangering eller hydrauliske formler endres her.
"""

import numpy as np

from plotting import beregn_ledningskarakteristikk_data, finn_krysning_q


FARGER = [
    "#1764c0", "#a05b24", "#287b65", "#7756a3", "#b34f68", "#477b91", "#777126",
    "#bd761b", "#4c5caa", "#9d466e", "#4b8150", "#986f48",
]


def _navn(r):
    return f"DN{r.dn_od_mm:g} {r.sdr_navn}"


def _pipe(r, parametere, farge):
    """Context values come from the calculation result, never interpolated curves."""
    return {"id": f"{r.dn_od_mm:g}-{r.sdr:g}", "label": _navn(r), "color": farge,
            "values": {"q": parametere.qdim_l_s, "h": r.totalt_tap_m,
                       "v": r.vannhastighet_m_s, "tau": r.skjaerspenning_pa,
                       "price": r.pris_mnok}, "points": []}


def _range(values, zero=True, padding=0.07):
    finite = [float(v) for v in values if np.isfinite(v)]
    if not finite:
        return [0, 1]
    low, high = min(finite), max(finite)
    if zero:
        low = min(0, low)
    span = high - low or max(abs(high), 1)
    return [min(0, low) if zero else max(0, low - span * padding), high + span * padding]


def _threshold_label(text, **position):
    return {"text": text, "showarrow": False, "font": {"size": 10, "color": "#596575"},
            "bgcolor": "rgba(255,255,255,0.92)", "borderpad": 3, **position}


def _layout(x, y, xmax=None, ymax=None):
    return {
        "font": {"family": "Segoe UI, sans-serif", "size": 12, "color": "#202327"},
        "paper_bgcolor": "white", "plot_bgcolor": "white", "dragmode": "pan", "separators": ", ",
        "hovermode": "closest", "margin": {"l": 66, "r": 18, "t": 24, "b": 50, "autoexpand": False},
        "xaxis": {"title": {"text": x}, "gridcolor": "#edf0f3", "zeroline": False,
                  **({"range": [0, xmax]} if xmax else {})},
        "yaxis": {"title": {"text": y}, "gridcolor": "#edf0f3", "zeroline": False,
                  **({"range": [0, ymax]} if ymax else {})},
        "showlegend": False,
        "legend": {"orientation": "h", "y": -0.2, "groupclick": "togglegroup"},
        "annotations": [], "shapes": [],
    }


def _kurvegraf(ror, parametere, samlet, fargekart):
    xmax = 450 if samlet else 400
    data, annotations, shapes = [], [], []
    pipes, curves, relevant_q, relevant_h = [], [], [parametere.qdim_l_s], [parametere.maks_totalt_tap_m]
    ymax = parametere.maks_totalt_tap_m
    for r in ror:
        navn, gruppe = _navn(r), f"{r.dn_od_mm:g}-{r.sdr:g}"
        farge = fargekart[gruppe]
        pipe = _pipe(r, parametere, farge)
        pipes.append(pipe)
        relevant_h.append(r.totalt_tap_m)
        q, v, h, tau = beregn_ledningskarakteristikk_data(
            r.dn_od_mm, r.sdr, parametere, q_min=1, q_maks=xmax, antall=xmax,
        )
        q, v, h, tau = [np.asarray(a) for a in (q, v, h, tau)]
        curves.append((q, h))
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
        relevant_q.extend(float(x) for x in (qt, qh) if x is not None)
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
            relevant_q.append(float(x))
            relevant_h.append(y)
            pipe["points"].append({"label": beskrivelse, "q": float(x), "h": y,
                                   "v": speed, "tau": shear, "traceIndex": len(data),
                                   "annotationIndex": len(annotations)})
            data.append({"type": "scatter", "mode": "markers", "name": navn, "legendgroup": gruppe,
                         "showlegend": False, "x": [float(x)], "y": [y],
                         "marker": {"color": farge, "size": 7, "symbol": "diamond" if beskrivelse.startswith("H =") else "circle"},
                         "text": [beskrivelse], "customdata": [[speed, shear]], "hovertemplate": "<b>%{text}</b><br>" + hover})
            annotations.append({"x": float(x), "y": y, "xref": "x", "yref": "y",
                                "axref": "pixel", "ayref": "pixel", "ax": 0, "ay": -80,
                                "text": f"<b>{navn}</b> · {beskrivelse}<br>Q {x:.1f} l/s · H {y:.2f} m<br>v {speed:.3f} m/s · τ {shear:.3f} Pa",
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
    # Fit the opening view to the operating/reference points. The original
    # sampled arrays remain intact and the complete range is available in UI.
    view_xmax = max(parametere.qdim_l_s * 1.06, min(xmax, max(relevant_q) * 1.06))
    for q, h in curves:
        relevant_h.append(float(np.interp(view_xmax, q, h)))
    view_y = _range(relevant_h)
    layout = _layout("Vannmengde Q [l/s]", "Total løftehøyde [m]", view_xmax, view_y[1])
    shapes.append({"type": "line", "xref": "paper", "x0": 0, "x1": 1,
                   "y0": parametere.maks_totalt_tap_m, "y1": parametere.maks_totalt_tap_m,
                   "line": {"color": "#7d8794", "dash": "dash", "width": 1}})
    thresholds = [_threshold_label(f"H max = {parametere.maks_totalt_tap_m:g} m", x=1, xref="paper",
                                   y=parametere.maks_totalt_tap_m, yref="y", xanchor="right", yanchor="bottom")]
    if samlet or qt is None:
        thresholds.append(_threshold_label(f"τ min = {parametere.min_skjaerspenning_pa:g} Pa", x=0, y=1,
                                            xref="paper", yref="paper", xanchor="left", yanchor="top"))
    elif qt is not None:
        shapes.append({"type": "line", "x0": float(qt), "x1": float(qt), "y0": 0, "y1": 1,
                       "yref": "paper", "name": gruppe,
                       "line": {"color": farge, "dash": "dot", "width": 1}})
        thresholds.append(_threshold_label(f"τ min = {parametere.min_skjaerspenning_pa:g} Pa", x=float(qt),
                                            xref="x", y=0, yref="paper", xanchor="left", yanchor="bottom"))
    shapes.append({"type": "line", "x0": parametere.qdim_l_s, "x1": parametere.qdim_l_s,
                   "y0": 0, "y1": 1, "yref": "paper",
                   "line": {"color": "#b1b9c3", "dash": "dashdot", "width": 1}})
    thresholds.append(_threshold_label(f"Qdim = {parametere.qdim_l_s:g} l/s", x=parametere.qdim_l_s,
                                        xref="x", y=1, yref="paper", xanchor="right", yanchor="bottom"))
    layout.update(annotations=annotations, shapes=shapes)
    return {"id": "samlet" if samlet else f"ror-{ror[0].dn_od_mm:g}-{ror[0].sdr:g}",
            "tittel": "Samlet ledningskarakteristikk" if samlet else f"Ledningskarakteristikk {_navn(ror[0])}",
            "beskrivelse": (f"Tykk linje: τ ≥ {parametere.min_skjaerspenning_pa:g} Pa og totalt tap ≤ {parametere.maks_totalt_tap_m:g} m. "
                            "Sirkel: τ-grense · diamant: tapsgrense.") if samlet else "Referansepunkter ved 150 og 300 l/s.",
            "data": data, "layout": layout, "pipes": pipes,
            "thresholdAnnotations": thresholds,
            "fullRange": {"x": [0, max(xmax, view_xmax)], "y": [0, max(ymax * 1.08, view_y[1])]}}


def lag_referansepunkter_for_rapport(ror, parametere):
    """Alle opprinnelige grafmarkører, også når tekstbokser er skjult i UI-et."""
    rader = []
    for r in ror:
        gruppe = f"{r.dn_od_mm:g}-{r.sdr:g}"
        for samlet in (True, False):
            spec = _kurvegraf([r], parametere, samlet, {gruppe: FARGER[0]})
            for trace in spec["data"]:
                if trace["mode"] == "markers":
                    v, tau = trace["customdata"][0]
                    rader.append([_navn(r), trace["text"][0], trace["x"][0], trace["y"][0], v, tau])
    return rader


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
        traces, pipes = [], []
        for r in (resultat.godkjente or resultat.alle_resultater):
            gruppe = f"{r.dn_od_mm:g}-{r.sdr:g}"
            color = farger.get(gruppe, FARGER[len(pipes) % len(FARGER)])
            pipe = _pipe(r, resultat.input, color)
            pipe["points"].append({"label": "Dimensjonerende vannmengde", "q": resultat.input.qdim_l_s,
                                   "h": r.totalt_tap_m, "v": r.vannhastighet_m_s,
                                   "tau": r.skjaerspenning_pa, "traceIndex": len(traces), "annotationIndex": None})
            pipes.append(pipe)
            traces.append({"type": "scatter", "mode": "markers", "name": _navn(r),
                           "legendgroup": f"{r.dn_od_mm:g}-{r.sdr:g}",
                           "x": [r.pris_mnok], "y": [r.skjaerspenning_pa],
                           "marker": {"size": max(6, min(32, r.vannhastighet_m_s * 10)), "color": color},
                           "text": [_navn(r)],
                           "customdata": [[r.totalt_tap_m, r.vannhastighet_m_s]],
                           "hovertemplate": "%{text}<br>Pris = %{x:.2f} MNOK<br>τ = %{y:.3f} Pa<br>H = %{customdata[0]:.2f} m<br>v = %{customdata[1]:.3f} m/s<extra></extra>"})
        layout = _layout("Materialpris [MNOK]", "Skjærspenning τ [Pa]")
        layout["xaxis"]["range"] = _range([t["x"][0] for t in traces], zero=False, padding=0.12)
        layout["yaxis"]["range"] = _range([resultat.input.min_skjaerspenning_pa] + [t["y"][0] for t in traces])
        layout["shapes"].append({"type": "line", "xref": "paper", "x0": 0, "x1": 1,
                                  "y0": resultat.input.min_skjaerspenning_pa, "y1": resultat.input.min_skjaerspenning_pa,
                                  "line": {"color": "#616973", "dash": "dash", "width": 1}})
        grafer.append({"id": "pris", "tittel": "Pris mot skjærspenning",
                       "beskrivelse": ("Godkjente rør. " if resultat.godkjente else "Ingen godkjente rør; viser alle beregnede alternativer. ") + "Størrelse: hastighet · stiplet linje: min. skjærspenning.",
                       "data": traces, "layout": layout, "pipes": pipes,
                       "thresholdAnnotations": [_threshold_label(f"τ min = {resultat.input.min_skjaerspenning_pa:g} Pa",
                                                                  x=1, xref="paper", y=resultat.input.min_skjaerspenning_pa,
                                                                  yref="y", xanchor="right", yanchor="bottom")],
                       "fullRange": {"x": layout["xaxis"]["range"], "y": layout["yaxis"]["range"]}})
    if valgt:
        grafer.append(_kurvegraf(valgt, resultat.input, True, farger))
        grafer.extend(_kurvegraf([r], resultat.input, False, farger) for r in valgt)
    return grafer
