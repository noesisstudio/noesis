"""Páginas del sitio dedicadas a un oficio concreto.

Existen por dos motivos que van juntos. Quien busca «programa para fontaneros» no
se reconoce en una portada que habla de «negocios de servicios», y una página que
le nombra convierte mucho mejor. Y en buscadores compiten en frases largas, donde
todavía hay sitio, en vez de pelear por las genéricas que dominan los grandes.

La condición para que funcione es que cada página diga algo distinto de verdad. Un
mismo texto con la palabra del oficio cambiada es lo que Google llama página
puente, y penaliza: hace más daño que no tenerla. Por eso lo que cambia aquí no es
el nombre, sino el problema —urgencias, certificados, obra larga, mantenimientos,
avisos sueltos— porque cada oficio factura de una manera.
"""

from __future__ import annotations

OFICIOS: dict[str, dict] = {
    "fontaneros": {
        "nombre": "fontaneros",
        "titulo": "Noesis para fontaneros",
        "h1": "La urgencia te rompe el día. El papeleo no debería rematarlo.",
        "descripcion": (
            "Noesis ordena avisos, material y facturas de un fontanero autónomo "
            "desde WhatsApp: cierra el aviso donde lo terminas, sin volver a casa "
            "a pasarlo a limpio."
        ),
        "entradilla": (
            "Un aviso de urgencia se cuela entre dos trabajos cerrados y toda la "
            "agenda se recoloca. Noesis toma nota mientras tanto para que el día no "
            "acabe con una libreta que hay que descifrar por la noche."
        ),
        "situaciones": [
            {
                "titulo": "El aviso que entra a media mañana",
                "texto": (
                    "Sales para una fuga y las dos visitas de la tarde se mueven. "
                    "Le dices a Noesis lo que ha pasado y queda el trabajo abierto "
                    "con su cliente, su dirección y lo que has hecho, sin parar a "
                    "escribirlo en ningún sitio."
                ),
            },
            {
                "titulo": "El material que compras por el camino",
                "texto": (
                    "Un latiguillo, dos llaves de paso y un termo. Se compran a "
                    "media faena y acaban en un ticket arrugado en la furgoneta. "
                    "Enviado a Noesis, el gasto queda pegado al trabajo del cliente "
                    "que lo va a pagar, no en un montón suelto de fin de mes."
                ),
            },
            {
                "titulo": "El trabajo que se cierra y no se factura",
                "texto": (
                    "El más caro de todos. Arreglas, cobras de palabra, y la factura "
                    "se queda para «cuando tenga un rato». Noesis mantiene a la vista "
                    "lo terminado y sin cobrar, para que ese rato no llegue en marzo."
                ),
            },
        ],
        "mensaje": "avería en Girona 12, cambio de termo, 240 más IVA",
        "mensaje_resultado": (
            "Queda el trabajo registrado con su cliente y el importe, y la factura "
            "preparada para que solo tengas que confirmarla."
        ),
        "detalle_titulo": "Los desplazamientos y las horas raras",
        "detalle_texto": (
            "Salir un sábado a las once de la noche cuesta dinero, y es justo lo que "
            "más se olvida de cobrar. Si lo dices al pasar —«desplazamiento fuera de "
            "horario»— queda como concepto en la factura, no en tu memoria."
        ),
    },
    "electricistas": {
        "nombre": "electricistas",
        "titulo": "Noesis para electricistas",
        "h1": "Obra nueva y averías el mismo día, sin mezclar los papeles.",
        "descripcion": (
            "Noesis ordena instalaciones, certificados, material y facturas de un "
            "electricista autónomo desde WhatsApp, con cada documento pegado a su "
            "instalación."
        ),
        "entradilla": (
            "Por la mañana una instalación que dura tres semanas; por la tarde, tres "
            "averías de media hora. Son dos formas de facturar distintas y acaban en "
            "la misma libreta. Noesis las separa por ti."
        ),
        "situaciones": [
            {
                "titulo": "El certificado que aparece cuando ya no está",
                "texto": (
                    "El boletín, el certificado de instalación, el plano que te pasó "
                    "el cliente. Documentos que se necesitan meses después, cuando ya "
                    "nadie recuerda en qué conversación estaban. Enviados a Noesis, "
                    "quedan guardados en la instalación a la que pertenecen."
                ),
            },
            {
                "titulo": "El material repartido entre cuatro obras",
                "texto": (
                    "Un pedido grande al almacén que se reparte entre varias obras a "
                    "ojo. Si dices a qué trabajo va cada cosa cuando la usas, al "
                    "acabar sabes lo que te ha costado esa obra de verdad, no lo que "
                    "creías que iba a costar."
                ),
            },
            {
                "titulo": "Las averías pequeñas que se acumulan",
                "texto": (
                    "Cambiar un diferencial son cuarenta minutos y ochenta euros. "
                    "Solas no parecen nada; veinte al mes son un sueldo. Noesis las "
                    "registra una a una para que ninguna se quede sin facturar."
                ),
            },
        ],
        "mensaje": "boletín de la reforma de Marta, mano de obra 180 y material 95",
        "mensaje_resultado": (
            "El importe queda separado entre mano de obra y material, que es como lo "
            "necesita tu gestoría y como lo entiende tu cliente."
        ),
        "detalle_titulo": "Lo que hay que poder enseñar años después",
        "detalle_texto": (
            "Una instalación se revisa, se amplía o se discute mucho tiempo después "
            "de cobrarla. Tener el certificado, las fotos y el presupuesto original "
            "en el mismo sitio deja de ser orden y pasa a ser tu respaldo."
        ),
    },
    "reformas": {
        "nombre": "empresas de reformas",
        "titulo": "Noesis para empresas de reformas",
        "h1": "Saber si la obra gana dinero antes de terminarla.",
        "descripcion": (
            "Noesis ordena presupuestos por partidas, costes y certificaciones de una "
            "empresa de reformas desde WhatsApp, con el margen real de cada obra a la "
            "vista mientras avanza."
        ),
        "entradilla": (
            "Una reforma dura meses, pasa por cinco gremios y se cobra a plazos. "
            "Cuando sale mal, casi nunca es por el precio: es porque nadie llevaba la "
            "cuenta mientras se hacía."
        ),
        "situaciones": [
            {
                "titulo": "El presupuesto que ya no se parece a la obra",
                "texto": (
                    "Se presupuesta un baño y acaban siendo un baño, dos ventanas y "
                    "una instalación nueva. Cada cambio se acuerda de palabra y "
                    "ninguno llega al papel. Noesis los va anotando según ocurren, "
                    "para que el precio final tenga de dónde salir."
                ),
            },
            {
                "titulo": "El coste que solo se sabe al final",
                "texto": (
                    "Materiales, subcontratas y jornadas se pagan durante meses y no "
                    "se suman hasta que la obra está cerrada. Para entonces, si el "
                    "margen se ha comido, ya no hay nada que hacer. Verlo a mitad sí "
                    "deja margen para reaccionar."
                ),
            },
            {
                "titulo": "Las certificaciones parciales",
                "texto": (
                    "Cobrar por avance obliga a justificar cuánto se ha hecho. Con el "
                    "presupuesto por partidas registrado, la certificación sale de lo "
                    "ya ejecutado en lugar de calcularse a ojo cada vez."
                ),
            },
        ],
        "mensaje": "certificación de la obra de Sant Cugat, 40 por ciento",
        "mensaje_resultado": (
            "Sale la factura por el avance sobre el presupuesto aprobado, y lo "
            "pendiente queda contado para la siguiente."
        ),
        "detalle_titulo": "Los gremios que trabajan contigo",
        "detalle_texto": (
            "El fontanero, el electricista y el pintor facturan a la empresa y esa "
            "factura es un coste de esa obra concreta. Registrada así, el margen que "
            "ves es el que hay, no el que sale de restar solo el material."
        ),
    },
    "climatizacion": {
        "nombre": "instaladores de climatización",
        "titulo": "Noesis para instaladores de climatización",
        "h1": "El mantenimiento del año que viene no debería depender de tu memoria.",
        "descripcion": (
            "Noesis ordena instalaciones, revisiones periódicas y facturas de un "
            "instalador de climatización desde WhatsApp, y no deja que se pasen los "
            "mantenimientos contratados."
        ),
        "entradilla": (
            "En este oficio el dinero previsible no está en instalar, está en "
            "mantener. Y un mantenimiento anual solo se cobra si alguien se acuerda "
            "de que tocaba."
        ),
        "situaciones": [
            {
                "titulo": "La revisión que tocaba en junio",
                "texto": (
                    "Se firma el mantenimiento con la instalación y se cumple el "
                    "primer año. El segundo, con la campaña de calor encima, se pasa. "
                    "Noesis mantiene la revisión como trabajo previsto, para que salga "
                    "en su fecha sin que tengas que llevarlo tú."
                ),
            },
            {
                "titulo": "Dos temporadas que se comen el año",
                "texto": (
                    "El calor y el frío concentran el trabajo en pocas semanas, y es "
                    "justo cuando no hay tiempo de facturar nada. Si el aviso queda "
                    "registrado al terminarlo, la temporada no acaba con veinte "
                    "trabajos pendientes de pasar a limpio."
                ),
            },
            {
                "titulo": "El parque de máquinas de cada cliente",
                "texto": (
                    "Un hotel con catorce equipos no es un cliente, son catorce "
                    "historiales. Saber qué se cambió y cuándo evita discutir si una "
                    "avería entra en garantía o se factura aparte."
                ),
            },
        ],
        "mensaje": "revisión anual del hotel Marina, la de todos los junios",
        "mensaje_resultado": (
            "Queda registrada la visita y anotada la siguiente, para que el contrato "
            "se cumpla sin depender de que alguien lo recuerde."
        ),
        "detalle_titulo": "Los contratos de mantenimiento",
        "detalle_texto": (
            "Un mantenimiento anual es ingreso que se repite: lo que da estabilidad "
            "cuando la instalación no entra. Tenerlos todos contados, con su fecha y "
            "su importe, cambia la conversación con el banco y con la gestoría."
        ),
    },
    "cerrajeros": {
        "nombre": "cerrajeros",
        "titulo": "Noesis para cerrajeros",
        "h1": "Muchos trabajos pequeños suman un negocio. Si se registran.",
        "descripcion": (
            "Noesis ordena avisos, cobros y facturas simplificadas de un cerrajero "
            "autónomo desde WhatsApp, sin tener que sentarse a pasar el día a limpio."
        ),
        "entradilla": (
            "Aquí no hay obras de meses: hay veinte intervenciones en una semana, "
            "muchas a horas imposibles y casi todas cobradas en el momento. El riesgo "
            "no es cobrar poco, es no dejar rastro de lo cobrado."
        ),
        "situaciones": [
            {
                "titulo": "La apertura de madrugada",
                "texto": (
                    "Sales a las tres, abres, cobras noventa euros y te vuelves a la "
                    "cama. Al día siguiente no queda ni el nombre del cliente. Un "
                    "mensaje al terminar deja el trabajo registrado antes de que se "
                    "olvide."
                ),
            },
            {
                "titulo": "El efectivo que no cuadra",
                "texto": (
                    "Cobrar en mano es rápido y es exactamente lo que se pierde. Si "
                    "cada cobro queda anotado según ocurre, a fin de mes la caja "
                    "cuadra sola y la gestoría no tiene que preguntarte de dónde sale "
                    "cada apunte."
                ),
            },
            {
                "titulo": "La factura que el cliente pide después",
                "texto": (
                    "Un particular te llama tres semanas más tarde porque el seguro "
                    "se la reclama. Con el trabajo registrado, la factura sale en un "
                    "momento en lugar de reconstruir de memoria qué hiciste y por "
                    "cuánto."
                ),
            },
        ],
        "mensaje": "apertura en Ronda Sant Pere, 90 euros, cobrado",
        "mensaje_resultado": (
            "Queda el trabajo cerrado, el cobro anotado y la factura lista para "
            "emitir cuando la pidan."
        ),
        "detalle_titulo": "Facturas simplificadas, que son la mayoría",
        "detalle_texto": (
            "En los importes pequeños a particulares suele bastar la factura "
            "simplificada. Noesis emite la que corresponde en cada caso y avisa "
            "cuando faltan datos obligatorios, en vez de dejarte descubrirlo cuando "
            "ya la has entregado."
        ),
    },
}


def listado() -> list[tuple[str, dict]]:
    """Los oficios en orden estable, para enlazarlos entre sí y en el sitemap."""
    return list(OFICIOS.items())
