"""Contenido comercial verificable; nunca publica el teléfono interno como demo."""
import re
from urllib.parse import quote

from .. import config

CAL_BOOKING_URL = "https://cal.com/bynoesis/agenda-una-llamada-con-nosotros"
PUBLIC_EVENTS = frozenset({
    "hero_whatsapp_cta", "hero_demo_started", "hero_demo_completed",
    "autonomos_cta", "gestorias_cta", "cal_demo_started", "cal_demo_booked",
    "pricing_click", "contact_whatsapp", "final_cta",
})
PUBLIC_EVENT_PAGES = frozenset({"/", "/autonomos", "/gestorias", "/contacto", "/precios"})
FAQS = [
    ("¿Qué es Bynoesis?", "Bynoesis es un asistente de gestión para autónomos y pequeños negocios de servicios. Puedes preparar facturas y presupuestos, registrar gastos y consultar clientes, agenda y cobros desde WhatsApp, con una web para revisar el detalle."),
    ("¿Puedo hacer facturas desde WhatsApp?", "Sí. Indicas el cliente, el concepto y el importe. Bynoesis prepara un borrador con los datos de tu negocio. Revisas el resultado y confirmas antes de emitir o enviar. Si la referencia del cliente no es clara, hay que aclararla."),
    ("¿Bynoesis sustituye a mi gestoría?", "No. Tu gestoría conserva el criterio fiscal. Si la conectas, puede revisar la documentación por empresa y período, pedir lo que falta y consultar borradores fiscales. Bynoesis no presenta impuestos por ti."),
    ("¿Para qué autónomos está pensado?", "Para profesionales de servicios como instaladores, electricistas, fontaneros, mantenimiento, reformas, limpieza y jardinería. No necesitas un equipo: puedes empezar trabajando por tu cuenta."),
    ("¿Cómo funciona Bynoesis con Veri*Factu?", "El código incluye registros de facturación, huellas encadenadas y QR tributario. La conexión con la AEAT requiere configuración y validación antes de su uso real. No anunciamos una certificación de la AEAT ni una garantía fiscal universal."),
    ("¿Bynoesis pertenece a WhatsApp o Meta?", "No. Bynoesis es un producto independiente que utiliza WhatsApp como canal de gestión. WhatsApp es una marca de sus respectivos titulares."),
]


def question_groups(*, voice_available: bool, ocr_available: bool,
                    signup_available: bool) -> list[dict]:
    """Preguntas de /preguntas agrupadas por tema.

    Las respuestas que dependen de una capacidad se eligen aquí y no en la
    plantilla: así la página y el JSON-LD que leen buscadores y asistentes de IA
    dicen exactamente lo mismo, y ninguno promete audio o lectura sin tenerlos.
    """
    after_trial = (
        "Si no eliges plan, sigues entrando a consultar y descargar todo lo tuyo; lo que se queda esperando es crear, enviar y automatizar. No desaparece nada ni se te cobra automáticamente."
        if signup_available else
        "La prueba pública todavía no está abierta. Durante el piloto acordamos contigo el acceso y nunca hacemos un cobro sin que elijas antes un plan."
    )
    voice = (
        "Sí. Bynoesis puede transcribir una instrucción, identificar los datos relevantes y preparar el siguiente paso para que lo revises."
        if voice_available else
        "La función está preparada y se habilita durante la puesta en marcha. Si no está activa, Bynoesis conserva el audio y te pide el dato por escrito sin inventarlo."
    )
    ocr = (
        "Puede detectar y extraer documentos. Si el tipo o algún dato no está claro, lo deja pendiente y te pregunta antes de clasificarlo definitivamente."
        if ocr_available else
        "Guarda y ordena el documento. La lectura automática se habilita durante la puesta en marcha; mientras tanto, te pide confirmar los datos antes de registrarlos."
    )
    return [
        {"id": "empezar", "label": "Empezar", "title": "La prueba y el día a día", "questions": [
            ("¿Necesito instalar una aplicación?", "No. El panel funciona en el navegador y se puede guardar como acceso directo. WhatsApp usa la integración oficial de Meta cuando está conectada."),
            ("¿Tengo que cambiar mi forma de trabajar?", "No. Puedes empezar enviando mensajes y documentos como ya haces. Durante la puesta en marcha activamos también audio y lectura de imágenes si tu plan los necesita."),
            ("¿Qué pasa después de los 14 días?", after_trial),
        ]},
        {"id": "whatsapp", "label": "WhatsApp y Bynoesis", "title": "Hablar, entender y actuar", "questions": [
            ("¿Puedo hablarle con notas de voz?", voice),
            ("¿Entiende fotografías de tickets y facturas?", ocr),
            ("¿Bynoesis envía o paga sin preguntarme?", "No. Preparar no es autorizar. Enviar facturas, reclamar cobros, mover citas o cualquier acción irreversible requiere el nivel de permiso definido y, en los casos sensibles, tu confirmación."),
        ]},
        {"id": "legalidad", "label": "Facturación y legalidad", "title": "Trabajar en regla", "questions": [
            ("¿Puedo emitir facturas correctas antes de activar Veri*Factu?", "Sí, para los casos actualmente soportados: factura completa o simplificada, series correlativas, fecha, emisor, destinatario cuando corresponde, conceptos, IVA, IRPF y total. Bynoesis bloquea la emisión si faltan datos obligatorios. Operaciones exentas, no sujetas o internacionales requieren todavía revisión específica con la gestoría."),
            ("¿Está adaptado a Veri*Factu?", "El registro, la huella, el QR, la cola y la conexión técnica están preparados, pero no se activan como servicio definitivo sin certificado y pruebas con la AEAT. Según el calendario vigente, la adaptación es obligatoria desde el 1 de enero de 2027 para sociedades y desde el 1 de julio de 2027 para el resto de empresas y autónomos."),
            ("¿Calcula IVA e IRPF?", "Sí, aplicando las reglas configuradas en cada documento. Bynoesis no presenta una estimación fiscal como definitiva: tu gestoría valida la presentación."),
            ("¿Sustituye a mi gestoría?", "No. Ordena y prepara el trabajo administrativo. La gestoría mantiene el criterio profesional en las decisiones fiscales delicadas."),
        ]},
        {"id": "datos", "label": "Datos y seguridad", "title": "Tu negocio sigue siendo tuyo", "questions": [
            ("¿Puedo llevarme mis datos?", "Sí. Puedes exportar la cuenta y descargar los principales registros y documentos."),
            ("¿Mis datos están separados de otros negocios?", "Sí. Cada lectura y escritura se limita al negocio correspondiente, con controles de sesión y aislamiento por identificador de negocio."),
            ("¿Toda la información sale a una IA externa?", "No. Lo rutinario se intenta resolver dentro de Bynoesis. La IA externa se reserva para tareas avanzadas y se puede desactivar desde Ajustes."),
        ]},
        {"id": "equipo-faq", "label": "Equipo y gestoría", "title": "Que cada persona vea solo lo que necesita", "questions": [
            ("¿Cada trabajador tiene su propio panel?", "Sí. Puede recibir trabajos asignados, consultar su planificación y fichar sin acceder a la información privada del titular."),
            ("¿La gestoría puede ver los documentos ordenados?", "Sí. El portal de gestoría organiza ingresos, gastos y documentos por períodos, con intercambio bidireccional y trazabilidad."),
            ("¿Qué ve mi cliente?", "Un portal privado para consultar y aceptar presupuestos o descargar facturas mediante un enlace compartido por el negocio."),
        ]},
    ]


def marketing_context(page: str, *, signup_available: bool | None = None,
                      voice_available: bool = False, ocr_available: bool = False) -> dict:
    phone = config.PUBLIC_WHATSAPP_DEMO_PHONE
    available = bool(re.fullmatch(r"[1-9][0-9]{7,14}", phone))
    signup = config.public_signup_available() if signup_available is None else signup_available
    href = (f"https://wa.me/{phone}?text={quote('Hola, quiero probar Bynoesis para mi negocio.')}"
            if available else "/onboarding?intent=trial" if signup else "/solicitar-acceso")
    label = ("Probar Bynoesis por WhatsApp" if available else
             "Probar Bynoesis 14 días" if signup else "Solicitar una prueba")
    groups = question_groups(
        voice_available=voice_available, ocr_available=ocr_available, signup_available=signup,
    ) if page == "preguntas" else []
    if page in {"inicio", "autonomos", "gestorias"}:
        faq_items = FAQS
    else:
        faq_items = [item for group in groups for item in group["questions"]]
    graph = [{"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in faq_items
    ]}] if faq_items else []
    names = {"autonomos": "Autónomos", "gestorias": "Gestorías", "contacto": "Contacto",
             "preguntas": "Preguntas"}
    if page in names:
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": config.BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": names[page], "item": config.BASE_URL + "/" + page},
        ]})
    return {
        "marketing_cta_href": href, "marketing_cta_label": label,
        "public_whatsapp_demo": available, "cal_booking_url": CAL_BOOKING_URL,
        "marketing_faqs": FAQS, "question_groups": groups,
        "marketing_schema": {"@context": "https://schema.org", "@graph": graph},
    }
