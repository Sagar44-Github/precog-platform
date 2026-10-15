
"""Sample mode: fill the world state from the sample files in contracts/samples.

This lets the web app be built and tested before the real pipeline exists.
"""
import json
from pathlib import Path


def _read(samples_dir, name):
    return json.loads((Path(samples_dir) / (name + ".sample.json")).read_text(encoding="utf-8"))


def load_samples(world, contracts_dir):

    
    samples_dir = Path(contracts_dir) / "samples"
    
    world.load_full_state(_read(samples_dir, "world_state"))
    
    world.set_session(_read(samples_dir, "session_record"))
    
    world.set_detection_report(_read(samples_dir, "detection_report"))
