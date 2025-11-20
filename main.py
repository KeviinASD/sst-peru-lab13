#!/usr/bin/env python3
"""
Punto de entrada principal para la aplicación SST Perú
"""
import sys
import os

# Agregar el directorio raíz al path para que Python encuentre el módulo 'app'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar y ejecutar la aplicación principal
from app.main import main

if __name__ == "__main__":
    main()