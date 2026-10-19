def summarize(rows):
    return {"total_s": sum(row["seconds"] for row in rows)}
