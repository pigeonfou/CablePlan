import copy
from xml.etree import ElementTree
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.drawing import csv_export, pdf, svg
from app.models import Assembly, Conductor, awg_mm2, length_mm
from conftest import reference_model


def test_units():
    assert awg_mm2(22) == pytest.approx(0.326, abs=0.001)
    assert length_mm(0.35, "m") == 350 and length_mm(35, "cm") == 350


@pytest.mark.parametrize(
    "field,value",
    [("length", -1), ("awg", 41), ("section_mm2", -1), ("color", "red<script>"), ("length", float("nan"))],
)
def test_conductor_validation(field, value):
    with pytest.raises(ValidationError):
        Conductor(**{field: value})


def test_graph_integrity():
    data = reference_model().model_dump(mode="json")
    wrong = copy.deepcopy(data)
    wrong["connectors"].pop()
    with pytest.raises(ValidationError, match="Connecteur inexistant"):
        Assembly.model_validate(wrong)
    wrong = copy.deepcopy(data)
    wrong["connections"][0]["end"]["pin_id"] = "unknown"
    with pytest.raises(ValidationError, match="Pin inexistante"):
        Assembly.model_validate(wrong)
    wrong = copy.deepcopy(data)
    wrong["connections"][0]["end"] = wrong["connections"][0]["start"]
    with pytest.raises(ValidationError, match="elle-même"):
        Assembly.model_validate(wrong)
    branch = copy.deepcopy(data["connections"][0])
    branch["id"] = "branch"
    branch["conductor"]["id"] = "branch-wire"
    branch["end"]["pin_id"] = data["connectors"][1]["pins"][4]["id"]
    data["connections"].append(branch)
    with pytest.raises(ValidationError, match="Pin déjà utilisée"):
        Assembly.model_validate(data)
    data["allow_shared_pins"] = True
    assert len(Assembly.model_validate(data).connections) == 5


def test_vector_exports_escape_and_determinism():
    model = reference_model()
    model.drawing.comment = "<script>alert(1)</script>"
    project = {"name": "Test & cable", "client": "Atelier"}
    first = svg(model, project)
    assert first == svg(model, project)
    ElementTree.fromstring(first)
    assert "<script>" not in first and "&lt;script&gt;" in first
    assert pdf(model, project).startswith(b"%PDF-")
    model.connections[0].conductor.reference = '=HYPERLINK("http://evil")'
    assert "'=HYPERLINK" in csv_export(model)


def test_proxy_configuration_overwrites_incoming_header():
    conf = (Path(__file__).parents[1] / "packaging/nginx/cableplan.conf").read_text()
    assert "proxy_set_header X-CablePlan-Access-Channel lan;" in conf
    assert "proxy_set_header X-CablePlan-Access-Channel tunnel;" in conf
    assert "listen 127.0.0.1:8081;" in conf
    assert "http://unix:/run/cableplan/app.sock" in conf
