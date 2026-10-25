"""Convenient entry point to the repository's portable campaign operator."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parent / '.agents/skills/bindcraft-colab/scripts/campaign.py'), run_name='__main__')
