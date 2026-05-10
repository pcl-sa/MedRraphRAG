import pandas as pd
from pathlib import Path
from typing import Optional


class DataLoader:
    """Load medical Q&A CSVs from Data_original/ and produce stratified samples."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._dept_map = {
            "Andriatria_男科": "Andriatria5_changed-13000.csv",
            "IM_内科": "IM5000-33000.csv",
            "OAGD_妇产科": "OAGD6-28000.csv",
            "Oncology_肿瘤科": "Oncology5-10000.csv",
            "Pediatric_儿科": "Pediatric5-14000.csv",
            "Surgical_外科": "Surgical5-14000.csv",
        }

    def load_all(self) -> pd.DataFrame:
        """Load and concatenate all 6 department CSV files."""
        frames = []
        for dept_dir, filename in self._dept_map.items():
            fp = self.data_dir / dept_dir / filename
            if not fp.exists():
                print(f"  SKIP: {fp} not found")
                continue
            df = pd.read_csv(fp, encoding="utf-8")
            frames.append(df)
        full = pd.concat(frames, ignore_index=True)
        print(f"Loaded {len(full)} records from {len(frames)} files")
        return full

    def stratified_sample(self, n: int = 500) -> pd.DataFrame:
        """Proportional stratified sample across departments."""
        df = pd.concat([
            pd.read_csv(self.data_dir / d / f, encoding="utf-8")
            for d, f in self._dept_map.items()
            if (self.data_dir / d / f).exists()
        ], ignore_index=True)

        sampled = df.groupby(
            df["department"].apply(lambda x: x.split("_")[0] if "_" in str(x) else str(x)),
            group_keys=False
        ).apply(
            lambda g: g.sample(n=max(1, int(n * len(g) / len(df))), random_state=42)
        ).reset_index(drop=True)

        print(f"Stratified sample: {len(sampled)} records")
        return sampled

    def save_sample(self, df: pd.DataFrame, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Sample saved to {path}")

    def load_sample(self, path: Path) -> pd.DataFrame:
        return pd.read_csv(Path(path), encoding="utf-8-sig")
