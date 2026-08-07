"""
Datamodeller for pumpeledningsberegningen.

Feltene er delt i tre kategorier, jf. avklaring i prosjektdialogen:

  A. Obligatorisk prosjektinput - ingen standardverdi. Brukeren MÅ oppgi
     disse for hvert prosjekt (qdim, lengde, tillatte SDR-klasser).
  B. Faglige standardverdier - forhåndsutfylt med dagens verdier fra
     config.py, men skal kunne overstyres av brukeren.
  C. Systemverdier - avanserte fysiske konstanter, sjelden endret, men
     fortsatt eksplisitte felt (ikke skjulte konstanter).
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class BeregningsInput(BaseModel):
    # --- A: obligatorisk prosjektinput, ingen standardverdi ---

    qdim_l_s: float = Field(
        ...,
        gt=0,
        description="Dimensjonerende vannmengde [l/s]. Må oppgis av bruker.",
    )
    qdim_kilde: str = Field(
        default="manual",
        description=(
            "Kilde til Qdim. Kun 'manual' er støttet i denne fasen. "
            "Feltet finnes slik at senere kilder (municipal_excel, "
            "map_estimate, external_system) kan innføres uten å skrive om "
            "hydraulikkmotoren."
        ),
    )
    lengde_m: float = Field(
        ..., gt=0, description="Total ledningslengde [m]. Må oppgis av bruker."
    )
    tillatte_sdr: list[float] = Field(
        ...,
        min_length=1,
        description=(
            "SDR-klasser som er tillatt å vurdere for dette prosjektet. "
            "Har bevisst ingen standardverdi - hvilke SDR-/trykklasser som "
            "er egnet varierer fra prosjekt til prosjekt og må velges "
            "eksplisitt hver gang."
        ),
    )

    # --- B: faglige standardverdier, forhåndsutfylt men overstyrbare ---

    lengde_sjo_m: Optional[float] = Field(
        default=None,
        ge=0,
        description=(
            "Lengde lagt i sjø [m]. Standard: hele ledningslengden dersom "
            "ikke oppgitt (bruk hent_lengde_sjo_m())."
        ),
    )
    lengde_land_m: float = Field(default=0.0, ge=0, description="Lengde lagt på land [m]")

    ruhet_mm: float = Field(default=0.5, ge=0, description="Absolutt ruhet [mm]")
    kinematisk_viskositet_m2_s: float = Field(default=0.000001309, gt=0)
    sum_singulaertapskoeffisienter: float = Field(
        default=5.0, ge=0, description="Sum singulærtapskoeffisienter, Tk"
    )
    maks_totalt_tap_m: float = Field(default=70.0, gt=0)
    min_hastighet_m_s: float = Field(default=1.0, ge=0)
    min_skjaerspenning_pa: float = Field(default=2.0, ge=0)

    pris_ror_kr_per_kg: float = Field(default=60.0, ge=0)
    pris_lodd_kr_per_kg: float = Field(default=8.0, ge=0)
    pris_legging_sjo_kr_per_kg: float = Field(default=0.0, ge=0)

    dimensjonerende_ringspenning_mpa: float = Field(
        default=8.0,
        gt=0,
        description=(
            "Dimensjonerende ringspenning/materialspenning σ [MPa], brukt til "
            "å beregne tillatt innvendig trykk per SDR-klasse: p = 2σ/(SDR-1). "
            "Standard 8,0 MPa tilsvarer PE100 med sikkerhetsfaktor C=1,25 "
            "(EN 12201). Bør overstyres dersom prosjektet bruker et annet "
            "materiale eller en annen sikkerhetsfaktor."
        ),
    )

    # --- C: systemverdier, avanserte fysiske konstanter ---

    gravitasjon_m_s2: float = Field(default=9.81, gt=0)
    spesifikk_vekt_vann_n_m3: float = Field(default=9806.65, gt=0)
    rho_avlop_kg_m3: float = Field(default=1000.0, gt=0)
    rho_pe_kg_m3: float = Field(default=980.0, gt=0)
    rho_saltvann_kg_m3: float = Field(default=1030.0, gt=0)
    rho_lodd_kg_m3: float = Field(default=2360.0, gt=0)
    luftfylling_andel: float = Field(default=0.60, ge=0, le=1)

    @field_validator("tillatte_sdr")
    @classmethod
    def _sjekk_positive_sdr(cls, verdi):
        if any(sdr <= 0 for sdr in verdi):
            raise ValueError("Alle SDR-verdier i tillatte_sdr må være positive.")
        return verdi

    def hent_lengde_sjo_m(self) -> float:
        """Returnerer lengde_sjo_m, eller lengde_m dersom ikke eksplisitt satt."""
        return self.lengde_sjo_m if self.lengde_sjo_m is not None else self.lengde_m


class RorData(BaseModel):
    """Standardisert internt format for én rad i rørkatalogen."""

    dn_od_mm: float
    sdr: float
    veggtykkelse_mm: float
    kg_per_m: float
    kilde: str = "RORKATALOG"


class RorResultat(BaseModel):
    """Beregningsresultat for én DN/SDR-kombinasjon."""

    dn_od_mm: float
    sdr: float
    sdr_navn: str
    indre_diameter_mm: float

    vannhastighet_m_s: float
    reynolds: float
    friksjonsfaktor: float
    friksjonstap_m: float
    singulaertap_m: float
    totalt_tap_m: float
    skjaerspenning_pa: float

    trykk_fra_totalt_tap_bar: float
    tillatt_trykk_bar: float

    vekt_pe_teoretisk_kg_m: float
    vekt_avlop_kg_m: float
    oppdrift_kg_m: float
    netto_oppdrift_kg_m: float
    vekt_lodd_kg_m: float

    pris_kr: float
    pris_mnok: float

    godkjent: bool
    avviksarsaker: list[str] = Field(default_factory=list)


HydrauliskMargin = Literal["margin_totalt_tap", "margin_skjaerspenning", "margin_hastighet"]
VektNavn = Literal["pris", "hastighet", "skjaerspenning"]


class RangeringsValg(BaseModel):
    """
    Brukerens valg for hvordan anbefalt rør skal velges blant de GODKJENTE
    alternativene. Kravkontroll (godkjent/underkjent) er allerede gjort før
    rangering - se avklaring i prosjektdialogen 2026-08-06.

    Strategier:
      - billigste_godkjent: laveste pris blant godkjente rør.
      - best_hydraulisk: leksikografisk sortering på en brukervalgt,
        prioritert rekkefølge av hydrauliske marginer (hydraulisk_prioritet).
        Ingen fast definisjon av "best" - brukeren bestemmer selv hvilke mål
        som teller og i hvilken rekkefølge.
      - balansert: vektet score med fast forhåndsutfylt vekting
        (50% pris, 25% hastighet, 25% skjærspenning), jf. planens §8.3.
      - egendefinert_vekting: samme vektede scoremodell som balansert, men
        med brukervalgte vekter (vekter). Vilkårlige positive vekter
        normaliseres automatisk - de trenger ikke summere til 100%.

    Totalt tap inngår bevisst IKKE i noen av scoremodellene i denne fasen -
    det er fortsatt kun et absolutt krav (godkjent/underkjent), ikke et
    vektet mål. Dette kan revurderes senere dersom det er ønskelig.
    """

    strategi: Literal[
        "billigste_godkjent",
        "best_hydraulisk",
        "balansert",
        "egendefinert_vekting",
    ]

    hydraulisk_prioritet: Optional[list[HydrauliskMargin]] = Field(
        default=None,
        description=(
            "Prioritert rekkefølge av hydrauliske marginer, brukt kun når "
            "strategi='best_hydraulisk'. Første element avgjør rangeringen, "
            "uavgjort brytes av neste element osv."
        ),
    )

    vekter: Optional[dict[VektNavn, float]] = Field(
        default=None,
        description=(
            "Vekter for pris/hastighet/skjærspenning, brukt kun når "
            "strategi='egendefinert_vekting'. Trenger ikke summere til 1,0 "
            "eller 100% - normaliseres automatisk."
        ),
    )

    @model_validator(mode="after")
    def _sjekk_felt_for_strategi(self):
        if self.strategi == "best_hydraulisk":
            if not self.hydraulisk_prioritet:
                raise ValueError(
                    "hydraulisk_prioritet må oppgis (minst ett mål) når "
                    "strategi='best_hydraulisk'."
                )
            if len(set(self.hydraulisk_prioritet)) != len(self.hydraulisk_prioritet):
                raise ValueError("hydraulisk_prioritet kan ikke inneholde duplikater.")

        if self.strategi == "egendefinert_vekting":
            if not self.vekter:
                raise ValueError(
                    "vekter må oppgis når strategi='egendefinert_vekting'."
                )
            if any(v <= 0 for v in self.vekter.values()):
                raise ValueError("Alle vekter må være positive.")

        return self


class BeregningsResultat(BaseModel):
    """Samlet resultat av én pumpeledningsberegning."""

    input: BeregningsInput
    rangering: RangeringsValg
    alle_resultater: list[RorResultat]
    godkjente: list[RorResultat]
    underkjente: list[RorResultat]
    anbefalt: Optional[RorResultat] = None
    anbefalingsbegrunnelse: Optional[str] = None
