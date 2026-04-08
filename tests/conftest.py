"""
Configurazione pytest: aggiunge il backend root al sys.path.
Permette di importare i moduli del progetto (utils, models, ecc.)
senza dover impostare PYTHONPATH manualmente.
"""

import sys
from pathlib import Path

# Aggiunge la directory backend/ al path
sys.path.insert(0, str(Path(__file__).parent.parent))
