import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app.utils.storage_helper import subir_archivo_storage
from app.utils.supabase_client import get_supabase_client
from app.auth import requerir_rol
import json
import uuid
import requests

def mostrar(usuario):
    """Módulo de Inspecciones de Seguridad (Ley 29783 Art. 27)"""
    requerir_rol(['admin', 'sst', 'supervisor'])
    
    st.title("📋 Inspecciones de Seguridad Laboral")
    
    # Tabs principales
    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 Crear Checklist",
        "📅 Programar Inspección",
        "🔍 Ejecutar Inspección",
        "📊 Seguimiento Hallazgos"
    ])
    
    with tab1:
        crear_checklist(usuario)
    
    with tab2:
        programar_inspeccion(usuario)
    
    with tab3:
        ejecutar_inspeccion(usuario)
    
    with tab4:
        seguimiento_hallazgos(usuario)

def crear_checklist(usuario):
    """Crear checklist digital personalizable"""

    st.subheader("📝 Configurar Nueva Checklist")

    # ------------------------
    # Estado inicial
    # ------------------------
    if 'preguntas' not in st.session_state:
        st.session_state.preguntas = []

    # ---------------------------------------------------------
    # 1) Sección AGREGAR PREGUNTA (FUERA del form)
    # ---------------------------------------------------------
    st.markdown("### 📋 Preguntas del Checklist")
    st.info("Agrega preguntas específicas para esta inspección. Usa 'Agregar Pregunta' para múltiples items.")

    with st.expander("➕ Agregar Nueva Pregunta", expanded=True):
        col_p1, col_p2, col_p3 = st.columns([3, 2, 1])

        with col_p1:
            pregunta_texto = st.text_input(
                "Texto de la Pregunta",
                key="pregunta_temp",
                help="Ej: ¿El extintor está en su lugar y con presión correcta?"
            )

        with col_p2:
            tipo_respuesta = st.selectbox(
                "Tipo de Respuesta",
                options=[
                    ("Si/No", "si_no"),
                    ("Sí/No/NA", "si_no_na"),
                    ("Escala 1-5", "escala"),
                    ("Texto", "texto")
                ],
                format_func=lambda x: x[0],
                key="tipo_temp"
            )[1]

        with col_p3:
            categoria = st.text_input(
                "Categoría",
                value="General",
                key="categoria_temp"
            )

        agregar = st.button("Agregar Pregunta", key="btn_agregar_pregunta")

        if agregar:
            if not pregunta_texto.strip():
                st.warning("Escribe el texto de la pregunta antes de agregarla.")
            else:
                st.session_state.preguntas.append({
                    "id": str(uuid.uuid4())[:8],
                    "pregunta": pregunta_texto,
                    "tipo": tipo_respuesta,
                    "categoria": categoria
                })
                st.success(f"✅ Pregunta agregada: {pregunta_texto[:50]}...")
                # Limpiar campos usando del en lugar de asignación directa
                if 'pregunta_temp' in st.session_state:
                    del st.session_state.pregunta_temp
                if 'categoria_temp' in st.session_state:
                    del st.session_state.categoria_temp
                if 'tipo_temp' in st.session_state:
                    del st.session_state.tipo_temp
                st.rerun()

    # ---------------------------------------------------------
    # 2) Mostrar preguntas agregadas (FUERA del form)
    # ---------------------------------------------------------
    if st.session_state.preguntas:
        st.markdown("#### 📌 Preguntas Configuradas")

        for idx, p in enumerate(st.session_state.preguntas):
            col_show1, col_show2, col_show3, col_show4 = st.columns([3, 2, 2, 1])

            with col_show1:
                st.write(f"**{idx + 1}.** {p['pregunta']}")

            with col_show2:
                st.caption(f"Tipo: {p['tipo']}")

            with col_show3:
                st.caption(f"Cat: {p['categoria']}")

            with col_show4:
                if st.button("🗑️", key=f"del_{p['id']}"):
                    st.session_state.preguntas.pop(idx)
                    st.rerun()
    else:
        st.info("Aún no agregaste preguntas.")

    st.divider()

    # ---------------------------------------------------------
    # 3) FORM SOLO para datos de checklist + GUARDAR
    # ---------------------------------------------------------
    with st.form("form_checklist", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            nombre = st.text_input(
                "Nombre de la Checklist",
                help="Ej: Inspección Diaria Área de Producción",
                key="nombre_checklist"
            )
            area = st.selectbox(
                "Área Aplicación",
                ["Producción", "Almacén", "Oficinas", "Mantenimiento", "Planta Alta", "Planta Baja"],
                key="area_checklist"
            )

        with col2:
            periodicidad = st.selectbox(
                "Periodicidad Sugerida",
                ["Diaria", "Semanal", "Mensual", "Trimestral"],
                help="Ayuda al programa automático de inspecciones",
                key="periodicidad_checklist"
            )

            activa = st.checkbox(
                "Activa inmediatamente",
                value=True,
                key="activa_checklist"
            )

        submitted = st.form_submit_button("💾 Guardar Checklist", type="primary")

    # ---------------------------------------------------------
    # 4) Acción de guardado
    # ---------------------------------------------------------
    if submitted:
        if not nombre.strip():
            st.error("La checklist necesita un nombre.")
            return
        if not st.session_state.preguntas:
            st.error("Agrega al menos una pregunta.")
            return

        guardar_checklist({
            'nombre': nombre,
            'area': area,
            # 'periodicidad': periodicidad,
            'activo': activa,
            'items': json.dumps(st.session_state.preguntas)
        })

        st.session_state.preguntas = []
        st.success("✅ Checklist guardada exitosamente!")
        st.rerun()

def guardar_checklist(data):
    """Guardar checklist en Supabase y activar webhook"""
    supabase = get_supabase_client()
    
    try:
        # Insertar
        result = supabase.table('checklists').insert(data).execute()
        
        # Notificar vía n8n
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/checklist-nueva",
            json={
                "checklist_id": result.data[0]['id'],
                "nombre": data['nombre'],
                "area": data['area']
            }
        )
    except Exception as e:
        st.error(f"Error guardando checklist: {e}")

def programar_inspeccion(usuario):
    """Programar inspección recurrente"""

    st.subheader("📅 Programar Nueva Inspección")

    supabase = get_supabase_client()

    # Cargar checklists disponibles
    checklists = supabase.table('checklists').select('*').eq('activo', True).execute().data

    if not checklists:
        st.warning("⚠️ No hay checklists activas. Crea una primero.")
        return

    with st.form("form_programar", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            checklist_id = st.selectbox(
                "Checklist",
                options=[c['id'] for c in checklists],
                format_func=lambda x: next(c['nombre'] for c in checklists if c['id'] == x)
            )

            area = st.selectbox(
                "Área a Inspeccionar",
                ["Producción", "Almacén", "Oficinas", "Mantenimiento"]
            )

        with col2:
            fecha_programada = st.date_input(
                "Fecha Programada",
                min_value=datetime.now().date()
            )

            inspector_id = st.selectbox(
                "Inspector Asignado",
                options=[usuario['id']],
                format_func=lambda x: usuario['nombre_completo']
            )

        # Programación recurrente
        st.markdown("### 🔄 Repetición (Opcional)")
        es_recurrente = st.checkbox("Programar como recurrente")

        frecuencia = None
        veces = None

        if es_recurrente:
            col_recurrente1, col_recurrente2 = st.columns(2)

            with col_recurrente1:
                frecuencia = st.selectbox(
                    "Frecuencia",
                    options=["diaria", "semanal", "mensual"],
                    help="Crea inspecciones automáticas"
                )

            with col_recurrente2:
                veces = st.number_input(
                    "N° de repeticiones",
                    min_value=1,
                    max_value=52,
                    value=4,
                    help="Ej: 4 semanas = 1 mes de inspecciones semanales"
                )

        submitted = st.form_submit_button("📅 Programar", type="primary")

    # -------------------------
    # Acción al enviar
    # -------------------------
    if submitted:

        if es_recurrente:
            # Crear múltiples inspecciones
            fechas = generar_fechas_recurrencia(fecha_programada, frecuencia, veces)

            ok_count = 0
            for fecha in fechas:
                ok = guardar_inspeccion_programada({
                    'checklist_id': checklist_id,
                    'area': area,
                    # ✅ pasamos ISO string para evitar problemas JSON
                    'fecha_programada': fecha.isoformat(),
                    'supervisor_id': inspector_id,
                    'estado': 'programada'
                })
                if ok:
                    ok_count += 1

            if ok_count > 0:
                st.success(f"✅ {ok_count} inspecciones programadas!")
            else:
                st.error("❌ No se pudo programar ninguna inspección.")

        else:
            ok = guardar_inspeccion_programada({
                'checklist_id': checklist_id,
                'area': area,
                # ✅ pasamos ISO string para evitar problemas JSON
                'fecha_programada': fecha_programada.isoformat(),
                'supervisor_id': inspector_id,
                'estado': 'programada'
            })

            if ok:
                st.success("✅ Inspección programada exitosamente!")
            else:
                st.error("❌ Error programando la inspección.")

def generar_fechas_recurrencia(fecha_inicio, frecuencia, veces):
    """Generar fechas para inspecciones recurrentes"""
    fechas = []
    fecha_actual = fecha_inicio
    
    for i in range(veces):
        fechas.append(fecha_actual)
        
        if frecuencia == "diaria":
            fecha_actual += timedelta(days=1)
        elif frecuencia == "semanal":
            fecha_actual += timedelta(weeks=1)
        elif frecuencia == "mensual":
            # Sumar mes manualmente
            mes = fecha_actual.month + 1
            año = fecha_actual.year
            if mes > 12:
                mes = 1
                año += 1
            fecha_actual = fecha_actual.replace(year=año, month=mes)
    
    return fechas

def guardar_inspeccion_programada(data):
    """Guardar inspección programada y notificar"""
    supabase = get_supabase_client()

    # 1) Guardar en BD
    try:
        result = supabase.table('inspecciones').insert(data).execute()
    except Exception as e:
        st.error(f"Error programando inspección (BD): {e}")
        return False

    # 2) Notificar a n8n (sin romper el guardado)
    """ try:
        payload = {
            "inspeccion_id": result.data[0]['id'],
            "area": data['area'],
            "fecha": data['fecha_programada'].isoformat()
                     if hasattr(data['fecha_programada'], "isoformat")
                     else str(data['fecha_programada']),
            "inspector_id": data['supervisor_id']
        }

        r = requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/inspeccion-programada",
            json=payload,
            timeout=15
        )
        r.raise_for_status()

    except Exception as e:
        st.warning(f"Inspección guardada, pero falló notificación a n8n: {e}") """

    return True


def ejecutar_inspeccion(usuario):
    """Ejecutar inspección en campo (interfaz móvil)"""

    st.subheader("🔍 Ejecutar Inspección Programada")

    supabase = get_supabase_client()

    # Cargar inspecciones asignadas al usuario y pendientes
    inspecciones_pendientes = supabase.from_('inspecciones').select(
        '*, checklists(*)'
    ).eq('supervisor_id', usuario['id']).in_(
        'estado', ['programada', 'en_proceso']
    ).execute().data

    if not inspecciones_pendientes:
        st.success("✅ No tienes inspecciones pendientes. ¡Excelente!")
        return

    # Seleccionar inspección a ejecutar
    inspeccion_seleccionada = st.selectbox(
        "Seleccionar Inspección",
        options=inspecciones_pendientes,
        format_func=lambda x: f"{x['checklists']['nombre']} - {x['area']} - {x['fecha_programada']}"
    )

    if not inspeccion_seleccionada:
        return

    # Mostrar información de la inspección
    with st.expander("📋 Detalles de la Inspección", expanded=True):
        st.json({
            "Checklist": inspeccion_seleccionada['checklists']['nombre'],
            "Área": inspeccion_seleccionada['area'],
            "Fecha Programada": inspeccion_seleccionada['fecha_programada'],
            "Estado Actual": inspeccion_seleccionada['estado']
        })

    # ---------------------------------------------------------
    # Cargar preguntas del checklist (FIX items str/list)
    # ---------------------------------------------------------
    checklist_data = inspeccion_seleccionada['checklists']
    items_raw = checklist_data.get('items', [])

    if isinstance(items_raw, str):
        try:
            preguntas = json.loads(items_raw)
        except:
            preguntas = []
    elif isinstance(items_raw, list):
        preguntas = items_raw
    else:
        preguntas = []

    # ---------------------------------------------------------
    # Normalizar preguntas (FIX KeyError 'id')
    # garantiza: id, pregunta, tipo, categoria
    # ---------------------------------------------------------
    preguntas_norm = []
    for i, p in enumerate(preguntas):
        if not isinstance(p, dict):
            continue

        pid = p.get("id") or p.get("pregunta_id") or str(uuid.uuid4())[:8]
        texto = p.get("pregunta") or p.get("texto") or p.get("question") or f"Pregunta {i+1}"
        tipo = p.get("tipo") or p.get("tipo_respuesta") or "si_no"
        categoria = p.get("categoria") or "General"

        preguntas_norm.append({
            "id": pid,
            "pregunta": texto,
            "tipo": tipo,
            "categoria": categoria
        })

    preguntas = preguntas_norm

    if not preguntas:
        st.warning("⚠️ Esta checklist no tiene preguntas válidas.")
        return

    st.markdown(f"### 📋 Checklist: {checklist_data['nombre']}")
    st.caption(f"Total de preguntas: {len(preguntas)}")

    # ---------------------------------------------------------
    # Formulario de ejecución
    # ---------------------------------------------------------
    with st.form("form_ejecutar_inspeccion", clear_on_submit=False):

        # pasar a "en_proceso" solo una vez por sesión
        flag_key = f"estado_en_proceso_{inspeccion_seleccionada['id']}"
        if inspeccion_seleccionada['estado'] == 'programada' and not st.session_state.get(flag_key):
            actualizar_estado_inspeccion(inspeccion_seleccionada['id'], 'en_proceso')
            st.session_state[flag_key] = True

        respuestas = []
        hallazgos_detectados = []

        for idx, pregunta in enumerate(preguntas):
            st.markdown(f"**{idx + 1}. {pregunta['pregunta']}**")
            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                # Campo de respuesta según tipo
                if pregunta['tipo'] == 'si_no':
                    respuesta = st.radio(
                        "Respuesta",
                        options=["Sí", "No"],
                        horizontal=True,
                        key=f"resp_{pregunta['id']}"
                    )
                elif pregunta['tipo'] == 'si_no_na':
                    respuesta = st.radio(
                        "Respuesta",
                        options=["Sí", "No", "N/A"],
                        horizontal=True,
                        key=f"resp_{pregunta['id']}"
                    )
                elif pregunta['tipo'] == 'escala':
                    respuesta = st.slider(
                        "Calificación (1-5)",
                        1, 5, 5,
                        key=f"resp_{pregunta['id']}"
                    )
                else:  # texto
                    respuesta = st.text_input(
                        "Observación",
                        key=f"resp_{pregunta['id']}"
                    )

            with col2:
                evidencia = st.file_uploader(
                    f"Evidencia (foto/video) - Pregunta {idx + 1}",
                    type=['jpg', 'png', 'mp4'],
                    key=f"evid_{pregunta['id']}"
                )

                camara = st.camera_input(
                    f"Tomar foto móvil - Pregunta {idx + 1}",
                    key=f"cam_{pregunta['id']}"
                )

            with col3:
                st.caption(f"Categoría: {pregunta['categoria']}")

            # Guardar respuesta
            respuestas.append({
                'pregunta_id': pregunta['id'],
                'pregunta_texto': pregunta['pregunta'],
                'respuesta': respuesta,
                'categoria': pregunta['categoria']
            })

            # Detectar hallazgo automático
            if (pregunta['tipo'] in ['si_no', 'si_no_na'] and respuesta == "No") or \
               (pregunta['tipo'] == 'escala' and respuesta <= 2):

                st.warning("⚠️ **HALLAZGO DETECTADO**")

                with st.expander("📝 Detallar Hallazgo", expanded=True):
                    hallazgo_desc = st.text_area(
                        "Descripción del Hallazgo",
                        value=f"No conformidad en: {pregunta['pregunta']}",
                        key=f"hall_{pregunta['id']}"
                    )

                    responsable = st.selectbox(
                        "Responsable de Corrección",
                        ["Juan Pérez", "María García", "Carlos Ruiz"],
                        key=f"resp_hall_{pregunta['id']}"
                    )

                    fecha_limite = st.date_input(
                        "Fecha Límite de Corrección",
                        value=datetime.now().date() + timedelta(days=7),
                        key=f"fecha_hall_{pregunta['id']}"
                    )

                    hallazgos_detectados.append({
                        'descripcion': hallazgo_desc,
                        'categoria': pregunta['categoria'],
                        'responsable': responsable,
                        'fecha_limite': fecha_limite,
                        'evidencia': evidencia or camara
                    })

        col_fin1, col_fin2 = st.columns([3, 1])

        with col_fin1:
            observaciones_finales = st.text_area(
                "Observaciones Generales de la Inspección",
                help="Comentarios adicionales sobre la inspección"
            )

        with col_fin2:
            st.markdown("### 🎯 Acción")
            finalizada = st.form_submit_button(
                "✅ Finalizar Inspección",
                type="primary",
                help="Guarda todas las respuestas y hallazgos"
            )

            guardar_borrador = st.form_submit_button(
                "💾 Guardar Borrador",
                help="Guarda progreso sin finalizar"
            )

    # ---------------------------------------------------------
    # Guardado fuera del form
    # ---------------------------------------------------------
    if finalizada or guardar_borrador:

        guardar_resultado_inspeccion(
            inspeccion_seleccionada['id'],
            respuestas,
            hallazgos_detectados,
            observaciones_finales,
            estado='completada' if finalizada else 'en_proceso'
        )

        if finalizada:
            st.success("✅ Inspección finalizada exitosamente!")

            if hallazgos_detectados:
                # limpiar hallazgos para n8n (sin evidencias/fechas crudas)
                hallazgos_notif = []
                for h in hallazgos_detectados:
                    hallazgos_notif.append({
                        "descripcion": h["descripcion"],
                        "categoria": h["categoria"],
                        "responsable": h["responsable"],
                        "fecha_limite": h["fecha_limite"].isoformat()
                            if hasattr(h["fecha_limite"], "isoformat") else str(h["fecha_limite"])
                    })

                notificar_hallazgos(inspeccion_seleccionada, hallazgos_notif)
        else:
            st.info("💾 Borrador guardado. Puedes continuar más tarde.")

def actualizar_estado_inspeccion(inspeccion_id, estado):
    """Actualizar estado de inspección"""
    supabase = get_supabase_client()
    supabase.table('inspecciones').update({
        'estado': estado,
        'fecha_realizada': datetime.now().date() if estado == 'completada' else None
    }).eq('id', inspeccion_id).execute()

def guardar_resultado_inspeccion(inspeccion_id, respuestas, hallazgos, observaciones, estado):
    """Guardar resultados de inspección y crear hallazgos"""
    supabase = get_supabase_client()
    
    try:
        # Guardar respuestas en JSON (puede crear tabla 'respuestas_inspeccion' si se necesita historial)
        supabase.table('inspecciones').update({
            'estado': estado,
            'fecha_realizada': datetime.now().date().isoformat(),
            # 'observaciones': observaciones,
            # 'respuestas_json': json.dumps(respuestas)
        }).eq('id', inspeccion_id).execute()
        
        # Crear hallazgos
        for hallazgo in hallazgos:
            # Subir evidencia si existe
            evidencia_url = None
            if hallazgo['evidencia']:
                evidencia_url = subir_evidencia_hallazgo(
                    hallazgo['evidencia'],
                    inspeccion_id
                )
            
            # Insertar hallazgo
            supabase.table('hallazgos').insert({
                'inspeccion_id': inspeccion_id,
                'descripcion': hallazgo['descripcion'],
                'categoria': hallazgo['categoria'],
                'evidencia': [evidencia_url] if evidencia_url else [],
                'estado': 'abierto',
                'responsable_id': hallazgo['responsable'],
                'fecha_limite': hallazgo['fecha_limite'].isoformat()
            }).execute()
    
    except Exception as e:
        st.error(f"Error guardando resultados: {e}")

def subir_evidencia_hallazgo(archivo, inspeccion_id):
    """Wrapper para subir evidencia de hallazgo"""
    return subir_archivo_storage(
        archivo,
        bucket='sst-evidencias',
        carpeta=f'inspecciones/{inspeccion_id}/'
    )


def notificar_hallazgos(inspeccion, hallazgos):
    """Notificar vía n8n sobre hallazgos detectados"""
    try:
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/hallazgos-detectados",
            json={
                "inspeccion_id": inspeccion['id'],
                "area": inspeccion['area'],
                "total_hallazgos": len(hallazgos),
                "hallazgos": hallazgos
            }
        )
    except:
        pass  # Silenciar error de notificación

def seguimiento_hallazgos(usuario):
    """Seguimiento y cierre de hallazgos"""

    st.subheader("📊 Seguimiento de Hallazgos")

    supabase = get_supabase_client()

    # -------------------------
    # Filtros
    # -------------------------
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)

    with col_filtro1:
        estado_filtro = st.selectbox(
            "Estado",
            options=["todos", "abierto", "en_correccion", "cerrado"],
            index=0
        )

    with col_filtro2:
        area_filtro = st.selectbox(
            "Área",
            options=["todos", "Producción", "Almacén", "Oficinas", "Mantenimiento"]
        )

    with col_filtro3:
        fecha_filtro = st.date_input(
            "Fecha Límite Hasta",
            value=datetime.now().date() + timedelta(days=30)
        )

    # -------------------------
    # Consultar hallazgos
    # -------------------------
    query = supabase.table('hallazgos').select(
        '*, inspecciones(area, fecha_programada), usuarios(nombre_completo)'
    )

    if estado_filtro != "todos":
        query = query.eq('estado', estado_filtro)

    # traemos todo y filtramos en pandas para evitar problemas con nested
    hallazgos = query.execute().data

    if not hallazgos:
        st.success("✅ No hay hallazgos con los filtros seleccionados")
        return

    df_hallazgos = pd.DataFrame(hallazgos)

    # -------------------------
    # Preparar datos para visualización (FIX del KeyError)
    # -------------------------
    df_display = df_hallazgos.copy()

    # extraer area/fecha desde dict anidado "inspecciones"
    df_display["area"] = df_display["inspecciones"].apply(
        lambda x: x.get("area") if isinstance(x, dict) else None
    )
    df_display["fecha_programada"] = df_display["inspecciones"].apply(
        lambda x: x.get("fecha_programada") if isinstance(x, dict) else None
    )

    # extraer inspector desde dict anidado "usuarios"
    df_display["inspector"] = df_display["usuarios"].apply(
        lambda x: x.get("nombre_completo") if isinstance(x, dict) else None
    )

    # -------------------------
    # Aplicar filtros extra en pandas
    # -------------------------
    if area_filtro != "todos":
        df_display = df_display[df_display["area"] == area_filtro]

    # fecha_limite puede venir como string -> convertimos
    if "fecha_limite" in df_display.columns:
        df_display["fecha_limite_dt"] = pd.to_datetime(
            df_display["fecha_limite"], errors="coerce"
        ).dt.date
        df_display = df_display[df_display["fecha_limite_dt"] <= fecha_filtro]

    if df_display.empty:
        st.success("✅ No hay hallazgos con los filtros seleccionados")
        return

    # -------------------------
    # Tabla interactiva
    # -------------------------
    st.markdown("#### 📋 Listado de Hallazgos")

    def color_estado(val):
        if val == 'abierto':
            return 'background-color: #ffcccc; color: #d40000'
        elif val == 'en_correccion':
            return 'background-color: #ffff99; color: #cc8800'
        else:
            return 'background-color: #ccffcc; color: #008800'

    styled = df_display[
        ['descripcion', 'area', 'categoria', 'estado', 'fecha_limite']
    ].style.applymap(color_estado, subset=['estado'])

    st.dataframe(styled, use_container_width=True)

    # -------------------------
    # Acciones por hallazgo
    # -------------------------
    st.markdown("#### 🎯 Acciones")

    hallazgo_ids = df_display['id'].tolist()

    hallazgo_editar = st.selectbox(
        "Seleccionar Hallazgo para Actualizar",
        options=hallazgo_ids,
        format_func=lambda x: f"ID: {x} - {df_display[df_display['id'] == x]['descripcion'].iloc[0][:50]}..."
        if not df_display[df_display['id'] == x].empty else f"ID: {x}"
    )

    if hallazgo_editar:
        hallazgo_actual = df_display[df_display['id'] == hallazgo_editar].iloc[0]

        with st.form("form_actualizar_hallazgo"):
            nuevo_estado = st.selectbox(
                "Nuevo Estado",
                options=["abierto", "en_correccion", "cerrado"],
                index=["abierto", "en_correccion", "cerrado"].index(hallazgo_actual['estado'])
            )

            comentarios = st.text_area(
                "Comentarios de Actualización",
                value=hallazgo_actual.get('comentarios', '')
            )

            if nuevo_estado == 'cerrado':
                fecha_cierre = st.date_input(
                    "Fecha de Cierre",
                    value=datetime.now().date()
                )
                evidencia_cierre = st.file_uploader(
                    "Evidencia de Cierre (foto)",
                    type=['jpg', 'png']
                )
            else:
                fecha_cierre = None
                evidencia_cierre = None

            actualizar = st.form_submit_button("💾 Actualizar Hallazgo", type="primary")

        if actualizar:
            actualizar_hallazgo(
                hallazgo_editar,
                nuevo_estado,
                comentarios,
                fecha_cierre,
                evidencia_cierre
            )
            st.success("✅ Hallazgo actualizado exitosamente!")
            st.rerun()

def actualizar_hallazgo(hallazgo_id, estado, comentarios, fecha_cierre, evidencia):
    """Actualizar estado y datos de hallazgo"""
    supabase = get_supabase_client()
    
    try:
        update_data = {
            'estado': estado,
            'comentarios': comentarios,
            'fecha_cierre': fecha_cierre.isoformat() if fecha_cierre else None
        }
        
        # Subir evidencia de cierre
        if evidencia:
            evidencia_url = subir_evidencia_hallazgo(evidencia, hallazgo_id)
            update_data['evidencia_cierre'] = [evidencia_url]
        
        supabase.table('hallazgos').update(update_data).eq('id', hallazgo_id).execute()
        
        # Notificar cierre
        if estado == 'cerrado':
            requests.post(
                st.secrets["N8N_WEBHOOK_URL"] + "/hallazgo-cerrado",
                json={"hallazgo_id": hallazgo_id}
            )
    
    except Exception as e:
        st.error(f"Error actualizando hallazgo: {e}")

