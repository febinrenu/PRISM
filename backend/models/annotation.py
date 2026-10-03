"""
Human annotation of one evaluation item (guideline v1).

Spans are character offsets into the item's frozen text (eval/v2 manifest);
scoring adds the item's start offset to compare with system spans in the
statute's canonical text. Effects use the same typed schema as extraction
(models.rules.Effect), with the source span as offsets as well.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from models.rules import Modality

GUIDELINE_VERSION = 1


class AnnSpan(BaseModel):
    start: int
    end: int

    @model_validator(mode="after")
    def _ordered(self):
        if self.start < 0 or self.end <= self.start:
            raise ValueError("span end must be after start")
        return self


class AnnCondition(AnnSpan):
    negated: bool = False


class AnnEffect(BaseModel):
    kind: str
    fields: dict = Field(default_factory=dict)     # numeric/categorical fields of the effect
    source: Optional[AnnSpan] = None


class AnnRule(BaseModel):
    modality: Modality
    agent_class: Optional[str] = None
    subject: Optional[AnnSpan] = None
    conditions: list[AnnCondition] = Field(default_factory=list)
    action: Optional[AnnSpan] = None
    consequence: Optional[AnnSpan] = None
    exceptions: list[AnnSpan] = Field(default_factory=list)
    cross_refs: list[AnnSpan] = Field(default_factory=list)
    effects: list[AnnEffect] = Field(default_factory=list)
    executable: bool = True
    note: str = ""


class Annotation(BaseModel):
    item_id: str = ""             # taken from the URL on save
    annotator_id: str = ""
    annotator_name: str = ""
    status: Literal["draft", "done"] = "draft"
    no_rule: bool = False          # the provision states no rule (heading, commencement …)
    rules: list[AnnRule] = Field(default_factory=list)
    seconds: int = 0               # time spent, for reporting annotation cost
    note: str = ""
    guideline_version: int = GUIDELINE_VERSION
    updated_at: str = ""

    def spans(self):
        for r in self.rules:
            for s in [r.subject, r.action, r.consequence, *r.conditions, *r.exceptions, *r.cross_refs,
                      *(e.source for e in r.effects)]:
                if s is not None:
                    yield s
