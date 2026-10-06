import math
import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def uid():
    return str(uuid4())


class Technical(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    properties: dict[str, str | float | bool] = Field(default_factory=dict)


class Pin(Technical):
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=40)
    function: str = ""
    contact_reference: str = ""
    comment: str = ""
    x: float | None = None
    y: float | None = None


class Connector(Technical):
    id: str = Field(default_factory=uid)
    reference: str = Field(min_length=1, max_length=40)
    definition_id: str | None = None
    designation: str = ""
    manufacturer: str = ""
    part_number: str = ""
    gender: str = ""
    view: Literal["solder", "mating"] = "solder"
    orientation: float = 0
    side: Literal["left", "right", "free"] = "left"
    x: float = Field(default=0, ge=-10000, le=10000)
    y: float = Field(default=0, ge=-10000, le=10000)
    pins: list[Pin] = Field(min_length=1, max_length=200)
    comment: str = ""


class Endpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connector_id: str
    pin_id: str | None = None  # None means housing


class Conductor(Technical):
    id: str = Field(default_factory=uid)
    color: str = "#e8e8e8"
    color_name: str = "Blanc"
    awg: int | None = Field(default=22, ge=0, le=40)
    section_mm2: float | None = Field(default=None, gt=0, le=1000)
    length: float = Field(default=350, ge=0, le=1000000)
    unit: Literal["mm", "cm", "m"] = "mm"
    material: str = "Cuivre"
    insulation: str = ""
    outer_diameter: float | None = Field(default=None, gt=0)
    manufacturer: str = ""
    part_number: str = ""
    reference: str = ""
    marker: str = ""
    comment: str = ""
    strip_start_mm: float = Field(default=0, ge=0)
    strip_end_mm: float = Field(default=0, ge=0)
    termination_start: str = ""
    termination_end: str = ""
    contact_start: str = ""
    contact_end: str = ""
    twisted: bool = False
    group: str = ""
    voltage: float | None = Field(default=None, ge=0)
    current: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def valid(self):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.color):
            raise ValueError("Couleur attendue : #RRGGBB")
        if self.awg is None and self.section_mm2 is None:
            raise ValueError("Renseignez AWG ou section mm²")
        if self.strip_start_mm + self.strip_end_mm > length_mm(self.length, self.unit):
            raise ValueError("Dénudage supérieur à la longueur du conducteur")
        return self


class Connection(Technical):
    id: str = Field(default_factory=uid)
    start: Endpoint
    end: Endpoint
    conductor: Conductor = Field(default_factory=Conductor)


class Shield(Technical):
    id: str = Field(default_factory=uid)
    designation: str = "Blindage"
    start: Endpoint | None = None
    end: Endpoint | None = None
    length_mm: float = Field(default=320, ge=0)
    material: str = "Cuivre étamé"
    kind: str = "Tresse"
    reference: str = ""
    manufacturer: str = ""
    diameter_mm: float | None = Field(default=None, gt=0)
    coverage: float | None = Field(default=None, ge=0, le=100)
    comment: str = ""


class Sheath(Technical):
    id: str = Field(default_factory=uid)
    designation: str = "Gaine"
    length_mm: float = Field(default=300, ge=0)
    start_mm: float = Field(default=25, ge=0)
    diameter_mm: float | None = Field(default=None, gt=0)
    color: str = "Noir"
    material: str = ""
    reference: str = ""
    manufacturer: str = ""
    comment: str = ""


class Accessory(Technical):
    id: str = Field(default_factory=uid)
    kind: str
    designation: str
    reference: str = ""
    quantity: int = Field(default=1, ge=1)
    comment: str = ""


class Drawing(Technical):
    designation: str = ""
    cable_reference: str = ""
    drawing_number: str = ""
    revision: str = "0"
    creator: str = ""
    validated_by: str = ""
    validation_date: str = ""
    length_mm: float = Field(default=350, ge=0)
    tolerance_plus_mm: float = Field(default=0, ge=0)
    tolerance_minus_mm: float = Field(default=0, ge=0)
    measurement: str = "Entre terminaisons"
    comment: str = ""


class Assembly(Technical):
    connectors: list[Connector] = Field(default_factory=list, max_length=100)
    connections: list[Connection] = Field(default_factory=list, max_length=500)
    shields: list[Shield] = Field(default_factory=list, max_length=100)
    sheaths: list[Sheath] = Field(default_factory=list, max_length=100)
    accessories: list[Accessory] = Field(default_factory=list, max_length=100)
    drawing: Drawing = Field(default_factory=Drawing)
    allow_shared_pins: bool = False

    @model_validator(mode="after")
    def graph_valid(self):
        ids = [c.id for c in self.connectors]
        refs = [c.reference for c in self.connectors]
        all_ids = ids + [p.id for c in self.connectors for p in c.pins]
        all_ids += [x.id for x in self.connections + self.shields + self.sheaths + self.accessories]
        all_ids += [x.conductor.id for x in self.connections]
        if len(all_ids) != len(set(all_ids)) or len(refs) != len(set(refs)):
            raise ValueError("Identifiants ou références dupliqués")
        pins = {c.id: {p.id for p in c.pins} for c in self.connectors}
        for c in self.connectors:
            if len({p.name for p in c.pins}) != len(c.pins):
                raise ValueError("Noms de pins dupliqués")
        used = set()
        edges = set()

        def check(ep, pin_required=False):
            if ep.connector_id not in pins:
                raise ValueError("Connecteur inexistant ou encore utilisé après suppression")
            if pin_required and ep.pin_id is None:
                raise ValueError("Connexion incomplète : pin requise")
            if ep.pin_id is not None and ep.pin_id not in pins[ep.connector_id]:
                raise ValueError("Pin inexistante")
            return (ep.connector_id, ep.pin_id)

        for edge in self.connections:
            a, b = check(edge.start, True), check(edge.end, True)
            if a == b:
                raise ValueError("Une pin ne peut pas être reliée à elle-même")
            pair = tuple(sorted((a, b)))
            if pair in edges:
                raise ValueError("Connexion déjà présente")
            edges.add(pair)
            for ep in (a, b):
                if ep in used and not self.allow_shared_pins:
                    raise ValueError("Pin déjà utilisée : autorisez explicitement les dérivations")
                used.add(ep)
        for shield in self.shields:
            for ep in (shield.start, shield.end):
                if ep:
                    check(ep)
        for sheath in self.sheaths:
            if sheath.start_mm + sheath.length_mm > self.drawing.length_mm:
                raise ValueError("La gaine dépasse la longueur du câble")
        return self


def length_mm(value, unit):
    return value * {"mm": 1, "cm": 10, "m": 1000}[unit]


def awg_mm2(awg):
    return math.pi / 4 * (0.127 * 92 ** ((36 - awg) / 39)) ** 2
