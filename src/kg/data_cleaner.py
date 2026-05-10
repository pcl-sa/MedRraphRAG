import re
import pandas as pd
from difflib import SequenceMatcher


class DataCleaner:
    """Clean and normalize medical Q&A text."""

    @staticmethod
    def clean_text(text: str) -> str:
        if not isinstance(text, str):
            return ""
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Unify full-width brackets
        text = text.replace("（", "(").replace("）", ")")
        text = text.replace("【", "[").replace("】", "]")
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove redundant punctuation
        text = re.sub(r"[,，]{2,}", "，", text)
        text = re.sub(r"[。.]{2,}", "。", text)
        return text.strip()

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        if not isinstance(text, str) or not text.strip():
            return []
        # Split on Chinese/English sentence-ending punctuation
        sents = re.split(r"(?<=[。！？；!?;])", text)
        return [s.strip() for s in sents if s.strip() and len(s.strip()) > 2]

    @staticmethod
    def normalize_medical_terms(text: str, term_map: dict | None = None) -> str:
        if term_map is None:
            term_map = {}
        for variant, standard in term_map.items():
            text = text.replace(variant, standard)
        return text

    @staticmethod
    def deduplicate(df: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
        """Remove near-duplicate Q&A pairs based on ask column similarity."""
        keep = []
        asks = df["ask"].astype(str).tolist()
        dropped = set()

        for i in range(len(asks)):
            if i in dropped:
                continue
            keep.append(i)
            for j in range(i + 1, len(asks)):
                if j in dropped:
                    continue
                if SequenceMatcher(None, asks[i], asks[j]).ratio() > threshold:
                    dropped.add(j)

        result = df.iloc[keep].reset_index(drop=True)
        if len(dropped) > 0:
            print(f"  Dedup: removed {len(dropped)} near-duplicate rows")
        return result

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Full cleaning pipeline."""
        print(f"Cleaning {len(df)} records...")
        df = df.copy()
        for col in ["title", "ask", "answer"]:
            if col in df.columns:
                df[col] = df[col].apply(self.clean_text)
        df = self.deduplicate(df)
        print(f"  After cleaning: {len(df)} records")
        return df
