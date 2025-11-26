"""
Script para crear los buckets necesarios en Supabase Storage.
Ejecuta este script una vez para inicializar los buckets requeridos.
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables de entorno
load_dotenv()

def crear_buckets():
    """Crea los buckets necesarios para la aplicación SST"""
    
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not url or not service_key:
        print("❌ Error: SUPABASE_URL y SUPABASE_SERVICE_KEY (o SUPABASE_KEY) deben estar en el archivo .env")
        sys.exit(1)
    
    supabase = create_client(url, service_key)
    
    # Buckets requeridos
    buckets = [
        {
            "name": "sst-evidencias",
            "public": True,
            "description": "Almacena fotos, videos y audios de incidentes e inspecciones"
        },
        {
            "name": "sst-documentos",
            "public": True,
            "description": "Almacena documentos, materiales de capacitación y archivos del repositorio"
        }
    ]
    
    print("🔧 Creando buckets en Supabase Storage...\n")
    
    for bucket_info in buckets:
        bucket_name = bucket_info["name"]
        is_public = bucket_info["public"]
        
        try:
            # Verificar si el bucket ya existe
            buckets_existentes = supabase.storage.list_buckets()
            bucket_existe = any(b.name == bucket_name for b in buckets_existentes)
            
            if bucket_existe:
                print(f"✅ El bucket '{bucket_name}' ya existe")
            else:
                # Crear el bucket
                supabase.storage.create_bucket(
                    bucket_name,
                    options={"public": is_public}
                )
                print(f"✅ Bucket '{bucket_name}' creado exitosamente (público: {is_public})")
                
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                print(f"✅ El bucket '{bucket_name}' ya existe")
            elif "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
                print(f"❌ Error de permisos al crear '{bucket_name}'. Necesitas usar SUPABASE_SERVICE_KEY (service role key)")
                print(f"   La anon key no tiene permisos para crear buckets.")
            else:
                print(f"❌ Error al crear '{bucket_name}': {error_msg}")
    
    print("\n✨ Proceso completado!")
    print("\n📝 Nota: Si algunos buckets no se crearon, créalos manualmente en:")
    print("   https://supabase.com/dashboard/project/[tu-proyecto]/storage/buckets")

if __name__ == "__main__":
    crear_buckets()


