import json
from pathlib import Path
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

RESULTS_FILE = Path("./benchmark_data/benchmark_results.json")

def main():
    """
    Analyzes the benchmark_results.json file and prints a quantitative summary.
    """
    console = Console()
    console.print(Panel("[bold cyan]Benchmark Analysis Report[/bold cyan]", expand=False))
    if not RESULTS_FILE.exists():
        console.print(f"[bold red]Error: Results file not found at '{RESULTS_FILE}'.[/bold red]")
        console.print("Please run the benchmark script first.")
        exit(1)

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        try:
            results = json.load(f)
        except json.JSONDecodeError:
            console.print(
                f"[bold red]Error: Could not parse '{RESULTS_FILE}'. It may be corrupted or empty.[/bold red]")
            exit(1)

    if not results:
        console.print("[yellow]Benchmark results file is empty. Nothing to analyze.[/yellow]")
        exit(0)

    processed_data = []
    for item in results:
        flat_item = {
            "question_id": item.get("question_id"),
            "source_file": item.get("source_file"),
            "question": item.get("question"),
        }
        critique = item.get("critique")
        if critique:
            flat_item.update(critique)
        processed_data.append(flat_item)

    df = pd.DataFrame(processed_data)

    total_questions = len(df)

    average_score = df["score"].mean()

    context_relevance_rate = df["context_is_relevant"].mean() * 100
    context_sufficiency_rate = df["context_is_sufficient"].mean() * 100
    answer_correctness_rate = df["is_answer_correct"].mean() * 100
    answer_groundedness_rate = df["is_answer_grounded"].mean() * 100

    summary_table = Table(title="[bold green]Overall System Performance[/bold green]")
    summary_table.add_column("Metric", style="cyan", no_wrap=True)
    summary_table.add_column("Score / Rate", style="magenta")

    summary_table.add_row("Total Questions Analyzed", str(total_questions))
    summary_table.add_row("Average Score (out of 5.0)", f"{average_score:.2f} ⭐")
    summary_table.add_row("-" * 20, "-" * 20)
    summary_table.add_row("Context Relevance Rate", f"{context_relevance_rate:.1f}%")
    summary_table.add_row("Context Sufficiency Rate", f"{context_sufficiency_rate:.1f}%")
    summary_table.add_row("Answer Correctness Rate", f"{answer_correctness_rate:.1f}%")
    summary_table.add_row("Answer Groundedness Rate", f"{answer_groundedness_rate:.1f}%")

    console.print(summary_table)

    worst_questions = df[df["score"] <= 2].sort_values("score").head(3)

    if not worst_questions.empty:
        worst_table = Table(title="[bold red]Top 3 Worst Performing Questions[/bold red]")
        worst_table.add_column("ID", style="cyan")
        worst_table.add_column("Score", style="magenta")
        worst_table.add_column("Question", style="white")

        for _, row in worst_questions.iterrows():
            worst_table.add_row(
                row["question_id"],
                str(row["score"]),
                row["question"]
            )

        console.print("\n")
        console.print(worst_table)


if __name__ == "__main__":
    main()
