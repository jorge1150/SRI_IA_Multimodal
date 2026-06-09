"""
relation_extractor.py — Extracción de relaciones entre entidades tributarias.

Estrategia: patrones léxico-verbales sobre oraciones.
Para cada oración del documento:
  1. Detecta entidades con EntityExtractor.
  2. Identifica el verbo/predicado dominante.
  3. Clasifica la relación según el verbo.
  4. Emite triples (fuente, relación, destino, evidencia).
"""

import re
import unicodedata
from typing import NamedTuple

from .entity_extractor import EntityExtractor, Entity


class Triple(NamedTuple):
    source: str          # nombre canónico de la entidad fuente
    source_type: str
    relation: str        # tipo de relación
    target: str          # nombre canónico de la entidad destino
    target_type: str
    evidence: str        # fragmento de texto que soporta la relación
    document: str        # nombre del documento origen
    weight: float        # confianza (0-1)


# ── Clases de verbos → tipo de relación ──────────────────────────────────────

_VERB_CLASSES: list[tuple[str, list[str]]] = [
    ("debe_presentar", [
        "debe declarar", "deben declarar", "deberá declarar", "deberán declarar",
        "debe presentar", "deben presentar", "deberá presentar",
        "está obligado a declarar", "están obligados a declarar",
        "tiene la obligación de declarar", "tienen la obligación de declarar",
        "debe pagar", "deben pagar", "deberá pagar", "deberán pagar",
        "está obligado a pagar", "están obligados a pagar",
    ]),
    ("debe_retener", [
        "debe retener", "deben retener", "deberá retener", "deberán retener",
        "está obligado a retener", "actúa como agente de retención",
        "efectuará la retención",
    ]),
    ("puede_deducir", [
        "puede deducir", "pueden deducir", "podrá deducir", "podrán deducir",
        "tiene derecho a deducir", "son deducibles", "es deducible",
        "se puede deducir", "se pueden deducir",
    ]),
    ("esta_exento", [
        "está exento", "están exentos", "estará exento", "no está sujeto",
        "no están sujetos", "se encuentra exento", "se encuentran exentos",
        "no causa", "no causan", "no grava", "exonerado",
    ]),
    ("aplica_tarifa", [
        "aplica una tarifa", "se aplica la tarifa", "tarifa del", "tarifa de",
        "tasa del", "alícuota del", "alicuota del",
        "grava con", "grava al",
    ]),
    ("debe_inscribirse", [
        "debe inscribirse", "deben inscribirse", "deberá inscribirse",
        "obligados a obtener el ruc", "deben obtener el ruc",
        "requiere ruc", "requieren ruc",
    ]),
    ("establece", [
        "establece", "establece que", "dispone", "determina", "fija",
        "regula", "señala", "indica", "estipula", "prevé",
    ]),
    ("declara_en", [
        "se declara en", "se declara mediante", "corresponde al formulario",
        "se presenta en", "se llena en", "declarar en el formulario",
    ]),
    ("genera_obligacion", [
        "genera la obligación", "genera obligación", "origina la obligación",
        "da lugar a la obligación",
    ]),
    ("tiene_plazo", [
        "tiene plazo", "tienen plazo", "debe presentarse hasta",
        "vence el", "plazo de presentación",
    ]),
    ("puede_acogerse", [
        "puede acogerse", "pueden acogerse", "podrá acogerse",
        "tiene derecho a acogerse", "puede inscribirse en",
    ]),
    ("relacionado_con", []),  # relación genérica cuando co-ocurren
]

# Normalizador
def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Pre-compilar patrones de verbos
_VERB_PATTERNS: list[tuple[str, re.Pattern]] = []
for _rel_type, _verb_list in _VERB_CLASSES:
    for _verb in _verb_list:
        _pat = re.compile(re.escape(_norm(_verb)))
        _VERB_PATTERNS.append((_rel_type, _pat))


_SENT_SPLIT = re.compile(r'(?<=[.;])\s+')


class RelationExtractor:
    """
    Extrae triples (sujeto, relación, objeto) de texto normativo tributario.
    Trabaja a nivel de oración — divide el texto en oraciones y analiza cada una.
    """

    def __init__(self):
        self._entity_extractor = EntityExtractor()

    def extract(self, text: str, document_name: str = "") -> list[Triple]:
        """
        Extrae todos los triples del texto dado.
        document_name: nombre del documento fuente (para trazabilidad).
        """
        sentences = _SENT_SPLIT.split(text.strip())
        triples: list[Triple] = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue
            triples.extend(self._extract_from_sentence(sentence, document_name))

        return triples

    def _extract_from_sentence(self, sentence: str, document_name: str) -> list[Triple]:
        entities = self._entity_extractor.extract(sentence)
        if len(entities) < 2:
            return []

        norm_sent = _norm(sentence)
        relation_type = self._detect_relation(norm_sent)
        triples: list[Triple] = []

        # Primer sujeto antes del verbo → fuente
        # Resto de entidades → destinos
        source = entities[0]
        for target in entities[1:]:
            if source.name == target.name:
                continue
            triples.append(Triple(
                source=source.name,
                source_type=source.entity_type,
                relation=relation_type,
                target=target.name,
                target_type=target.entity_type,
                evidence=sentence[:200],
                document=document_name,
                weight=self._confidence(relation_type),
            ))

        return triples

    def _detect_relation(self, norm_sentence: str) -> str:
        """Retorna el tipo de relación más probable según los verbos presentes."""
        for rel_type, pat in _VERB_PATTERNS:
            if pat.search(norm_sentence):
                return rel_type
        return "relacionado_con"

    @staticmethod
    def _confidence(relation_type: str) -> float:
        """Mayor confianza para relaciones detectadas con verbos específicos."""
        if relation_type == "relacionado_con":
            return 0.4
        return 0.75
