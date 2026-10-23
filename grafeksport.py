"""Validerte, lokale PNG-øyeblikksbilder av brukerens interaktive grafer."""

import base64
import binascii
import struct
from io import BytesIO

from PIL import Image
from pydantic import BaseModel, Field, field_validator


class GrafEksport(BaseModel):
    id: str = Field(max_length=100)
    tittel: str = Field(min_length=1, max_length=200)
    bilde: str = Field(max_length=20_000_000)

    @field_validator("bilde")
    @classmethod
    def _png(cls, verdi):
        try:
            if not verdi.startswith("data:image/png;base64,"):
                raise ValueError("Grafen må være et PNG-bilde.")
            raw = base64.b64decode(verdi.split(",", 1)[1], validate=True)
            if raw[:8] != b"\x89PNG\r\n\x1a\n" or len(raw) < 24:
                raise ValueError("Ugyldig PNG-bilde.")
            w, h = struct.unpack(">II", raw[16:24])
            if not (0 < w <= 8000 and 0 < h <= 20000 and w * h <= 40_000_000):
                raise ValueError("Grafbildet er for stort.")
            with Image.open(BytesIO(raw)) as bilde:
                bilde.verify()
        except (binascii.Error, OSError, SyntaxError) as feil:
            raise ValueError("Ugyldig PNG-bilde.") from feil
        return verdi

    def png_bytes(self):
        return base64.b64decode(self.bilde.split(",", 1)[1])
