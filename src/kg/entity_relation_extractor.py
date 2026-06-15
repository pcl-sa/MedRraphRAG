import json
import os
import time
from pathlib import Path
from typing import List, Optional
from tqdm import tqdm
from langchain_community.chat_models.tongyi import ChatTongyi
from ..config import get_settings
from .schema import ExtractionResult, ExtractedTriple, RelationType, EntityType, RELATION_DESCRIPTIONS

# ====================== 模型列表（按优先级排列，前一个 token 耗尽时自动切换下一个）======================
MODEL_LIST = [
    "qwen3.7-max",
]
# ==================================================================================================

_RELATION_LIST = "\n".join(f"- {r.value}: {RELATION_DESCRIPTIONS[r]}" for r in RelationType)

_EXTRACTION_PROMPT = f"""医疗文本知识三元组提取。请从给定医学文本中识别医学实体并抽取关系。

【实体类型】
disease(疾病), symptom(症状), drug(药物), examination(检查), treatment(治疗方法),
department(科室), body_part(身体部位), risk_factor(风险因素), cause(病因),
complication(并发症), food(食物/饮食), substance(化学物质), outcome(预后/结局), other(其他)

【关系类型】
{_RELATION_LIST}

【规则】
1. 实体必须使用书面语全称，禁止使用缩写或英文
2. 仅输出标准JSON，不要其他内容
3. confidence取0.0~1.0，低于0.4的三元组不要输出
4. 每对实体间只标注最准确的一个关系
5. 如果没有可抽取的医学知识，返回空列表

【输入文本】
{{text}}

【输入科室】
{{department}}
"""

# 判断 token 耗尽的错误关键词
_TOKEN_EXHAUSTED_KEYWORDS = [
    "rate limit", "quota exceeded", "token", "throttle",
    "exhausted", "limit exceeded", "too many requests", "429",
    "rate exceeded", "quota limit", "over quota", "rate limited",
    "流量限制", "额度不足", "token不足", "配额", "超限",
]


def _is_token_exhausted(error: Exception) -> bool:
    """Check if the error is due to token/rate limit exhaustion."""
    msg = str(error).lower()
    return any(kw in msg for kw in _TOKEN_EXHAUSTED_KEYWORDS)


class EntityRelationExtractor:
    """Use Tongyi LLM to extract medical entities and relations from text.

    Supports automatic model fallback: when the current model's token quota is
    exhausted, the extractor switches to the next model in MODEL_LIST.
    """

    def __init__(self, model_list: Optional[List[str]] = None, temperature: float = 0.3):
        settings = get_settings()
        self.settings = settings
        self.temperature = temperature
        self.model_list = model_list or MODEL_LIST
        if not self.model_list:
            raise ValueError("MODEL_LIST is empty — please add at least one model name")
        self._model_index = 0
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM with the current model in the list."""
        model_name = self.model_list[self._model_index]
        self.current_model = model_name
        self.llm = ChatTongyi(
            model=model_name,
            dashscope_api_key=self.settings.dashscope_api_key,
            temperature=self.temperature,
            max_tokens=self.settings.llm_max_tokens,
        )
        self.structured_llm = self.llm.with_structured_output(ExtractionResult)
        print(f"  LLM model: {model_name}")

    def _try_switch_model(self) -> bool:
        """Switch to the next model in the list. Returns False if no more models."""
        if self._model_index + 1 >= len(self.model_list):
            return False
        self._model_index += 1
        self._init_llm()
        return True

    def extract_from_text(self, text: str, department: str = "", max_retries: int = 3) -> List[ExtractedTriple]:
        """Extract triples from a single medical text. Auto-fallbacks on token exhaustion."""
        if not text or len(text) < 10:
            return []

        prompt = _EXTRACTION_PROMPT.format(text=text[:2000], department=department)

        while True:  # model fallback loop
            for attempt in range(max_retries):
                try:
                    result = self.structured_llm.invoke(prompt)
                    if result is None:
                        raise ValueError("LLM returned None — may indicate API error or malformed response")
                    return [t for t in result.triples if t.confidence >= 0.4]
                except Exception as e:
                    if _is_token_exhausted(e):
                        print(f"  Token exhausted for '{self.current_model}': {str(e)[:100]}")
                        if self._try_switch_model():
                            print(f"  Switched to '{self.current_model}'")
                            break  # break retry loop, continue with new model
                        else:
                            print(f"  No more fallback models available")
                            return []
                    # Non-quota error: retry with current model
                    if attempt == max_retries - 1:
                        print(f"  Extraction failed: {str(e)[:100]}")
                        return []
                    time.sleep(1.0 * (attempt + 1))
            else:
                # All retries exhausted without triggering a model switch
                return []

    def extract_batch(
        self,
        texts: list[str],
        departments: list[str] | None = None,
        delay: float = 0.5,
    ) -> List[List[ExtractedTriple]]:
        """Extract triples from a batch of texts (no checkpoint)."""
        if departments is None:
            departments = [""] * len(texts)

        results = []
        for i in tqdm(range(len(texts)), desc="Extracting triples"):
            triples = self.extract_from_text(texts[i], departments[i])
            results.append(triples)
            if delay > 0:
                time.sleep(delay)
        return results

    def extract_from_dataframe(
        self,
        df,
        text_col: str = "answer",
        dept_col: str = "department",
        delay: float = 0.5,
        checkpoint_path: Optional[str] = None,
    ) -> List[dict]:
        """Extract from a DataFrame with automatic checkpoint/resume support.

        If checkpoint_path is provided and the file exists, extraction resumes
        from the last processed row. After each row, progress is saved to disk.
        """
        texts = df[text_col].astype(str).tolist()
        depts = df[dept_col].astype(str).tolist() if dept_col in df.columns else [""] * len(texts)
        total = len(texts)

        # ── Resume from checkpoint ──
        all_triples: List[dict] = []
        start_row = 0
        if checkpoint_path:
            ckpt = self._load_checkpoint(checkpoint_path)
            if ckpt is not None:
                all_triples = ckpt["triples"]
                start_row = ckpt["last_row"] + 1
                # Restore model index if it was saved
                if "model_index" in ckpt and ckpt["model_index"] != self._model_index:
                    self._model_index = ckpt["model_index"]
                    self._init_llm()
                print(f"  Resuming from row {start_row}/{total} "
                      f"({len(all_triples)} triples loaded, model: {self.current_model})")

        # ── Process remaining rows ──
        for i in tqdm(range(start_row, total), desc="Extracting triples",
                      initial=start_row, total=total):
            triples = self.extract_from_text(texts[i], depts[i])
            for t in triples:
                all_triples.append({
                    "head_entity": t.head_entity,
                    "head_type": t.head_type.value,
                    "relation": t.relation.value,
                    "tail_entity": t.tail_entity,
                    "tail_type": t.tail_type.value,
                    "confidence": t.confidence,
                    "evidence": t.evidence,
                    "source_row": i,
                })

            # ── Save checkpoint ──
            if checkpoint_path:
                self._save_checkpoint(checkpoint_path, all_triples, i)

            if delay > 0:
                time.sleep(delay)

        # ── Clean up checkpoint on success ──
        if checkpoint_path:
            self._remove_checkpoint(checkpoint_path)

        return all_triples

    # ── checkpoint helpers ──

    def _save_checkpoint(self, path: str, triples: List[dict], last_row: int):
        """Atomic checkpoint write."""
        data = {
            "triples": triples,
            "last_row": last_row,
            "model_index": self._model_index,
        }
        tmp = path + ".tmp"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)  # atomic on same filesystem

    def _load_checkpoint(self, path: str) -> Optional[dict]:
        if not Path(path).exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _remove_checkpoint(self, path: str):
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass
