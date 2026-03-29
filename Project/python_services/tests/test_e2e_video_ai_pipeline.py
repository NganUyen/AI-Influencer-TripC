from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from services.contracts import ApprovedProductionPackageContract


SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "e2e_video_ai_pipeline.py"
)


def _load_script_module():
    spec = spec_from_file_location("e2e_video_ai_pipeline", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_create_minimal_approved_package_matches_contract():
    module = _load_script_module()

    package = module.create_minimal_approved_package("persona-e2e")
    contract = ApprovedProductionPackageContract.model_validate(package)

    assert contract.concept_brief.persona_id == "persona-e2e"
    assert len(contract.beat_sheet.beats) == 5
    assert contract.beat_sheet.beats[0].purpose == "hook"
    assert contract.beat_sheet.beats[0].top_half_source_type == "ai_visual_fallback"


def test_extract_workflow_state_handles_nested_and_plain_status_payloads():
    module = _load_script_module()

    assert module._extract_workflow_state({"status": {"status": "generating_assets"}}) == "generating_assets"
    assert module._extract_workflow_state({"status": "COMPLETED"}) == "completed"
    assert module._extract_workflow_state({"status": None}) is None
