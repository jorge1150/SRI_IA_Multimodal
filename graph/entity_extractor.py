"""
entity_extractor.py — Extracción de entidades tributarias del SRI Ecuador.

Estrategia: taxonomía basada en reglas (sin spaCy).
Las entidades son términos fijos del dominio tributario ecuatoriano.
Cada entidad tiene un nombre canónico, tipo y lista de alias.
"""

import re
import unicodedata
from typing import NamedTuple


class Entity(NamedTuple):
    name: str        # nombre canónico
    entity_type: str # tipo de entidad
    alias_matched: str
    start: int       # posición en el texto (carácter)
    end: int


# ── Taxonomía de entidades SRI Ecuador ───────────────────────────────────────
# Formato: (nombre_canónico, tipo, [alias_en_minúsculas_normalizados])

_TAXONOMY: list[tuple[str, str, list[str]]] = [

    # ── Impuestos y tributos
    ("IVA",
     "impuesto",
     ["iva", "impuesto al valor agregado", "impuesto al valor anadido"]),

    ("impuesto a la renta",
     "impuesto",
     ["impuesto a la renta", "ir ", "impuesto sobre la renta",
      "impuesto a los ingresos"]),

    ("ICE",
     "impuesto",
     ["ice", "impuesto a los consumos especiales"]),

    ("RISE",
     "regimen",
     ["rise", "regimen impositivo simplificado ecuatoriano",
      "regimen simplificado"]),

    ("retención",
     "impuesto",
     ["retencion", "retenciones", "retencion en la fuente",
      "retenciones en la fuente"]),

    ("anticipo de impuesto a la renta",
     "concepto",
     ["anticipo de impuesto a la renta", "anticipo del ir",
      "anticipo de ir", "anticipo impuesto"]),

    # ── Sujetos tributarios
    ("contribuyente",
     "sujeto",
     ["contribuyente", "contribuyentes"]),

    ("persona natural",
     "sujeto",
     ["persona natural", "personas naturales"]),

    ("persona jurídica",
     "sujeto",
     ["persona juridica", "personas juridicas", "entidad juridica"]),

    ("sociedad",
     "sujeto",
     ["sociedad", "sociedades", "empresa", "empresas",
      "compania", "companias", "corporacion"]),

    ("empleador",
     "sujeto",
     ["empleador", "empleadores"]),

    ("agente de retención",
     "sujeto",
     ["agente de retencion", "agentes de retencion",
      "agente retenedor", "agentes retenedores"]),

    ("sujeto pasivo",
     "sujeto",
     ["sujeto pasivo", "sujetos pasivos"]),

    # ── Registros y regímenes
    ("RUC",
     "registro",
     ["ruc", "registro unico de contribuyentes",
      "numero de ruc"]),

    # ── Obligaciones y trámites
    ("declaración",
     "obligacion",
     ["declaracion", "declaraciones", "formulario de declaracion"]),

    ("declaración de IVA",
     "obligacion",
     ["declaracion de iva", "declaracion del iva",
      "declaracion mensual de iva"]),

    ("declaración de impuesto a la renta",
     "obligacion",
     ["declaracion de impuesto a la renta",
      "declaracion anual de impuesto a la renta",
      "declaracion del ir"]),

    ("pago de impuestos",
     "obligacion",
     ["pago de impuesto", "pago de impuestos", "pago tributario"]),

    ("comprobante electrónico",
     "obligacion",
     ["comprobante electronico", "comprobantes electronicos",
      "factura electronica", "facturas electronicas",
      "nota de credito electronica", "nota de debito electronica",
      "guia de remision"]),

    ("obligación tributaria",
     "obligacion",
     ["obligacion tributaria", "obligaciones tributarias"]),

    # ── Formularios SRI
    ("formulario 104",
     "formulario",
     ["formulario 104", "form 104", "104"]),

    ("formulario 101",
     "formulario",
     ["formulario 101", "form 101", "101"]),

    ("formulario 103",
     "formulario",
     ["formulario 103", "form 103", "103"]),

    # ── Leyes y reglamentos
    ("LORTI",
     "ley",
     ["lorti", "ley organica de regimen tributario interno",
      "ley de regimen tributario"]),

    ("Código Tributario",
     "ley",
     ["codigo tributario"]),

    ("Reglamento LORTI",
     "ley",
     ["reglamento de aplicacion de la lorti",
      "reglamento de aplicacion", "reglamento lorti"]),

    ("resolución del SRI",
     "ley",
     ["resolucion del sri", "resolucion nac",
      "resoluciones nac", "nac-dgercgc"]),

    # ── Conceptos tributarios
    ("exención",
     "concepto",
     ["exencion", "exento", "exenta", "exentos", "exentas",
      "no sujeto", "exoneracion"]),

    ("deducción",
     "concepto",
     ["deduccion", "deducciones", "gasto deducible",
      "gastos deducibles", "deducible"]),

    ("crédito tributario",
     "concepto",
     ["credito tributario", "creditos tributarios"]),

    ("base imponible",
     "concepto",
     ["base imponible", "base gravable"]),

    ("tarifa",
     "concepto",
     ["tarifa", "alicuota", "tasa del impuesto", "porcentaje"]),

    ("multa",
     "concepto",
     ["multa", "multas", "sancion", "sanciones", "penalidad"]),

    ("mora",
     "concepto",
     ["mora", "intereses por mora", "recargo", "intereses moratorios"]),

    ("deuda tributaria",
     "concepto",
     ["deuda tributaria", "deudas tributarias", "adeudo tributario"]),

    # ── Períodos
    ("período fiscal",
     "periodo",
     ["periodo fiscal", "ejercicio fiscal", "ejercicio economico",
      "ejercicio impositivo", "periodo impositivo"]),

    # ── Entidades reguladoras
    ("SRI",
     "entidad",
     ["sri", "servicio de rentas internas"]),
]


def _normalize(text: str) -> str:
    """Minúsculas + eliminar tildes para matching robusto."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Pre-compilar patrones con los alias (orden: más largo primero)
_COMPILED: list[tuple[str, str, str, re.Pattern]] = []

for _canon, _etype, _aliases in _TAXONOMY:
    _aliases_sorted = sorted(_aliases, key=len, reverse=True)
    for _alias in _aliases_sorted:
        _norm_alias = _normalize(_alias)
        _pat = re.compile(
            r'(?<![a-z\d])' + re.escape(_norm_alias) + r'(?![a-z\d])',
            re.IGNORECASE
        )
        _COMPILED.append((_canon, _etype, _alias, _pat))


class EntityExtractor:
    """
    Detecta entidades tributarias del SRI en texto libre.
    Usa un diccionario de términos (taxonomía) sin modelos NLP.
    """

    def extract(self, text: str) -> list[Entity]:
        """
        Retorna lista de Entity ordenadas por posición de aparición.
        Elimina solapamientos (el match más largo tiene prioridad).
        """
        norm_text = _normalize(text)
        raw_matches: list[tuple[int, int, str, str]] = []  # (start, end, canon, etype)

        for canon, etype, _alias, pat in _COMPILED:
            for m in pat.finditer(norm_text):
                raw_matches.append((m.start(), m.end(), canon, etype))

        # Desambiguar solapamientos: conservar el match más largo
        raw_matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        entities: list[Entity] = []
        last_end = -1
        for start, end, canon, etype in raw_matches:
            if start >= last_end:
                alias_matched = text[start:end] if end <= len(text) else ""
                entities.append(Entity(
                    name=canon, entity_type=etype,
                    alias_matched=alias_matched, start=start, end=end,
                ))
                last_end = end

        return entities

    def extract_unique(self, text: str) -> list[dict]:
        """
        Retorna entidades únicas (por nombre canónico) con count de ocurrencias.
        Formato: [{"name": ..., "type": ..., "count": ...}]
        """
        from collections import Counter
        entities = self.extract(text)
        counts: Counter = Counter(e.name for e in entities)
        type_map = {e.name: e.entity_type for e in entities}

        return [
            {"name": name, "type": type_map[name], "count": count}
            for name, count in counts.most_common()
        ]
