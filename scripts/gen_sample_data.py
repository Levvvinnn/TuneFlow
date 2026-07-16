#!/usr/bin/env python3
"""
Generate dashboard/src/sampleData.js from docs/sample_run_output/ JSON files.

Usage:
    python3 scripts/gen_sample_data.py

The output file is checked in — re-run whenever the sample JSON files change.
"""
import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent
SAMPLE_DIR = REPO_ROOT / "docs" / "sample_run_output"
OUT_FILE   = REPO_ROOT / "dashboard" / "src" / "sampleData.js"

MULTI_AGENT_FILE = SAMPLE_DIR / "multi_agent_run.json"
BASELINE_FILE    = SAMPLE_DIR / "baseline_run.json"


def load_json(path: pathlib.Path) -> dict:
    with open(path) as f:
        return json.load(f)


def js_literal(data: dict, indent: int = 0) -> str:
    """Serialize a dict to a JS object literal (JSON is valid JS)."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def main() -> None:
    multi = load_json(MULTI_AGENT_FILE)
    baseline = load_json(BASELINE_FILE)

    lines = [
        "// Auto-generated from docs/sample_run_output/ — do not edit by hand.",
        "// Re-run: python3 scripts/gen_sample_data.py",
        "// Used by the dashboard demo mode so you can explore without Docker.",
        "",
        f"export const DEMO_MULTI_AGENT = {js_literal(multi)};",
        "",
        f"export const DEMO_BASELINE = {js_literal(baseline)};",
        "",
        "export const DEMO_RUN_LIST = [",
        "  {",
        f'    run_id: "{multi["run_id"]}",',
        f'    mode: "{multi["mode"]}",',
        f'    status: "{multi["status"]}",',
        f'    termination_reason: "{multi.get("termination_reason", "")}",',
        '    created_at: "2026-07-16T14:00:00+00:00",',
        "    is_demo: true,",
        "  },",
        "  {",
        f'    run_id: "{baseline["run_id"]}",',
        f'    mode: "{baseline["mode"]}",',
        f'    status: "{baseline["status"]}",',
        f'    termination_reason: "{baseline.get("termination_reason", "")}",',
        '    created_at: "2026-07-16T15:00:00+00:00",',
        "    is_demo: true,",
        "  },",
        "];",
        "",
        "export const DEMO_RUN_MAP = {",
        f'  "{multi["run_id"]}": DEMO_MULTI_AGENT,',
        f'  "{baseline["run_id"]}": DEMO_BASELINE,',
        "};",
        "",
    ]

    OUT_FILE.write_text("\n".join(lines))
    print(f"Written {OUT_FILE.relative_to(REPO_ROOT)}")
    print(f"  Multi-agent run: {multi['run_id'][:8]}… ({len(multi.get('iterations', []))} iterations)")
    print(f"  Baseline run:    {baseline['run_id'][:8]}… ({len(baseline.get('iterations', []))} iterations)")


if __name__ == "__main__":
    main()
