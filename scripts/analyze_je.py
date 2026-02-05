#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import pandas as pd


def detect_date_range(series: pd.Series) -> dict | None:
    if series.empty:
        return None
    if pd.api.types.is_datetime64_any_dtype(series):
        parsed = series
    else:
        parsed = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
    non_null = parsed.notna().sum()
    if non_null == 0:
        return None
    ratio = non_null / len(series)
    if ratio < 0.5:
        return None
    return {
        "non_null": int(non_null),
        "min": parsed.min().isoformat() if non_null else None,
        "max": parsed.max().isoformat() if non_null else None,
    }


def numeric_summary(series: pd.Series) -> dict | None:
    if not pd.api.types.is_numeric_dtype(series):
        return None
    non_null = series.notna().sum()
    if non_null == 0:
        return None
    return {
        "non_null": int(non_null),
        "mean": float(series.mean()),
        "min": float(series.min()),
        "max": float(series.max()),
        "sum": float(series.sum()),
    }


def benford_expected() -> dict[int, float]:
    return {digit: math.log10(1 + 1 / digit) for digit in range(1, 10)}


def leading_digit(series: pd.Series) -> pd.Series:
    if not pd.api.types.is_numeric_dtype(series):
        return pd.Series(dtype="Int64")
    values = series.dropna().astype(float).abs()
    values = values[values > 0]
    if values.empty:
        return pd.Series(dtype="Int64")
    digits = values.apply(lambda value: int(str(value).lstrip("0.")[0]))
    return digits


def benford_summary(series: pd.Series) -> dict | None:
    digits = leading_digit(series)
    if digits.empty:
        return None
    counts = digits.value_counts().reindex(range(1, 10), fill_value=0).sort_index()
    total = counts.sum()
    expected = benford_expected()
    expected_counts = pd.Series(
        {digit: expected[digit] * total for digit in range(1, 10)}
    )
    chi_square = float(
        (((counts - expected_counts) ** 2) / expected_counts).sum()
        if total > 0
        else 0
    )
    return {
        "total": int(total),
        "chi_square": chi_square,
        "counts": counts.to_dict(),
        "percentages": (counts / total).to_dict(),
    }


def build_summary(excel_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    workbook = pd.ExcelFile(excel_path)

    summary = {
        "workbook": excel_path.name,
        "sheet_count": len(workbook.sheet_names),
        "sheets": [],
    }

    column_rows = []

    benford_rows = []
    for sheet_name in workbook.sheet_names:
        df = workbook.parse(sheet_name)
        sheet_summary = {
            "sheet": sheet_name,
            "row_count": int(df.shape[0]),
            "column_count": int(df.shape[1]),
            "columns": list(df.columns.astype(str)),
            "date_ranges": {},
            "numeric_summaries": {},
        }

        for column in df.columns:
            series = df[column]
            column_rows.append(
                {
                    "sheet": sheet_name,
                    "column": str(column),
                    "dtype": str(series.dtype),
                    "non_null": int(series.notna().sum()),
                    "nulls": int(series.isna().sum()),
                    "unique": int(series.nunique(dropna=True)),
                }
            )

            date_info = detect_date_range(series)
            if date_info:
                sheet_summary["date_ranges"][str(column)] = date_info

            numeric_info = numeric_summary(series)
            if numeric_info:
                sheet_summary["numeric_summaries"][str(column)] = numeric_info

            benford_info = benford_summary(series)
            if benford_info:
                benford_rows.append(
                    {
                        "sheet": sheet_name,
                        "column": str(column),
                        "total_values": benford_info["total"],
                        "chi_square": benford_info["chi_square"],
                        **{
                            f"digit_{digit}_pct": benford_info["percentages"][digit]
                            for digit in range(1, 10)
                        },
                    }
                )

        summary["sheets"].append(sheet_summary)

        describe_path = output_dir / f"describe_{sheet_name}.csv"
        df.describe(include="all").to_csv(describe_path)

    (output_dir / "column_stats.csv").write_text(
        pd.DataFrame(column_rows).to_csv(index=False)
    )

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    if benford_rows:
        benford_path = output_dir / "benford_summary.csv"
        pd.DataFrame(benford_rows).to_csv(benford_path, index=False)

    md_lines = [
        f"# Journal Entry Summary for `{excel_path.name}`",
        "",
        f"Total sheets: **{summary['sheet_count']}**",
        "",
    ]
    for sheet in summary["sheets"]:
        md_lines.extend(
            [
                f"## Sheet: {sheet['sheet']}",
                f"- Rows: **{sheet['row_count']}**",
                f"- Columns: **{sheet['column_count']}**",
            ]
        )
        if sheet["date_ranges"]:
            md_lines.append("- Date ranges:")
            for col, info in sheet["date_ranges"].items():
                md_lines.append(
                    f"  - {col}: {info['min']} → {info['max']} (non-null {info['non_null']})"
                )
        if sheet["numeric_summaries"]:
            md_lines.append("- Numeric summaries:")
            for col, info in sheet["numeric_summaries"].items():
                md_lines.append(
                    "  - {col}: mean {mean:.2f}, min {min:.2f}, max {max:.2f}, sum {sum:.2f}".format(
                        col=col,
                        mean=info["mean"],
                        min=info["min"],
                        max=info["max"],
                        sum=info["sum"],
                    )
                )
        md_lines.append("")

    if benford_rows:
        md_lines.extend(
            [
                "## Benford's Law Results",
                "",
                "Benford analysis is computed on numeric columns using leading digits.",
                "See `benford_summary.csv` for per-column distributions and chi-square scores.",
                "",
            ]
        )

    (output_dir / "summary.md").write_text("\n".join(md_lines))

    index_lines = [
        "# Output Files",
        "",
        "This folder is generated by the journal entry analysis workflow.",
        "",
        "- `summary.json`: machine-readable summary",
        "- `summary.md`: human-readable summary",
        "- `column_stats.csv`: per-column statistics",
        "- `describe_<sheet>.csv`: pandas describe output per sheet",
        "- `benford_summary.csv`: Benford's Law leading digit distribution per column",
    ]
    (output_dir / "index.md").write_text("\n".join(index_lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze journal entry Excel data.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("je_samples (1).xlsx"),
        help="Path to the Excel workbook",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs"),
        help="Directory to write outputs",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")

    build_summary(args.input, args.output)


if __name__ == "__main__":
    main()
