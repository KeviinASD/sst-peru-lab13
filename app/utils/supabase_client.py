from dotenv import load_dotenv
import os
from supabase import create_client

load_dotenv()

def get_supabase_client():
	"""Crea y devuelve un cliente de Supabase.

	Requiere las variables de entorno `SUPABASE_URL` y `SUPABASE_KEY`.
	"""
	url = os.getenv("SUPABASE_URL")
	key = os.getenv("SUPABASE_KEY")

	if not url or not key:
		raise RuntimeError(
			"SUPABASE_URL o SUPABASE_KEY no configuradas. Coloca estas variables en un archivo .env o en el entorno."
		)

	return create_client(url, key)

