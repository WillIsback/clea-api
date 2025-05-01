# test/conftest.py
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]  # dossier racine du projet
sys.path.insert(0, str(ROOT))
