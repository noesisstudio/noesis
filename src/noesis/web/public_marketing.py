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
    ("¿Qué es Noesis?", "Noesis es un asistente de gestión para autónomos y pequeños negocios de servicios. Puedes preparar facturas y presupuestos, registrar gastos y consultar clientes, agenda y cobros desde WhatsApp, con una web para revisar el detalle."),
    ("¿Puedo hacer facturas desde WhatsApp?", "Sí. Indicas el cliente, el concepto y el importe. Noesis prepara un borrador con los datos de tu negocio. Revisas el resultado y confirmas antes de emitir o enviar. Si la referencia del cliente no es clara, hay que aclararla."),
    ("¿Noesis sustituye a mi gestoría?", "No. Tu gestoría conserva el criterio fiscal. Si la conectas, puede revisar la documentación por empresa y período, pedir lo que falta y consultar borradores fiscales. Noesis no presenta impuestos por ti."),
    ("¿Para qué autónomos está pensado?", "Para profesionales de servicios como instaladores, electricistas, fontaneros, mantenimiento, reformas, limpieza y jardinería. No necesitas un equipo: puedes empezar trabajando por tu cuenta."),
    ("¿Cómo funciona Noesis con VeriFactu?", "El código incluye registros de facturación, huellas encadenadas y QR tributario. La conexión con la AEAT requiere configuración y validación antes de su uso real. No anunciamos una certificación de la AEAT ni una garantía fiscal universal."),
    ("¿Noesis pertenece a WhatsApp o Meta?", "No. Noesis es un producto independiente que utiliza WhatsApp como canal de gestión. WhatsApp es una marca de sus respectivos titulares."),
]


def marketing_context(page: str, *, signup_available: bool | None = None) -> dict:
    phone = config.PUBLIC_WHATSAPP_DEMO_PHONE
    available = bool(re.fullmatch(r"[1-9][0-9]{7,14}", phone))
    signup = config.public_signup_available() if signup_available is None else signup_available
    href = (f"https://wa.me/{phone}?text={quote('Hola, quiero probar Noesis para mi negocio.')}"
            if available else "/onboarding?intent=trial" if signup else "/solicitar-acceso")
    label = ("Probar Noesis por WhatsApp" if available else
             "Probar Noesis 14 días" if signup else "Solicitar una prueba")
    graph = [{"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in FAQS
    ]}] if page in {"inicio", "autonomos", "gestorias"} else []
    names = {"autonomos": "Autónomos", "gestorias": "Gestorías", "contacto": "Contacto"}
    if page in names:
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": config.BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": names[page], "item": config.BASE_URL + "/" + page},
        ]})
    return {
        "marketing_cta_href": href, "marketing_cta_label": label,
        "public_whatsapp_demo": available, "cal_booking_url": CAL_BOOKING_URL,
        "marketing_faqs": FAQS,
        "marketing_schema": {"@context": "https://schema.org", "@graph": graph},
    }
