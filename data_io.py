import re

import pandas as pd

DN_OD_KOLONNE = "DN/OD"

_SDR_VEGGTYKKELSE_MONSTER = re.compile(
    r"^SDR\s*([\d,]+)\s*Veggtykkelse\b", re.IGNORECASE
)


def les_ror_csv(csv_fil):
    """Leser norsk CSV-format og normaliserer DN/OD-kolonnen uten enhetssuffiks."""
    df = pd.read_csv(
        csv_fil,
        sep=";",
        decimal=","
    )

    df = df.dropna(axis=1, how="all")
    df.columns = [kol.strip() for kol in df.columns]

    dn_od_kandidater = [
        kol for kol in df.columns
        if kol == DN_OD_KOLONNE or kol.startswith(DN_OD_KOLONNE + " ")
    ]

    if dn_od_kandidater:
        df = df.rename(columns={dn_od_kandidater[0]: DN_OD_KOLONNE})

    for kolonne in df.columns:
        df[kolonne] = pd.to_numeric(df[kolonne], errors="coerce")

    return df


def finn_sdr_liste_fra_katalog(df):
    """
    Finner SDR-klasser fra katalogens kolonnepar, sortert stigende.

    Forventer kolonnepar av typen:
        "SDR <verdi> Veggtykkelse ..."
        "SDR <verdi> Vekt ..." eller "SDR <verdi> kg/m"

    Returnerer:
        {"SDR": float, "SDR-navn": str, "veggtykkelse_kolonne": str, "kg_per_m_kolonne": str}
    """
    sdr_liste = []

    for kolonne in df.columns:
        treff = _SDR_VEGGTYKKELSE_MONSTER.match(kolonne)

        if not treff:
            continue

        sdr_tekst = treff.group(1)
        sdr_verdi = float(sdr_tekst.replace(",", "."))

        vekt_kolonne = None

        for kandidat in df.columns:
            if kandidat.startswith(f"SDR {sdr_tekst} Vekt") or kandidat == f"SDR {sdr_tekst} kg/m":
                vekt_kolonne = kandidat
                break

        if vekt_kolonne is None:
            raise ValueError(
                f"Fant veggtykkelse-kolonne '{kolonne}' i rørkatalogen, "
                f"men ingen tilhørende vekt-kolonne for SDR {sdr_tekst}."
            )

        sdr_liste.append({
            "SDR": sdr_verdi,
            "SDR-navn": f"SDR {sdr_tekst}",
            "veggtykkelse_kolonne": kolonne,
            "kg_per_m_kolonne": vekt_kolonne,
        })

    if not sdr_liste:
        raise ValueError(
            "Fant ingen SDR-klasser i rørkatalogen. Forventet kolonner av "
            "typen 'SDR <verdi> Veggtykkelse ...' og 'SDR <verdi> Vekt ...'."
        )

    sdr_liste.sort(key=lambda info: info["SDR"])

    return sdr_liste


def filtrer_sdr_liste(sdr_liste_full, tillatte_sdr):
    """Filtrerer til prosjektets SDR-valg; tomme eller ukjente valg gir ValueError."""
    if not tillatte_sdr:
        raise ValueError(
            "Ingen SDR-klasser er valgt. Brukeren må oppgi minst én "
            "tillatt SDR-klasse for denne beregningen."
        )

    tilgjengelige = {info["SDR"]: info for info in sdr_liste_full}

    ukjente = [
        sdr for sdr in tillatte_sdr
        if sdr not in tilgjengelige
    ]

    if ukjente:
        raise ValueError(
            "Følgende valgte SDR-klasser finnes ikke i rørkatalogen: "
            + ", ".join(str(sdr) for sdr in ukjente)
            + "\n\nTilgjengelige SDR-klasser i katalogen er: "
            + ", ".join(info["SDR-navn"] for info in sdr_liste_full)
        )

    return [tilgjengelige[sdr] for sdr in tillatte_sdr]


def sjekk_nodvendige_kolonner(df, sdr_liste):
    """Sjekker at CSV-filen inneholder alle kolonnene som kreves."""
    nodvendige_kolonner = [DN_OD_KOLONNE]

    for sdr_info in sdr_liste:
        nodvendige_kolonner.append(sdr_info["veggtykkelse_kolonne"])
        nodvendige_kolonner.append(sdr_info["kg_per_m_kolonne"])

    manglende = [
        kol for kol in nodvendige_kolonner
        if kol not in df.columns
    ]

    if manglende:
        raise ValueError(
            "CSV-filen mangler følgende kolonner:\n"
            + "\n".join(manglende)
            + "\n\nKolonnene i CSV-filen er:\n"
            + "\n".join(df.columns)
        )


def er_veggtykkelse_rimelig(DN, SDR, veggtykkelse):
    """
    Filtrerer bort åpenbart feil CSV-rader.
    For PE-rør er cirka veggtykkelse = DN / SDR.
    """
    forventet = DN / SDR

    nedre_grense = 0.5 * forventet
    ovre_grense = 1.5 * forventet

    return nedre_grense <= veggtykkelse <= ovre_grense


def finn_duplikate_dn(df):
    """
    Finner DN/OD-verdier som forekommer mer enn én gang i katalogen.
    Returnerer en sortert liste med duplikate DN-verdier (tom liste hvis ingen).
    """
    dn_serie = df[DN_OD_KOLONNE].dropna()
    dn_serie = dn_serie[dn_serie > 0]

    telling = dn_serie.value_counts()
    duplikater = telling[telling > 1].index.tolist()

    return sorted(duplikater)


def sjekk_ingen_duplikate_dn(df):
    """Avviser duplikate DN/OD-verdier fordi de gjør katalogen tvetydig."""
    duplikater = finn_duplikate_dn(df)

    if duplikater:
        raise ValueError(
            "Rørkatalogen har duplikate DN/OD-verdier, dette er tvetydig og "
            "må rettes i katalogen før beregning: "
            + ", ".join(str(dn) for dn in duplikater)
        )


def valider_rorkatalog(df, sdr_liste):
    """
    Går gjennom hver DN/SDR-kombinasjon i katalogen og rapporterer rader med
    mistenkt feil: urimelig veggtykkelse, negative/null-verdier, eller at kun
    én av veggtykkelse/vekt er oppgitt.

    Manglende verdier for en DN/SDR-kombinasjon som rett og slett ikke finnes
    i katalogen (f.eks. SDR 41 tilbys ikke for store DN) regnes IKKE som en
    feil - katalogen kan være glissen i utgangspunktet.

    Returnerer en liste med avvik:
        [{"DN": float, "SDR-navn": str, "problem": str}, ...]
    Tom liste betyr at ingen avvik ble funnet.
    """
    avvik = []

    for _, rad in df.iterrows():
        DN = rad[DN_OD_KOLONNE]

        if pd.isna(DN) or DN <= 0:
            continue

        for sdr_info in sdr_liste:
            veggtykkelse = rad[sdr_info["veggtykkelse_kolonne"]]
            kg_per_m = rad[sdr_info["kg_per_m_kolonne"]]

            veggtykkelse_mangler = pd.isna(veggtykkelse)
            kg_per_m_mangler = pd.isna(kg_per_m)

            if veggtykkelse_mangler and kg_per_m_mangler:
                continue  # kombinasjonen finnes ikke i katalogen - ikke en feil

            if veggtykkelse_mangler or kg_per_m_mangler:
                avvik.append({
                    "DN": DN,
                    "SDR-navn": sdr_info["SDR-navn"],
                    "problem": "Kun én av veggtykkelse og vekt er oppgitt, ikke begge.",
                })
                continue

            if veggtykkelse <= 0 or kg_per_m <= 0:
                avvik.append({
                    "DN": DN,
                    "SDR-navn": sdr_info["SDR-navn"],
                    "problem": f"Veggtykkelse={veggtykkelse} mm, vekt={kg_per_m} kg/m - må begge være positive.",
                })
                continue

            if not er_veggtykkelse_rimelig(DN, sdr_info["SDR"], veggtykkelse):
                forventet = DN / sdr_info["SDR"]
                avvik.append({
                    "DN": DN,
                    "SDR-navn": sdr_info["SDR-navn"],
                    "problem": (
                        f"Veggtykkelse {veggtykkelse} mm er urimelig for DN{DN:.0f} "
                        f"{sdr_info['SDR-navn']} (forventet ca. {forventet:.1f} mm)."
                    ),
                })

    return avvik
