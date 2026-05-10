from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    DISEASE = "disease"
    SYMPTOM = "symptom"
    DRUG = "drug"
    EXAMINATION = "examination"
    TREATMENT = "treatment"
    DEPARTMENT = "department"
    BODY_PART = "body_part"
    RISK_FACTOR = "risk_factor"
    CAUSE = "cause"
    COMPLICATION = "complication"
    FOOD = "food"
    SUBSTANCE = "substance"
    OUTCOME = "outcome"
    OTHER = "other"


class RelationType(str, Enum):
    HAS_SYMPTOM = "has_symptom"             # 疾病 → 症状
    TREATED_WITH = "treated_with"           # 疾病 → 药物
    CAUSED_BY = "caused_by"                 # 疾病 → 病因
    LOCATED_IN = "located_in"               # 疾病/症状 → 部位
    HAS_COMPLICATION = "has_complication"   # 疾病 → 并发症
    HAS_TREATMENT = "has_treatment"         # 疾病 → 治疗方法
    HAS_DIAGNOSIS = "has_diagnosis"         # 疾病 → 检查方法
    HAS_SIDE_EFFECT = "has_side_effect"     # 药物 → 副作用
    BELONGS_TO = "belongs_to"               # 症状/疾病 → 科室
    DRUG_CONTRAINDICATION = "drug_contraindication"  # 药物 → 禁忌症
    DRUG_INTERACTION = "drug_interaction"   # 药物 → 药物（相互作用）
    EXAMINES = "examines"                   # 检查 → 疾病
    HAS_RISK_FACTOR = "has_risk_factor"     # 疾病 → 风险因素
    AFFECTS = "affects"                     # 疾病 → 影响部位
    PREVENTS = "prevents"                   # 药物/疗法 → 预防疾病
    ASSOCIATED_WITH = "associated_with"     # 疾病 → 相关疾病


RELATION_DESCRIPTIONS = {
    RelationType.HAS_SYMPTOM: "疾病有什么症状",
    RelationType.TREATED_WITH: "疾病用什么药物治疗",
    RelationType.CAUSED_BY: "疾病由什么原因引起",
    RelationType.LOCATED_IN: "疾病/症状发生在什么部位",
    RelationType.HAS_COMPLICATION: "疾病可能引起什么并发症",
    RelationType.HAS_TREATMENT: "疾病的治疗方法是什么",
    RelationType.HAS_DIAGNOSIS: "疾病如何诊断/做什么检查",
    RelationType.HAS_SIDE_EFFECT: "药物有什么副作用",
    RelationType.BELONGS_TO: "症状/疾病属于哪个科室",
    RelationType.DRUG_CONTRAINDICATION: "药物有什么禁忌症",
    RelationType.DRUG_INTERACTION: "药物与什么药物相互作用",
    RelationType.EXAMINES: "检查项目用于诊断什么疾病",
    RelationType.HAS_RISK_FACTOR: "疾病有什么风险因素",
    RelationType.AFFECTS: "疾病影响哪些部位",
    RelationType.PREVENTS: "药物/疗法可以预防什么疾病",
    RelationType.ASSOCIATED_WITH: "疾病与哪些疾病相关",
}


class ExtractedTriple(BaseModel):
    head_entity: str = Field(description="头实体名称（书面语全称）")
    head_type: EntityType = Field(description="头实体类型")
    relation: RelationType = Field(description="关系类型")
    tail_entity: str = Field(description="尾实体名称（书面语全称）")
    tail_type: EntityType = Field(description="尾实体类型")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度")
    evidence: str = Field(default="", description="原文证据")


class ExtractionResult(BaseModel):
    triples: List[ExtractedTriple] = Field(description="提取到的三元组列表")
