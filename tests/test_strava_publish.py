from cli.formatters.strava_publish import build_publish_texts

print("=== FULL DATASET / NO ===")
report_full = {
    "scores": {"cgs": 88, "intensity": 93, "duration": 82, "quality": 88},
    "vi": 1.11,
    "pa_hr_pct": 2.4,
    "w_per_beat": 1.59,
    "w_per_beat_baseline": 1.45,
    "trend": {"cgs_last3_avg": 85, "cgs_delta_vs_last3": 3.4},
    "if": 0.92
}
pieces_no = build_publish_texts(report_full, lang="no")
print("COMMENT:", pieces_no.comment)
print("HEADER:", pieces_no.desc_header)
print("BODY:", pieces_no.desc_body)

print("\n=== FULL DATASET / EN ===")
pieces_en = build_publish_texts(report_full, lang="en")
print("COMMENT:", pieces_en.comment)
print("HEADER:", pieces_en.desc_header)
print("BODY:", pieces_en.desc_body)

print("\n=== MISSING FIELDS ===")
report_missing = {
    "scores": {"cgs": 70},
    "if": 0.80
}
pieces_missing = build_publish_texts(report_missing, lang="no")
print("COMMENT:", pieces_missing.comment)
print("HEADER:", pieces_missing.desc_header)
print("BODY:", pieces_missing.desc_body)
