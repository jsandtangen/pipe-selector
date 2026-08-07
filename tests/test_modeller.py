import pytest
from pydantic import ValidationError

from modeller import BeregningsInput


def test_gyldig_input_bruker_standardverdier():
    p = BeregningsInput(qdim_l_s=300.0, lengde_m=10250.0, tillatte_sdr=[13.6, 17.0])
    assert p.ruhet_mm == 0.5
    assert p.maks_totalt_tap_m == 70.0
    assert p.qdim_kilde == "manual"
    assert p.dimensjonerende_ringspenning_mpa == 8.0


def test_dimensjonerende_ringspenning_kan_overstyres():
    p = BeregningsInput(
        qdim_l_s=300.0, lengde_m=10250.0, tillatte_sdr=[17.0],
        dimensjonerende_ringspenning_mpa=6.3,  # f.eks. PE80
    )
    assert p.dimensjonerende_ringspenning_mpa == 6.3


def test_dimensjonerende_ringspenning_ma_vaere_positiv():
    with pytest.raises(ValidationError):
        BeregningsInput(
            qdim_l_s=300.0, lengde_m=10250.0, tillatte_sdr=[17.0],
            dimensjonerende_ringspenning_mpa=0.0,
        )


def test_qdim_ma_vaere_positiv():
    with pytest.raises(ValidationError):
        BeregningsInput(qdim_l_s=0.0, lengde_m=1000.0, tillatte_sdr=[17.0])

    with pytest.raises(ValidationError):
        BeregningsInput(qdim_l_s=-10.0, lengde_m=1000.0, tillatte_sdr=[17.0])


def test_lengde_ma_vaere_positiv():
    with pytest.raises(ValidationError):
        BeregningsInput(qdim_l_s=300.0, lengde_m=0.0, tillatte_sdr=[17.0])


def test_tillatte_sdr_er_obligatorisk_uten_standardverdi():
    with pytest.raises(ValidationError):
        BeregningsInput(qdim_l_s=300.0, lengde_m=1000.0)


def test_tillatte_sdr_kan_ikke_vaere_tom_liste():
    with pytest.raises(ValidationError):
        BeregningsInput(qdim_l_s=300.0, lengde_m=1000.0, tillatte_sdr=[])


def test_tillatte_sdr_ma_vaere_positive():
    with pytest.raises(ValidationError):
        BeregningsInput(qdim_l_s=300.0, lengde_m=1000.0, tillatte_sdr=[-17.0])
