import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app.utils.supabase_client import get_supabase_client
from app.utils.storage_helper import subir_archivo_storage
from app.auth import requerir_rol
import json
import requests

def mostrar(usuario):
    """Módulo de Análisis de Incidentes y Accidentes (Ley 29783 Art. 33-34)"""
    requerir_rol(['admin', 'sst', 'supervisor', 'trabajador', 'gerente'])
    
    st.title("🚨 Gestión de Incidentes y Accidentes")
    
    if usuario['rol'] in ['trabajador', 'supervisor']:
        st.info("💡 Puedes reportar incidentes rápidamente desde tu móvil")
    
    # Tabs principales
    tab1, tab2, tab3, tab4 = st.tabs([
        "⚡ Reportar Incidente (< 2 min)",
        "🔍 Investigación y Análisis",
        "✅ Acciones Correctivas",
        "📊 Dashboard Incidentes"
    ])
    
    with tab1:
        reportar_incidente(usuario)
    
    with tab2:
        investigar_incidente(usuario)
    
    with tab3:
        gestionar_acciones(usuario)
    
    with tab4:
        dashboard_incidentes(usuario)

def reportar_incidente(usuario):
    """Formulario ultra-rápido para reportar incidentes (< 2 min)"""
    
    st.subheader("⚡ Reporte Rápido de Incidente")
    st.caption("Tiempo estimado: 90 segundos | Cumplimiento: Art. 33° Ley 29783")
    
    # Formulario optimizado para móvil
    with st.form("form_incidente_rapido", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Código automático
            fecha_actual = datetime.now()
            codigo = st.text_input(
                "Código del Incidente",
                value=f"INC-{fecha_actual.strftime('%Y%m%d-%H%M%S')}",
                disabled=True,
                help="Generado automáticamente"
            )
            
            tipo = st.selectbox(
                "Tipo de Evento",
                options=[
                    ("Incidente", "incidente"),
                    ("Accidente (con lesión)", "accidente"),
                    ("Enfermedad Laboral", "enfermedad_laboral"),
                    ("Cuasi-accidente", "cuasiaccidente")
                ],
                format_func=lambda x: x[0],
                help="Selecciona el tipo más adecuado"
            )[1]
        
        with col2:
            fecha_hora = st.datetime_input(
                "Fecha y Hora del Evento",
                value=fecha_actual,
                help="Fecha exacta cuando ocurrió"
            )
            
            area = st.selectbox(
                "Área donde ocurrió",
                ["Producción", "Almacén", "Oficinas", "Mantenimiento", "Planta Alta", "Planta Baja", "Área Externa"],
                help="Área geográfica de la empresa"
            )
        
        # Descripción breve
        descripcion = st.text_area(
            "¿Qué sucedió? (describa brevemente)",
            placeholder="Ej: Trabajador resbaló en piso mojado durante limpieza",
            help="Máximo 500 caracteres",
            max_chars=500
        )
        
        # Datos del trabajador afectado
        st.markdown("#### 👤 Trabajador Afectado")
        col3, col4 = st.columns(2)
        
        with col3:
            trabajador_nombre = st.text_input(
                "Nombre del Trabajador",
                value=usuario['nombre_completo'] if usuario['rol'] == 'trabajador' else "",
                help="Nombre completo de la persona afectada"
            )
        
        with col4:
            puesto_trabajo = st.text_input(
                "Puesto de Trabajo",
                help="Ej: Operario de Línea, Montacarguista"
            )
        
        # Consecuencias inmediatas
        st.markdown("#### 💥 Consecuencias")
        col5, col6 = st.columns(2)
        
        with col5:
            lesiones = st.radio(
                "¿Hubo lesiones?",
                options=["No", "Leve", "Grave", "Crítico"],
                horizontal=True,
                help="Gravedad de las lesiones físicas"
            )
        
        with col6:
            danos = st.radio(
                "¿Daños a equipo/instalaciones?",
                options=["No", "Menor", "Moderado", "Mayor"],
                horizontal=True,
                help="Impacto en infraestructura"
            )
        
        # Evidencia inmediata (fotos/videos)
        st.markdown("#### 📸 Evidencia Inmediata")
        
        col_media1, col_media2 = st.columns(2)
        
        with col_media1:
            # Cámara móvil para foto rápida
            foto = st.camera_input(
                "Tomar foto del lugar",
                help="Use la cámara de su dispositivo móvil"
            )
            
            # Audio testimonio
            audio = st.file_uploader(
                "Audio testimonio (opcional)",
                type=['mp3', 'm4a', 'wav'],
                help="Grabación de voz del afectado o testigo"
            )
        
        with col_media2:
            # Video del incidente
            video = st.file_uploader(
                "Video del incidente (opcional)",
                type=['mp4', 'mov'],
                help="Video de las consecuencias o reconstrucción"
            )
            
            # Archivos adicionales
            documentos = st.file_uploader(
                "Documentos adicionales",
                type=['pdf', 'docx'],
                accept_multiple_files=True,
                help="Reporte médico inicial, fotografías adicionales"
            )
        
        # Testigos
        testigos = st.text_area(
            "Testigos (nombres separados por coma)",
            placeholder="Juan Pérez, María García",
            help="Personas que presenciaron el evento"
        )
        
        # Prioridad automática (para n8n)
        st.markdown("---")
        prioridad = calcular_prioridad(lesiones, danos)
        
        col_prio1, col_prio2 = st.columns(2)
        
        with col_prio1:
            st.info(f"**Prioridad Calculada: {prioridad['label'].upper()}**")
            st.caption(prioridad['descripcion'])
        
        with col_prio2:
            # Checkbox para notificación inmediata
            notificar_inmediato = st.checkbox(
                "🚨 Notificar inmediatamente al supervisor",
                value=prioridad['nivel'] in ['alto', 'crítico'],
                help="Enviará alerta por email y Slack"
            )
        
        # Botón de envío
        submitted = st.form_submit_button(
            "🚀 Reportar Incidente",
            type="primary",
            use_container_width=True
        )
        
        if submitted:
            if not descripcion or not trabajador_nombre:
                st.error("❌ Descripción y nombre del trabajador son obligatorios")
                return
            
            # Preparar datos
            incidente_data = {
                'codigo': codigo,
                'tipo': tipo,
                'fecha_hora': fecha_hora.isoformat(),
                'area': area,
                'puesto_trabajo': puesto_trabajo,
                'trabajador_nombre': trabajador_nombre,
                'descripcion': descripcion,
                'consecuencias': {
                    'lesiones': lesiones,
                    'danos': danos,
                    'gravedad': prioridad['gravedad']
                },
                'testigos': [t.strip() for t in testigos.split(',') if t.strip()],
                'estado': 'reportado',
                'nivel_riesgo': prioridad['gravedad'],
                'reportado_por': usuario['id'],
                'informe_inicial': json.dumps({
                    'fecha_reporte': datetime.now().isoformat(),
                    'reportado_por_nombre': usuario['nombre_completo'],
                    'rol_reporta': usuario['rol']
                })
            }
            
            # Guardar incidente
            incidente_id = guardar_incidente(incidente_data)
            
            if incidente_id:
                # Subir evidencia
                with st.spinner("📤 Subiendo evidencia..."):
                    subir_evidencia_incidente(incidente_id, foto, video, audio, documentos)
                
                # Notificar si es necesario
                if notificar_inmediato or prioridad['nivel'] in ['alto', 'crítico']:
                    notificar_incidente(incidente_data)
                
                st.success(f"✅ Incidente reportado: {codigo}")
                st.info("El supervisor será notificado y se iniciará investigación")
                
                # Limpiar formulario
                st.rerun()

def calcular_prioridad(lesiones, danos):
    """Calcular nivel de prioridad según consecuencias"""
    # Puntuación de gravedad
    puntos_lesiones = {"No": 0, "Leve": 2, "Grave": 4, "Crítico": 6}
    puntos_danos = {"No": 0, "Menor": 1, "Moderado": 2, "Mayor": 3}
    
    gravedad = puntos_lesiones[lesiones] + puntos_danos[danos]
    
    if gravedad >= 8:
        return {'nivel': 'crítico', 'label': 'CRÍTICO', 'descripcion': 'Requiere respuesta inmediata (< 15 min)'}
    elif gravedad >= 5:
        return {'nivel': 'alto', 'label': 'ALTO', 'descripcion': 'Respuesta rápida (< 1 hora)'}
    elif gravedad >= 2:
        return {'nivel': 'medio', 'label': 'MEDIO', 'descripcion': 'Respuesta en 24 horas'}
    else:
        return {'nivel': 'bajo', 'label': 'BAJO', 'descripcion': 'Respuesta estándar (72 horas)'}

def guardar_incidente(data):
    """Guardar incidente en Supabase"""
    supabase = get_supabase_client()
    
    try:
        response = supabase.table('incidentes').insert(data).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error guardando incidente: {e}")
        return None

def subir_evidencia_incidente(incidente_id, foto, video, audio, documentos):
    """Subir múltiples tipos de evidencia"""
    urls = []
    
    # Foto
    if foto:
        url = subir_archivo_storage(
            foto,
            bucket='sst-evidencias',
            carpeta=f'incidentes/{incidente_id}/'
        )
        if url: urls.append(url)
    
    # Video
    if video:
        url = subir_archivo_storage(
            video,
            bucket='sst-evidencias',
            carpeta=f'incidentes/{incidente_id}/'
        )
        if url: urls.append(url)
    
    # Audio
    if audio:
        url = subir_archivo_storage(
            audio,
            bucket='sst-evidencias',
            carpeta=f'incidentes/{incidente_id}/'
        )
        if url: urls.append(url)
    
    # Documentos
    if documentos:
        for doc in documentos:
            url = subir_archivo_storage(
                doc,
                bucket='sst-evidencias',
                carpeta=f'incidentes/{incidente_id}/'
            )
            if url: urls.append(url)
    
    # Actualizar incidente con URLs
    if urls:
        supabase = get_supabase_client()
        supabase.table('incidentes').update({
            'evidencia': urls
        }).eq('id', incidente_id).execute()

def notificar_incidente(data):
    """Notificar vía n8n sobre nuevo incidente"""
    try:
        supabase = get_supabase_client()
        
        # Obtener supervisor del área
        supervisor = supabase.table('usuarios').select(
            'id', 'nombre_completo', 'email'
        ).eq('rol', 'supervisor').eq('area', data['area']).execute().data
        
        supervisor_email = supervisor[0]['email'] if supervisor else "sst@empresa.com"
        supervisor_id = supervisor[0]['id'] if supervisor else None
        
        # Enviar a n8n
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/incidente-reportado",
            json={
                'codigo': data['codigo'],
                'tipo': data['tipo'],
                'area': data['area'],
                'nivel_riesgo': data['nivel_riesgo'],
                'descripcion': data['descripcion'],
                'trabajador_nombre': data['trabajador_nombre'],
                'supervisor_email': supervisor_email,
                'supervisor_id': supervisor_id,
                'prioridad': data['nivel_riesgo']
            },
            timeout=5
        )
    except Exception as e:
        st.warning(f"⚠️ No se pudo notificar al supervisor: {e}")

def investigar_incidente(usuario):
    """Investigar incidente y aplicar análisis de causa raíz (5 Porqués)"""
    
    st.subheader("🔍 Investigación y Análisis de Causa Raíz")
    
    supabase = get_supabase_client()
    
    # Cargar incidentes pendientes de investigación
    incidentes = supabase.table('incidentes').select(
        '*, acciones_correctivas(*), usuarios!incidentes_reportado_por_fkey(nombre_completo)'
    ).in_('estado', ['reportado', 'en_investigacion']).execute().data
    
    if not incidentes:
        st.success("✅ No hay incidentes pendientes de investigación")
        return
    
    # Seleccionar incidente
    incidente_seleccionado = st.selectbox(
        "Seleccionar Incidente para Investigar",
        options=incidentes,
        format_func=lambda x: f"{x['codigo']} - {x['tipo'].upper()} - {x['area']} ({x['estado']})"
    )
    
    if not incidente_seleccionado:
        return
    
    # Mostrar detalles del incidente
    with st.expander("📋 Detalles del Incidente", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Código:** {incidente_seleccionado['codigo']}")
            st.write(f"**Fecha:** {incidente_seleccionado['fecha_hora']}")
            st.write(f"**Área:** {incidente_seleccionado['area']}")
            st.write(f"**Trabajador:** {incidente_seleccionado['trabajador_nombre']}")
        
        with col2:
            st.write(f"**Reportado por:** {incidente_seleccionado['usuarios']['nombre_completo']}")
            st.write(f"**Estado:** {incidente_seleccionado['estado'].upper()}")
            st.write(f"**Prioridad:** {incidente_seleccionado['nivel_riesgo']}/25")
        
        st.write(f"**Descripción:** {incidente_seleccionado['descripcion']}")
        
        # Mostrar evidencia si existe
        if incidente_seleccionado.get('evidencia'):
            st.markdown("**Evidencia:**")
            for url in incidente_seleccionado['evidencia']:
                st.link_button("Ver evidencia", url)
    
    # Formulario de investigación
    st.markdown("### 🔍 Investigación Detallada")
    
    with st.form("form_investigacion", clear_on_submit=False):
        # Método de análisis
        metodo_analisis = st.selectbox(
            "Método de Análisis de Causa Raíz",
            [
                ("Análisis 5 Porqués", "5_porques"),
                ("Árbol de Causas", "arbol_causas"),
                ("Análisis FMEA", "fmea"),
                ("Evento y Causalidad", "evento_causalidad")
            ],
            format_func=lambda x: x[0]
        )[1]
        
        # Análisis 5 Porqués (mostrar si se selecciona)
        if metodo_analisis == "5_porques":
            st.markdown("#### ❓ Análisis 5 Porqués")
            
            with st.container():
                # Secuencia de 5 porqués
                porques = []
                respuesta_anterior = ""
                
                for i in range(1, 6):
                    col_porque, col_respuesta = st.columns([1, 3])
                    
                    with col_porque:
                        st.write(f"**Porqué #{i}**")
                    
                    with col_respuesta:
                        if i == 1:
                            respuesta = st.text_input(
                                f"¿Por qué ocurrió el evento?",
                                key=f"porque_{i}"
                            )
                        else:
                            respuesta = st.text_input(
                                f"¿Por qué? (consecuencia del anterior)",
                                key=f"porque_{i}"
                            )
                        
                        porques.append({
                            'nivel': i,
                            'pregunta': f"Porqué #{i}",
                            'respuesta': respuesta
                        })
        
        # Factores contribuyentes
        st.markdown("#### ⚠️ Factores Contribuyentes")
        
        col_factor1, col_factor2 = st.columns(2)
        
        with col_factor1:
            factor_humano = st.text_area(
                "Factor Humano",
                placeholder="Ej: No uso de EPP, falta de capacitación, distracción"
            )
            
            factor_tecnico = st.text_area(
                "Factor Técnico",
                placeholder="Ej: Falla de equipo, mal diseño, falta de mantenimiento"
            )
        
        with col_factor2:
            factor_organizacional = st.text_area(
                "Factor Organizacional",
                placeholder="Ej: Falta de procedimientos, supervisión inadecuada"
            )
            
            factor_ambiental = st.text_area(
                "Factor Ambiental",
                placeholder="Ej: Iluminación deficiente, piso mojado, ruido"
            )
        
        # Conclusiones
        st.markdown("#### 🎯 Conclusiones")
        
        causa_raiz = st.text_area(
            "Causa Raíz Identificada",
            help="Descripción clara y concisa de la causa raíz",
            placeholder="Ej: Falta de mantenimiento preventivo del equipo de elevación"
        )
        
        recomendaciones = st.text_area(
            "Recomendaciones Inmediatas",
            help="Acciones para prevenir recurrencia inmediata"
        )
        
        # Adjuntos de investigación
        st.markdown("#### 📄 Evidencia de Investigación")
        
        col_inv1, col_inv2 = st.columns(2)
        
        with col_inv1:
            foto_investigacion = st.file_uploader(
                "Fotos de la escena",
                type=['jpg', 'png'],
                accept_multiple_files=True,
                key="fotos_inv"
            )
        
        with col_inv2:
            documentos_investigacion = st.file_uploader(
                "Documentos (reporte médico, croquis)",
                type=['pdf'],
                accept_multiple_files=True,
                key="docs_inv"
            )
        
        # Botones de acción
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            guardar_investigacion = st.form_submit_button(
                "💾 Guardar Investigación",
                type="primary"
            )
        
        with col_btn2:
            cerrar_incidente = st.form_submit_button(
                "✅ Cerrar Incidente (solo si es bajo riesgo)",
                help="Solo disponible para incidentes de bajo riesgo"
            )
        
        if guardar_investigacion:
            if not causa_raiz:
                st.error("❌ Debes identificar la causa raíz")
            else:
                # Guardar investigación
                guardar_investigacion_incidente(
                    incidente_seleccionado['id'],
                    {
                        'metodo_analisis': metodo_analisis,
                        'porques': porques if metodo_analisis == "5_porques" else [],
                        'factor_humano': factor_humano,
                        'factor_tecnico': factor_tecnico,
                        'factor_organizacional': factor_organizacional,
                        'factor_ambiental': factor_ambiental,
                        'causa_raiz': causa_raiz,
                        'recomendaciones': recomendaciones,
                        'investigado_por': usuario['id'],
                        'fecha_investigacion': datetime.now().isoformat()
                    },
                    foto_investigacion,
                    documentos_investigacion
                )
                
                def actualizar_estado_incidente(incidente_id, estado):
                    """Actualizar estado de incidente"""
                    supabase = get_supabase_client()
                    
                    try:
                        supabase.table('incidentes').update({
                            'estado': estado,
                            'fecha_cierre': datetime.now().date() if estado == 'cerrado' else None
                        }).eq('id', incidente_id).execute()
                    except Exception as e:
                        st.error(f"Error actualizando estado: {e}")


                # Actualizar estado
                nuevo_estado = 'cerrado' if incidente_seleccionado['nivel_riesgo'] < 5 else 'analizado'
                actualizar_estado_incidente(incidente_seleccionado['id'], nuevo_estado)
                
                st.success(f"✅ Investigación guardada. Estado: {nuevo_estado.upper()}")
                
                # Crear acciones correctivas automáticas
                if recomendaciones:
                    st.info("🔄 Creando acciones correctivas automáticas...")
                    crear_accion_correctiva_automatica(
                        incidente_seleccionado['id'],
                        recomendaciones,
                        usuario['id']
                    )
                
                st.rerun()

def guardar_investigacion_incidente(incidente_id, investigacion_data, fotos, docs):
    """Guardar datos de investigación"""
    supabase = get_supabase_client()
    
    try:
        # Actualizar incidente
        supabase.table('incidentes').update({
            'metodo_analisis': investigacion_data['metodo_analisis'],
            'causa_raiz': investigacion_data['causa_raiz'],
            'investigacion_data': json.dumps(investigacion_data),
            'estado': 'analizado'
        }).eq('id', incidente_id).execute()
        
        # Subir evidencia de investigación
        if fotos:
            for foto in fotos:
                subir_archivo_storage(
                    foto,
                    bucket='sst-evidencias',
                    carpeta=f'incidentes/{incidente_id}/investigacion/'
                )
        
        if docs:
            for doc in docs:
                subir_archivo_storage(
                    doc,
                    bucket='sst-evidencias',
                    carpeta=f'incidentes/{incidente_id}/investigacion/'
                )
                
    except Exception as e:
        st.error(f"Error guardando investigación: {e}")

def crear_accion_correctiva_automatica(incidente_id, recomendaciones, responsable_id):
    """Crear acciones correctivas derivadas de investigación"""
    supabase = get_supabase_client()
    
    try:
        # Parsear recomendaciones línea por línea
        acciones = recomendaciones.split('\n')
        
        for accion in acciones:
            if accion.strip():
                supabase.table('acciones_correctivas').insert({
                    'incidente_id': incidente_id,
                    'descripcion': accion.strip(),
                    'responsable_id': responsable_id,
                    'fecha_limite': (datetime.now() + timedelta(days=7)).isoformat(),
                    'estado': 'abierta'
                }).execute()
        
        # Notificar vía n8n
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/acciones-creadas",
            json={"incidente_id": incidente_id, "num_acciones": len(acciones)}
        )
        
    except Exception as e:
        st.warning(f"⚠️ No se pudieron crear todas las acciones: {e}")

def gestionar_acciones(usuario):
    """Gestionar acciones correctivas y preventivas"""
    
    st.subheader("✅ Acciones Correctivas y Preventivas")
    
    supabase = get_supabase_client()
    
    # Filtros
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
    
    with col_filtro1:
        estado_filtro = st.selectbox(
            "Estado",
            options=["todos", "abierta", "en_progreso", "implementada", "verificada"],
            index=0
        )
    
    with col_filtro2:
        responsable_filtro = st.selectbox(
            "Responsable",
            options=["todos", "yo", "otros"]
        )
    
    with col_filtro3:
        fecha_filtro = st.date_input(
            "Fecha Límite Hasta",
            value=datetime.now().date() + timedelta(days=30)
        )
    
    # Consultar acciones
    query = supabase.from_('acciones_correctivas').select(
        '*, incidentes(codigo, area), usuarios(nombre_completo)'
    )
    
    if estado_filtro != "todos":
        query = query.eq('estado', estado_filtro)
    
    if responsable_filtro == "yo":
        query = query.eq('responsable_id', usuario['id'])
    elif responsable_filtro == "otros":
        query = query.neq('responsable_id', usuario['id'])
    
    acciones = query.execute().data
    
    if not acciones:
        st.success("✅ No hay acciones con los filtros seleccionados")
        return
    
    df_acciones = pd.DataFrame(acciones)
    
    # Dashboard de acciones
    st.markdown("### 📊 Resumen de Acciones")
    
    col_res1, col_res2, col_res3, col_res4 = st.columns(4)
    
    with col_res1:
        st.metric("🔴 Abiertas", len(df_acciones[df_acciones['estado'] == 'abierta']))
    
    with col_res2:
        st.metric("🟡 En Progreso", len(df_acciones[df_acciones['estado'] == 'en_progreso']))
    
    with col_res3:
        st.metric("🟢 Implementadas", len(df_acciones[df_acciones['estado'] == 'implementada']))
    
    with col_res4:
        # Calcular atrasadas
        atrasadas = sum(
            1 for _, a in df_acciones.iterrows()
            if pd.to_datetime(a['fecha_limite']).date() < datetime.now().date()
            and a['estado'] not in ['implementada', 'verificada']
        )
        st.metric("⏰ Atrasadas", atrasadas)
    
    # Lista de acciones
    st.markdown("### 📋 Acciones Detalladas")
    
    # Seleccionar acción para editar
    accion_editar = st.selectbox(
        "Seleccionar Acción para Actualizar",
        options=df_acciones['id'].tolist(),
        format_func=lambda x: f"ID: {x} - {df_acciones[df_acciones['id'] == x]['descripcion'].iloc[0][:60]}..."
    )
    
    if accion_editar:
        accion_actual = df_acciones[df_acciones['id'] == accion_editar].iloc[0]
        
        with st.form(f"form_accion_{accion_editar}"):
            st.write(f"**Incid.:** {accion_actual['incidentes']['codigo']} | **Área:** {accion_actual['incidentes']['area']}")
            st.write(f"**Descripción:** {accion_actual['descripcion']}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nuevo_estado = st.selectbox(
                    "Nuevo Estado",
                    options=["abierta", "en_progreso", "implementada", "verificada"],
                    index=0
                )
                
                fecha_limite = st.date_input(
                    "Fecha Límite",
                    value=pd.to_datetime(accion_actual['fecha_limite']).date()
                )
            
            with col2:
                porcentaje = st.slider(
                    "% de Avance",
                    0, 100,
                    value=accion_actual.get('porcentaje_avance', 0)
                )
                
                evidencia = st.file_uploader(
                    "Evidencia de la acción",
                    type=['jpg', 'png', 'pdf'],
                    key=f"evid_accion_{accion_editar}"
                )
            
            comentarios = st.text_area(
                "Comentarios de Actualización",
                value=accion_actual.get('comentarios', '')
            )
            
            actualizar = st.form_submit_button("💾 Actualizar Acción", type="primary")
            
            if actualizar:
                actualizar_accion(
                    accion_editar,
                    {
                        'estado': nuevo_estado,
                        'fecha_limite': fecha_limite.isoformat(),
                        'porcentaje_avance': porcentaje,
                        'comentarios': comentarios
                    },
                    evidencia
                )
                
                st.success("✅ Acción actualizada exitosamente")
                st.rerun()

def actualizar_accion(accion_id, data, evidencia_archivo):
    """Actualizar acción correctiva"""
    supabase = get_supabase_client()
    
    try:
        # Subir evidencia si existe
        if evidencia_archivo:
            url = subir_archivo_storage(
                evidencia_archivo,
                bucket='sst-evidencias',
                carpeta=f'acciones/{accion_id}/'
            )
            data['evidencia_url'] = url
        
        # Actualizar estado
        supabase.table('acciones_correctivas').update(data).eq('id', accion_id).execute()
        
        # Notificar cierre
        if data['estado'] == 'implementada':
            requests.post(
                st.secrets["N8N_WEBHOOK_URL"] + "/accion-cerrada",
                json={"accion_id": accion_id}
            )
            
    except Exception as e:
        st.error(f"Error actualizando acción: {e}")

def dashboard_incidentes(usuario):
    """Dashboard de seguimiento de incidentes"""
    
    st.subheader("📊 Dashboard de Incidentes")
    
    supabase = get_supabase_client()
    
    # Filtros
    with st.expander("🔍 Filtros", expanded=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            fecha_inicio = st.date_input(
                "Fecha Inicio",
                value=datetime.now() - timedelta(days=30)
            )
        
        with col_f2:
            fecha_fin = st.date_input(
                "Fecha Fin",
                value=datetime.now()
            )
        
        with col_f3:
            area_filtro = st.multiselect(
                "Área",
                ["Producción", "Almacén", "Oficinas", "Mantenimiento", "Planta Alta", "Planta Baja"]
            )
    
    # Cargar datos
    query = supabase.table('incidentes').select(
        '*, acciones_correctivas(*), usuarios!incidentes_reportado_por_fkey(nombre_completo)'
    ).gte('fecha_hora', fecha_inicio).lte('fecha_hora', fecha_fin)
    
    if area_filtro:
        query = query.in_('area', area_filtro)
    
    incidentes = query.execute().data
    
    if not incidentes:
        st.info("ℹ️ No hay incidentes en este período")
        return
    
    df_incidentes = pd.DataFrame(incidentes)
    
    # KPIs
    st.markdown("#### 📈 Indicadores Clave")
    
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    
    with col_kpi1:
        total_incidentes = len(df_incidentes)
        st.metric("🚨 Total Incidentes", total_incidentes)
    
    with col_kpi2:
        incidentes_cerrados = len(df_incidentes[df_incidentes['estado'] == 'cerrado'])
        tasa_cierre = incidentes_cerrados / total_incidentes * 100
        st.metric("✅ % Cierre", f"{tasa_cierre:.1f}%")
    
    with col_kpi3:
        avg_riesgo = df_incidentes['nivel_riesgo'].mean()
        st.metric("⚠️ Riesgo Promedio", f"{avg_riesgo:.1f}/25")
    
    with col_kpi4:
        # Calcular TF (Tasa de Frecuencia)
        horas_hombre = 50000  # Simulado - debería venir de sistema de asistencia
        acc_con_lesion = len(df_incidentes[df_incidentes['consecuencias']['lesiones'] != 'No'])
        tf = calcular_tasa_frecuencia(acc_con_lesion, horas_hombre)
        st.metric("📊 Tasa Frecuencia", f"{tf:.2f}")
    
    # Gráficos
    col_graph1, col_graph2 = st.columns(2)
    
    with col_graph1:
        # Serie temporal
        df_incidentes['fecha'] = pd.to_datetime(df_incidentes['fecha_hora']).dt.date
        incidentes_dia = df_incidentes.groupby('fecha').size()
        
        fig = px.line(
            incidentes_dia,
            title="Incidentes por Día",
            labels={'value': 'N° Incidentes', 'fecha': 'Fecha'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col_graph2:
        # Distribución por tipo
        fig2 = px.pie(
            df_incidentes,
            names='tipo',
            title="Distribución por Tipo",
            hole=0.5
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # Tabla de incidentes
    st.markdown("#### 📋 Listado de Incidentes")
    
    # Preparar datos para mostrar
    df_display = df_incidentes.copy()
    df_display['reportado_por'] = df_display['usuarios']['nombre_completo']
    
    # Colorear por estado
    def color_estado(val):
        if val == 'abierto': return 'background-color: #ffcccc'
        elif val == 'en_investigacion': return 'background-color: #ffff99'
        elif val == 'analizado': return 'background-color: #cce5ff'
        else: return 'background-color: #ccffcc'
    
    styled = df_display[['codigo', 'tipo', 'area', 'fecha_hora', 'nivel_riesgo', 'estado', 'reportado_por']].style.applymap(
        color_estado, subset=['estado']
    )
    
    st.dataframe(styled, use_container_width=True)
    
    # Exportar reporte
    if st.button("📥 Exportar Reporte de Incidentes"):
        excel_data = df_incidentes.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Descargar Reporte",
            excel_data,
            f"reporte_incidentes_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
