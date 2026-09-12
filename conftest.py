"""Hace importable el paquete `integracion` al ejecutar `pytest` desde la raíz."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
