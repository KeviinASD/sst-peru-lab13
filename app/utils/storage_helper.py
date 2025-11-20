import streamlit as st
from supabase import create_client
import uuid
from datetime import datetime

def subir_archivo_storage(archivo, bucket, carpeta):
    """
    Función genérica para subir archivos a Supabase Storage
    
    Args:
        archivo: Archivo de Streamlit (st.file_uploader o st.camera_input)
        bucket: Nombre del bucket (ej: 'sst-evidencias')
        carpeta: Carpeta dentro del bucket (ej: 'inspecciones/123/')
    
    Returns:
        URL pública del archivo o None si error
    """
    if not archivo:
        return None
    
    try:
        supabase = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_SERVICE_KEY"]  # Usar service key para upload
        )
        
        # Generar nombre único
        extension = archivo.name.split('.')[-1] if hasattr(archivo, 'name') else 'jpg'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_archivo = f"{carpeta}{timestamp}_{uuid.uuid4()}.{extension}"
        
        # Subir archivo
        file_bytes = archivo.read() if hasattr(archivo, 'read') else archivo.getvalue()
        content_type = archivo.type if hasattr(archivo, 'type') else 'image/jpeg'
        
        supabase.storage.from_(bucket).upload(
            file=file_bytes,
            path=nombre_archivo,
            file_options={"content-type": content_type}
        )
        
        # Obtener URL pública
        url_publica = supabase.storage.from_(bucket).get_public_url(nombre_archivo)
        
        return url_publica
        
    except Exception as e:
        st.error(f"Error subiendo archivo: {e}")
        return None

def eliminar_archivo_storage(url_publica, bucket):
    """Eliminar archivo por URL pública"""
    try:
        supabase = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_SERVICE_KEY"]
        )
        
        # Extraer ruta del URL
        # URL: https://bucket.supabase.co/storage/v1/object/public/bucket/ruta/archivo.jpg
        ruta = url_publica.split(f"/{bucket}/")[-1]
        
        supabase.storage.from_(bucket).remove([ruta])
        return True
        
    except Exception as e:
        st.error(f"Error eliminando archivo: {e}")
        return False
