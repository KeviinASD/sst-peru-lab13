import streamlit as st
from supabase import create_client
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

def _get_supabase_credentials():
    """Obtiene las credenciales de Supabase desde variables de entorno o secrets"""
    # Intentar obtener desde variables de entorno primero
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    
    # Si no están en variables de entorno, intentar desde secrets
    if not url or not service_key:
        try:
            url = url or st.secrets.get("SUPABASE_URL")
            service_key = service_key or st.secrets.get("SUPABASE_SERVICE_KEY") or st.secrets.get("SUPABASE_KEY")
        except:
            pass
    
    if not url or not service_key:
        raise RuntimeError(
            "SUPABASE_URL y SUPABASE_SERVICE_KEY (o SUPABASE_KEY) deben estar configuradas. "
            "Colócalas en un archivo .env o en Streamlit secrets."
        )
    
    return url, service_key

def _verificar_o_crear_bucket(supabase, bucket_name, public=True):
    """
    Verifica si un bucket existe y lo crea si no existe.
    
    Args:
        supabase: Cliente de Supabase
        bucket_name: Nombre del bucket
        public: Si el bucket debe ser público (default: True)
    
    Returns:
        True si el bucket existe o fue creado, False si hay error
    """
    try:
        # Intentar listar buckets para verificar si existe
        buckets = supabase.storage.list_buckets()
        bucket_existe = any(b.name == bucket_name for b in buckets)
        
        if not bucket_existe:
            # Crear el bucket
            try:
                supabase.storage.create_bucket(
                    bucket_name,
                    options={"public": public}
                )
                return True
            except Exception as e:
                # Si falla, puede ser porque no tenemos permisos (necesitamos service role key)
                error_msg = str(e)
                if "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    st.warning(
                        f"⚠️ No se pudo crear el bucket '{bucket_name}' automáticamente. "
                        f"Necesitas crearlo manualmente en Supabase Dashboard o usar SUPABASE_SERVICE_KEY. "
                        f"Ve a Storage > Buckets y crea un bucket público llamado '{bucket_name}'"
                    )
                return False
        return True
    except Exception as e:
        # Si no podemos listar buckets, asumimos que no tenemos permisos suficientes
        return False

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
        url, service_key = _get_supabase_credentials()
        supabase = create_client(url, service_key)
        
        # Verificar si el bucket existe, intentar crearlo si no existe
        _verificar_o_crear_bucket(supabase, bucket)
        
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
        error_msg = str(e)
        # Mensajes de error más claros
        if "Bucket not found" in error_msg or "404" in error_msg:
            st.error(
                f"❌ El bucket '{bucket}' no existe en Supabase Storage. "
                f"Por favor, créalo manualmente en el Dashboard de Supabase:\n"
                f"1. Ve a tu proyecto en https://supabase.com\n"
                f"2. Navega a Storage > Buckets\n"
                f"3. Crea un nuevo bucket público llamado '{bucket}'\n"
                f"4. Asegúrate de que esté configurado como público"
            )
        elif "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
            st.error(
                f"❌ Error de permisos. Para subir archivos necesitas usar SUPABASE_SERVICE_KEY "
                f"(service role key) en lugar de SUPABASE_KEY (anon key). "
                f"La service role key tiene más permisos y es necesaria para operaciones de Storage."
            )
        else:
            st.error(f"❌ Error subiendo archivo: {error_msg}")
        return None

def eliminar_archivo_storage(url_publica, bucket):
    """Eliminar archivo por URL pública"""
    try:
        url, service_key = _get_supabase_credentials()
        supabase = create_client(url, service_key)
        
        # Extraer ruta del URL
        # URL: https://bucket.supabase.co/storage/v1/object/public/bucket/ruta/archivo.jpg
        ruta = url_publica.split(f"/{bucket}/")[-1]
        
        supabase.storage.from_(bucket).remove([ruta])
        return True
        
    except Exception as e:
        st.error(f"Error eliminando archivo: {e}")
        return False
