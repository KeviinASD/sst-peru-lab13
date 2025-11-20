import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app.utils.supabase_client import get_supabase_client
from app.utils.storage_helper import subir_archivo_storage
from app.auth import requerir_rol
import json
import requests

def mostrar(usuario):
    """Módulo de Capacitaciones y Concientización (Ley 29783 Art. 31)"""
    requerir_rol(['admin', 'sst', 'supervisor', 'gerente'])
    
    st.title("🎓 Gestión de Capacitaciones SST")
    
    # Tabs principales
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Programar Capacitación",
        "👥 Gestionar Asistentes",
        "📤 Material de Capacitación",
        "📋 Encuestas Post-Capacitación",
        "📊 Reporte de Efectividad"
    ])
    
    with tab1:
        programar_capacitacion(usuario)
    
    with tab2:
        gestionar_asistentes(usuario)
    
    with tab3:
        gestionar_material(usuario)
    
    with tab4:
        encuestas_post_capacitacion(usuario)
    
    with tab5:
        reporte_efectividad(usuario)

def programar_capacitacion(usuario):
    """Programar nueva capacitación con recordatorios automáticos"""
    
    st.subheader("📅 Programar Nueva Capacitación")
    
    with st.form("form_capacitacion", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            codigo = st.text_input(
                "Código de Capacitación",
                value=f"CAP-{datetime.now().strftime('%Y%m%d')}-",
                help="Formato: CAP-YYYYMMdd-###"
            )
            
            tema = st.text_input(
                "Tema de Capacitación",
                help="Ej: Uso Correcto de EPP, Manejo de Extintores"
            )
            
            area_destino = st.multiselect(
                "Área(s) Destino",
                ["Producción", "Almacén", "Oficinas", "Mantenimiento", "Seguridad"],
                help="Selecciona todos los públicos objetivo"
            )
        
        with col2:
            fecha_programada = st.date_input(
                "Fecha de Capacitación",
                min_value=datetime.now().date()
            )
            
            hora = st.time_input(
                "Hora de Inicio",
                value=datetime.strptime("09:00", "%H:%M").time()
            )
            
            duracion_horas = st.number_input(
                "Duración (horas)",
                min_value=0.5,
                max_value=8.0,
                value=2.0,
                step=0.5
            )
        
        # Datos del instructor
        st.markdown("### 👨🏫 Información del Instructor")
        col3, col4 = st.columns(2)
        
        with col3:
            instructor = st.text_input(
                "Nombre del Instructor",
                value=usuario['nombre_completo']
            )
            
            credenciales = st.text_area(
                "Credenciales/Certificaciones del Instructor",
                help="Ej: Certificado Instructor SST, Curso de primeros auxilios"
            )
        
        with col4:
            metodo = st.selectbox(
                "Método de Capacitación",
                ["Presencial", "Virtual", "Híbrido", "E-learning"]
            )
            
            ubicacion = st.text_input(
                "Ubicación/Link",
                help="Salón de capacitación o URL de videoconferencia"
            )
        
        # Configuración de recordatorios
        st.markdown("### 🔔 Configuración de Recordatorios")
        st.info("Los recordatorios se enviarán automáticamente vía n8n")
        
        recordatorio_24h = st.checkbox("Recordatorio 24 horas antes", value=True)
        recordatorio_1h = st.checkbox("Recordatorio 1 hora antes", value=True)
        
        # Material preliminar
        material_opcional = st.file_uploader(
            "Material Preliminar (opcional)",
            type=['pdf', 'pptx', 'docx'],
            help="Agenda, temario o material de pre lectura"
        )
        
        submitted = st.form_submit_button("📅 Programar Capacitación", type="primary")
        
        if submitted:
            if not tema or not codigo:
                st.error("❌ Tema y código son obligatorios")
                return
            
            # Combinar fecha y hora
            fecha_hora = datetime.combine(fecha_programada, hora)
            
            capacitacion_data = {
                'codigo': codigo,
                'tema': tema,
                'area_destino': json.dumps(area_destino),
                'fecha_programada': fecha_hora.isoformat(),
                'duracion_horas': duracion_horas,
                'instructor': instructor,
                'credenciales': credenciales,
                'metodo': metodo,
                'ubicacion': ubicacion,
                'estado': 'programada',
                'recordatorio_24h': recordatorio_24h,
                'recordatorio_1h': recordatorio_1h
            }
            
            # Subir material si existe
            if material_opcional:
                url_material = subir_archivo_storage(
                    material_opcional,
                    bucket='sst-documentos',
                    carpeta=f'capacitaciones/{codigo}/material/'
                )
                capacitacion_data['material_preliminar_url'] = url_material
            
            # Guardar en BD
            result = guardar_capacitacion(capacitacion_data)
            
            if result:
                st.success(f"✅ Capacitación programada: {codigo}")
                
                # Disparar webhook de n8n para recordatorios
                try:
                    requests.post(
                        st.secrets["N8N_WEBHOOK_URL"] + "/capacitacion-programada",
                        json={
                            "capacitacion_id": result['id'],
                            "codigo": codigo,
                            "tema": tema,
                            "fecha": fecha_hora.isoformat(),
                            "recordatorios": {
                                "24h": recordatorio_24h,
                                "1h": recordatorio_1h
                            }
                        }
                    )
                except:
                    st.warning("⚠️ No se pudo conectar con n8n para recordatorios")

def guardar_capacitacion(data):
    """Guardar capacitación en Supabase"""
    supabase = get_supabase_client()
    
    try:
        response = supabase.table('capacitaciones').insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"Error guardando capacitación: {e}")
        return None

def gestionar_asistentes(usuario):
    """Gestionar lista de asistentes y registro de asistencia"""
    
    st.subheader("👥 Gestionar Asistentes a Capacitaciones")
    
    supabase = get_supabase_client()
    
    # Cargar capacitaciones programadas
    capacitaciones = supabase.table('capacitaciones').select(
        '*, asistentes_capacitacion(*, usuarios(*))'
    ).eq('estado', 'programada').execute().data
    
    if not capacitaciones:
        st.info("ℹ️ No hay capacitaciones programadas")
        return
    
    # Seleccionar capacitación
    cap_seleccionada = st.selectbox(
        "Seleccionar Capacitación",
        options=capacitaciones,
        format_func=lambda x: f"{x['codigo']} - {x['tema'][:50]}... ({x['fecha_programada']})"
    )
    
    if not cap_seleccionada:
        return
    
    # Mostrar detalles
    with st.expander("📋 Detalles de la Capacitación", expanded=True):
        st.json({
            "Código": cap_seleccionada['codigo'],
            "Tema": cap_seleccionada['tema'],
            "Fecha": cap_seleccionada['fecha_programada'],
            "Instructor": cap_seleccionada['instructor'],
            "Método": cap_seleccionada['metodo']
        })
    
    # Cargar trabajadores disponibles
    trabajadores = supabase.table('usuarios').select(
        'id', 'nombre_completo', 'area', 'rol'
    ).eq('activo', True).neq('rol', 'admin').execute().data
    
    if not trabajadores:
        st.warning("⚠️ No hay trabajadores activos")
        return
    
    df_trabajadores = pd.DataFrame(trabajadores)
    
    # Tabla de asistentes actuales
    st.markdown("### 📋 Asistentes Asignados")
    
    asistentes_actuales = cap_seleccionada.get('asistentes_capacitacion', [])
    
    if asistentes_actuales:
        df_asistentes = pd.DataFrame([
            {
                'ID': a['trabajador_id'],
                'Nombre': a['usuarios']['nombre_completo'],
                'Asistió': a['asistio'],
                'Calificación': a.get('calificacion', 'N/A')
            } for a in asistentes_actuales
        ])
        
        st.dataframe(df_asistentes, use_container_width=True)
        
        # Botón para descargar lista
        if st.button("📥 Descargar Lista de Asistentes"):
            excel_data = df_asistentes.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Descargar CSV",
                excel_data,
                f"asistentes_{cap_seleccionada['codigo']}.csv",
                "text/csv"
            )
    else:
        st.info("ℹ️ No hay asistentes asignados aún")
    
    # Agregar nuevos asistentes
    st.markdown("### ➕ Agregar Asistentes")
    
    # Filtrar trabajadores por área si aplica
    area_capacitacion = json.loads(cap_seleccionada['area_destino'])
    trabajadores_filtrados = df_trabajadores[
        df_trabajadores['area'].isin(area_capacitacion)
    ] if area_capacitacion else df_trabajadores
    
    # Multiselect para agregar
    nuevos_asistentes = st.multiselect(
        "Seleccionar Trabajadores",
        options=trabajadores_filtrados['id'].tolist(),
        format_func=lambda x: f"{df_trabajadores[df_trabajadores['id'] == x]['nombre_completo'].iloc[0]} ({df_trabajadores[df_trabajadores['id'] == x]['area'].iloc[0]})"
    )
    
    if nuevos_asistentes:
        if st.button("📅 Agregar Asistentes Seleccionados", type="primary"):
            agregar_asistentes(cap_seleccionada['id'], nuevos_asistentes)
            st.success(f"✅ {len(nuevos_asistentes)} asistentes agregados")
            st.rerun()
    
    # Registrar asistencia el día de la capacitación
    st.markdown("### ✅ Registrar Asistencia")
    
    if datetime.now().date() == pd.to_datetime(cap_seleccionada['fecha_programada']).date():
        st.success("🎯 Hoy es el día de la capacitación. Puedes registrar asistencia.")
        
        for asistente in asistentes_actuales:
            with st.expander(f"📝 {asistente['usuarios']['nombre_completo']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    asistio = st.checkbox(
                        "Asistió",
                        value=asistente['asistio'],
                        key=f"asist_{asistente['id']}"
                    )
                
                with col2:
                    calificacion = st.number_input(
                        "Calificación (1-5)",
                        min_value=1,
                        max_value=5,
                        value=asistente.get('calificacion', 3),
                        key=f"calif_{asistente['id']}"
                    )
                
                feedback = st.text_area(
                    "Feedback del Asistente",
                    value=asistente.get('feedback', ''),
                    key=f"feed_{asistente['id']}",
                    help="Comentarios sobre la capacitación"
                )
                
                if st.button("💾 Guardar Asistencia", key=f"save_{asistente['id']}"):
                    actualizar_asistencia(
                        asistente['id'],
                        asistio,
                        calificacion,
                        feedback
                    )
                    st.success("✅ Asistencia registrada")
    else:
        st.info(f"ℹ️ La capacitación es el {cap_seleccionada['fecha_programada']}. No puedes registrar asistencia aún.")

def agregar_asistentes(capacitacion_id, trabajador_ids):
    """Agregar múltiples asistentes a capacitación"""
    supabase = get_supabase_client()
    
    try:
        for trabajador_id in trabajador_ids:
            supabase.table('asistentes_capacitacion').insert({
                'capacitacion_id': capacitacion_id,
                'trabajador_id': trabajador_id,
                'asistio': False
            }).execute()
    except Exception as e:
        st.error(f"Error agregando asistentes: {e}")

def actualizar_asistencia(asistente_id, asistio, calificacion, feedback):
    """Actualizar registro de asistencia y calificación"""
    supabase = get_supabase_client()
    
    try:
        supabase.table('asistentes_capacitacion').update({
            'asistio': asistio,
            'calificacion': calificacion,
            'feedback': feedback,
            'fecha_asistencia': datetime.now().isoformat() if asistio else None
        }).eq('id', asistente_id).execute()
        
        # Disparar webhook para encuesta post-capacitación
        if asistio:
            try:
                requests.post(
                    st.secrets["N8N_WEBHOOK_URL"] + "/asistencia-registrada",
                    json={"asistente_id": asistente_id}
                )
            except:
                pass
    except Exception as e:
        st.error(f"Error actualizando asistencia: {e}")

def gestionar_material(usuario):
    """Subir y gestionar material de capacitación"""
    
    st.subheader("📤 Material de Capacitación")
    
    supabase = get_supabase_client()
    
    # Cargar capacitaciones
    capacitaciones = supabase.table('capacitaciones').select('id', 'codigo', 'tema').execute().data
    
    if not capacitaciones:
        st.warning("⚠️ No hay capacitaciones para gestionar material")
        return
    
    # Seleccionar capacitación
    cap_seleccionada = st.selectbox(
        "Seleccionar Capacitación",
        options=capacitaciones,
        format_func=lambda x: f"{x['codigo']} - {x['tema']}"
    )
    
    if not cap_seleccionada:
        return
    
    # Tabs para diferentes tipos de material
    subtab1, subtab2, subtab3 = st.tabs([
        "📄 Subir Material",
        "📽️ Videos",
        "🔗 Recursos Externos"
    ])
    
    with subtab1:
        st.markdown("### 📄 Subir Documentos")
        
        archivo = st.file_uploader(
            "Seleccionar archivo",
            type=['pdf', 'pptx', 'docx', 'xlsx'],
            help="Máximo 50MB por archivo"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            tipo_material = st.selectbox(
                "Tipo de Material",
                ["Presentación", "Guía Práctica", "Evaluación", "Certificado", "Temario"]
            )
        
        with col2:
            descripcion = st.text_input(
                "Descripción",
                help="Breve descripción del contenido"
            )
        
        if st.button("📤 Subir Material", type="primary"):
            if archivo:
                url_material = subir_archivo_storage(
                    archivo,
                    bucket='sst-documentos',
                    carpeta=f"capacitaciones/{cap_seleccionada['codigo']}/material/"
                )
                
                if url_material:
                    # Guardar en tabla material_capacitacion
                    try:
                        supabase.table('material_capacitacion').insert({
                            'capacitacion_id': cap_seleccionada['id'],
                            'tipo': tipo_material,
                            'descripcion': descripcion,
                            'archivo_url': url_material,
                            'subido_por': usuario['id']
                        }).execute()
                        
                        st.success("✅ Material subido exitosamente")
                    except Exception as e:
                        st.error(f"Error registrando material: {e}")
            else:
                st.warning("⚠️ Selecciona un archivo primero")
    
    with subtab2:
        st.markdown("### 📽️ Videos de Capacitación")
        
        video_url = st.text_input(
            "YouTube/Vimeo URL",
            help="Enlace al video de capacitación"
        )
        
        if video_url and st.button("🔗 Agregar Video"):
            try:
                supabase.table('material_capacitacion').insert({
                    'capacitacion_id': cap_seleccionada['id'],
                    'tipo': 'Video',
                    'descripcion': 'Video de capacitación',
                    'archivo_url': video_url,
                    'subido_por': usuario['id']
                }).execute()
                st.success("✅ Video agregado")
            except Exception as e:
                st.error(f"Error agregando video: {e}")
    
    # Ver material existente
    st.markdown("### 📚 Material Actual")
    
    material_existente = supabase.table('material_capacitacion').select(
        '*'
    ).eq('capacitacion_id', cap_seleccionada['id']).execute().data
    
    if material_existente:
        df_material = pd.DataFrame(material_existente)
        
        for _, item in df_material.iterrows():
            with st.expander(f"📄 {item['tipo']} - {item['descripcion']}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"📅 Subido: {pd.to_datetime(item['created_at']).strftime('%d/%m/%Y')}")
                    st.link_button("📥 Ver Material", item['archivo_url'])
                
                with col2:
                    if st.button("🗑️ Eliminar", key=f"del_mat_{item['id']}"):
                        # Eliminar de Storage y BD
                        eliminar_material(item['id'], item['archivo_url'])
                        st.rerun()
    else:
        st.info("ℹ️ No hay material asociado aún")

def eliminar_material(material_id, archivo_url):
    """Eliminar material de capacitación"""
    supabase = get_supabase_client()
    
    try:
        # Eliminar de Supabase Storage
        from app.utils.storage_helper import eliminar_archivo_storage
        eliminar_archivo_storage(archivo_url, 'sst-documentos')
        
        # Eliminar registro
        supabase.table('material_capacitacion').delete().eq('id', material_id).execute()
        
        st.success("✅ Material eliminado")
    except Exception as e:
        st.error(f"Error eliminando material: {e}")

def encuestas_post_capacitacion(usuario):
    """Sistema de encuestas para evaluar efectividad"""
    
    st.subheader("📋 Encuestas Post-Capacitación")
    
    supabase = get_supabase_client()
    
    # Cargar capacitaciones realizadas
    capacitaciones = supabase.table('capacitaciones').select(
        '*, asistentes_capacitacion(*, usuarios(*))'
    ).eq('estado', 'realizada').execute().data
    
    if not capacitaciones:
        st.info("ℹ️ No hay capacitaciones realizadas para evaluar")
        return
    
    # Seleccionar capacitación
    cap_seleccionada = st.selectbox(
        "Seleccionar Capacitación para Ver Encuestas",
        options=capacitaciones,
        format_func=lambda x: f"{x['codigo']} - {x['tema']}"
    )
    
    if not cap_seleccionada:
        return
    
    # Ver resultados de encuestas
    st.markdown("### 📊 Resultados de Encuestas")
    
    encuestas = supabase.table('encuestas_capacitacion').select(
        '*'
    ).eq('capacitacion_id', cap_seleccionada['id']).execute().data
    
    if encuestas:
        df_encuestas = pd.DataFrame(encuestas)
        
        # Calcular estadísticas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_satisfaccion = df_encuestas['satisfaccion'].mean()
            st.metric("😊 Satisfacción Promedio", f"{avg_satisfaccion:.1f}/5")
        
        with col2:
            avg_utilidad = df_encuestas['utilidad'].mean()
            st.metric("🎯 Utilidad Promedio", f"{avg_utilidad:.1f}/5")
        
        with col3:
            tasa_respuesta = len(encuestas) / len(cap_seleccionada['asistentes_capacitacion']) * 100
            st.metric("📈 Tasa de Respuesta", f"{tasa_respuesta:.1f}%")
        
        # Comentarios destacados
        st.markdown("#### 💬 Comentarios Destacados")
        comentarios = df_encuestas[df_encuestas['comentarios'].notna()]['comentarios']
        for i, comentario in enumerate(comentarios.head(5), 1):
            st.info(f"**{i}.** {comentario}")
    
    # Formulario de encuesta (para asistentes)
    st.markdown("### 📝 Completar Encuesta")
    
    # Verificar si el usuario actual es asistente
    es_asistente = any(
        a['trabajador_id'] == usuario['id'] for a in cap_seleccionada['asistentes_capacitacion']
    )
    
    if not es_asistente:
        st.warning("⚠️ No eres asistente de esta capacitación")
        return
    
    # Verificar si ya respondió
    ya_respondio = supabase.table('encuestas_capacitacion').select(
        '*'
    ).eq('capacitacion_id', cap_seleccionada['id']).eq('trabajador_id', usuario['id']).execute().data
    
    if ya_respondio:
        st.success("✅ Ya has completado la encuesta para esta capacitación")
        return
    
    # Formulario de encuesta
    with st.form("form_encuesta"):
        st.markdown(f"#### 📋 Encuesta: {cap_seleccionada['tema']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            satisfaccion = st.slider(
                "¿Qué tan satisfecho estás con la capacitación? (1-5)",
                1, 5, 4,
                help="1 = Muy insatisfecho, 5 = Muy satisfecho"
            )
            
            utilidad = st.slider(
                "¿Qué tan útil fue para tu trabajo? (1-5)",
                1, 5, 4,
                help="1 = Nada útil, 5 = Extremadamente útil"
            )
        
        with col2:
            instructor_calif = st.slider(
                "Calificación del Instructor (1-5)",
                1, 5, 4
            )
            
            duracion_adecuada = st.radio(
                "¿La duración fue la adecuada?",
                options=["Sí", "Muy corta", "Muy larga"],
                horizontal=True
            )
        
        tema_claro = st.radio(
            "¿El tema fue claro y entendible?",
            options=["Sí, completamente", "Más o menos", "No, fue confuso"],
            horizontal=True
        )
        
        aplicacion_inmediata = st.checkbox(
            "¿Puedes aplicar lo aprendido inmediatamente?",
            value=True
        )
        
        comentarios = st.text_area(
            "Comentarios y Sugerencias",
            help="¿Qué mejorarías? ¿Qué te gustó más?"
        )
        
        submitted = st.form_submit_button("📤 Enviar Encuesta", type="primary")
        
        if submitted:
            # Guardar encuesta
            guardar_encuesta({
                'capacitacion_id': cap_seleccionada['id'],
                'trabajador_id': usuario['id'],
                'satisfaccion': satisfaccion,
                'utilidad': utilidad,
                'instructor_calif': instructor_calif,
                'duracion_adecuada': duracion_adecuada,
                'tema_claro': tema_claro,
                'aplicacion_inmediata': aplicacion_inmediata,
                'comentarios': comentarios
            })
            
            st.success("✅ Encuesta enviada exitosamente. ¡Gracias por tu feedback!")

def guardar_encuesta(data):
    """Guardar respuesta de encuesta en Supabase"""
    supabase = get_supabase_client()
    
    try:
        supabase.table('encuestas_capacitacion').insert(data).execute()
    except Exception as e:
        st.error(f"Error guardando encuesta: {e}")

def reporte_efectividad(usuario):
    """Reporte de efectividad y cumplimiento de capacitaciones"""
    
    st.subheader("📊 Reporte de Efectividad de Capacitaciones")
    
    supabase = get_supabase_client()
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fecha_inicio = st.date_input(
            "Fecha Inicio",
            value=datetime.now() - timedelta(days=90)
        )
    
    with col2:
        fecha_fin = st.date_input(
            "Fecha Fin",
            value=datetime.now()
        )
    
    with col3:
        area_filtro = st.multiselect(
            "Área",
            ["Producción", "Almacén", "Oficinas", "Mantenimiento", "Seguridad"]
        )
    
    # Cargar capacitaciones en rango
    query = supabase.table('capacitaciones').select(
        '*, asistentes_capacitacion(*, usuarios(*)), encuestas_capacitacion(*)'
    ).gte('fecha_programada', fecha_inicio).lte('fecha_programada', fecha_fin)
    
    if area_filtro:
        # Filtrar por área (necesita processing en memoria porque es JSON array)
        pass
    
    capacitaciones = query.execute().data
    
    if not capacitaciones:
        st.info("ℹ️ No hay capacitaciones en este período")
        return
    
    # Métricas clave
    st.markdown("#### 📈 Indicadores de Efectividad")
    
    # Procesar datos
    total_capacitaciones = len(capacitaciones)
    total_asistentes = sum(len(c['asistentes_capacitacion']) for c in capacitaciones)
    
    asistieron = sum(
        1 for c in capacitaciones for a in c['asistentes_capacitacion'] if a['asistio']
    )
    tasa_asistencia = (asistieron / total_asistentes * 100) if total_asistentes > 0 else 0
    
    # Encuestas completadas
    encuestas_completadas = sum(
        len(c['encuestas_capacitacion']) for c in capacitaciones
    )
    tasa_encuesta = (encuestas_completadas / asistieron * 100) if asistieron > 0 else 0
    
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    
    with col_kpi1:
        st.metric("🎓 Capacitaciones", total_capacitaciones)
    
    with col_kpi2:
        st.metric("👥 Asistentes", total_asistentes)
    
    with col_kpi3:
        st.metric("✅ Asistencia", f"{tasa_asistencia:.1f}%")
    
    with col_kpi4:
        st.metric("📋 Encuestas", f"{tasa_encuesta:.1f}%")
    
    # Análisis por capacitación
    st.markdown("#### 📊 Detalle por Capacitación")
    
    df_detalle = []
    
    for cap in capacitaciones:
        asistentes = len(cap['asistentes_capacitacion'])
        asistieron_cap = sum(1 for a in cap['asistentes_capacitacion'] if a['asistio'])
        encuestas_cap = len(cap['encuestas_capacitacion'])
        
        # Calcular promedio de satisfacción
        satisfacciones = [e['satisfaccion'] for e in cap['encuestas_capacitacion']]
        satisfaccion_avg = sum(satisfacciones) / len(satisfacciones) if satisfacciones else 0
        
        df_detalle.append({
            'Código': cap['codigo'],
            'Tema': cap['tema'],
            'Fecha': pd.to_datetime(cap['fecha_programada']).strftime('%d/%m/%Y'),
            'Asistentes': asistentes,
            'Asistieron': asistieron_cap,
            '% Asist': f"{asistieron_cap/asistentes*100:.1f}%" if asistentes > 0 else "N/A",
            'Encuestas': encuestas_cap,
            'Satisfacción': f"{satisfaccion_avg:.1f}/5" if satisfaccion_avg > 0 else "N/A"
        })
    
    df_detalle = pd.DataFrame(df_detalle)
    
    # Colorear según cumplimiento
    def color_cumplimiento(val):
        if val == "N/A": return ''
        num = float(val.strip('%'))
        if num >= 80: return 'background-color: #ccffcc'
        elif num >= 60: return 'background-color: #ffff99'
        else: return 'background-color: #ffcccc'
    
    styled = df_detalle.style.applymap(
        color_cumplimiento, subset=['% Asist']
    )
    
    st.dataframe(styled, use_container_width=True)
    
    # Exportar reporte completo
    if st.button("📥 Exportar Reporte Completo"):
        excel_data = df_detalle.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Descargar Reporte",
            excel_data,
            f"reporte_efectividad_{fecha_inicio}_{fecha_fin}.csv",
            "text/csv"
        )
