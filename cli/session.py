import argparse

def cmd_session(args: argparse.Namespace) -> int:
    cfg = load_cfg(args.cfg)
    history_dir = cfg.get("history_dir", "history")
    outdir = getattr(args, "out", "output")
    fmt = getattr(args, "format", "json")
    lang = getattr(args, "lang", "no")

    paths = sorted(glob.glob(args.input))
    if getattr(args, "debug", False):
        print("DEBUG: input filer:", paths, file=sys.stderr)
    if not paths:
        print(f"Ingen filer for pattern: {args.input}", file=sys.stderr)
        return 2

    reports: List[Dict[str, Any]] = []

    for path in paths:
        samples = read_session_csv(path, debug=getattr(args, "debug", False))
        if getattr(args, "debug", False):
            print(f"DEBUG: {path} -> {len(samples)} samples", file=sys.stderr)
        if not samples:
            print(f"ADVARSEL: {path} har ingen gyldige samples.", file=sys.stderr)
            continue

        sid = session_id_from_path(path)
        duration_sec = infer_duration_sec(samples)
        meta = {
            "session_id": sid,
            "duration_sec": duration_sec,
            "ftp": None,
            "hr_max": cfg.get("hr_max"),
            "start_time_utc": None
        }
        if getattr(args, "mode", None):
           print(f"🎛️ Overstyrt modus: {args.mode}")
           meta["mode"] = args.mode
        else:
           print("🔍 Ingen overstyring – modus settes automatisk senere hvis relevant.")

        if getattr(args, "set_ftp", None) is not None:
            meta["ftp"] = float(args.set_ftp)
        elif getattr(args, "auto_ftp", False):
            ftp_est = estimate_ftp_20min95(samples)
            if ftp_est > 0:
                meta["ftp"] = round(ftp_est, 1)
        elif "ftp" in cfg:
            meta["ftp"] = cfg.get("ftp")

        report_raw = _analyze_session_bridge(samples, meta, cfg)

        if isinstance(report_raw, str) and report_raw.strip() == "":
            print(f"ADVARSEL: _analyze_session_bridge returnerte tom streng for {path}", file=sys.stderr)
            continue

        try:
            report = json.loads(report_raw) if isinstance(report_raw, str) else report_raw
        except json.JSONDecodeError as e:
            print(f"ADVARSEL: Klarte ikke å parse JSON for {path}: {e}", file=sys.stderr)
            continue

        baseline = load_baseline_wpb(history_dir, sid, report.get("duration_min", 0.0))
        if baseline is not None:
            report["w_per_beat_baseline"] = round(baseline, 4)

        maybe_apply_big_engine_badge(report)
        reports.append(report)

        if not getattr(args, "batch", False):
            if getattr(args, "dry_run", False):
                print(json.dumps(report, ensure_ascii=False, indent=2))
                try:
                    pieces = build_publish_texts(report, lang=lang)
                    print(f"[DRY-RUN] COMMENT: {pieces.comment}")
                    print(f"[DRY-RUN] DESC: {pieces.desc_header}")
                except Exception as e:
                    print(f"[DRY-RUN] build_publish_texts feilet: {e}")
            else:
                write_report(outdir, sid, report, fmt)
                write_history_copy(history_dir, report)

            if getattr(args, "publish_to_strava", False):
                try:
                    pieces = build_publish_texts(report, lang=lang)
                    aid, status = StravaClient(lang=lang).publish_to_strava(pieces, dry_run=getattr(args, "dry_run", False))
                    print(f"[STRAVA] activity_id={aid} status={status}")
                except Exception as e:
                    print(f"[STRAVA] publisering feilet: {e}")

    if getattr(args, "batch", False) and reports:
        if getattr(args, "with_trend", False):
            apply_trend_last3(reports)

        for r in reports:
            sid = r.get("session_id", "session")
            baseline = load_baseline_wpb(history_dir, sid, r.get("duration_min", 0.0))
            if baseline is not None:
                r["w_per_beat_baseline"] = round(baseline, 4)
            maybe_apply_big_engine_badge(r)

            if getattr(args, "dry_run", False):
                print(json.dumps(r, ensure_ascii=False, indent=2))
                try:
                    pieces = build_publish_texts(r, lang=lang)
                    print(f"[DRY-RUN] COMMENT: {pieces.comment}")
                    print(f"[DRY-RUN] DESC: {pieces.desc_header}")
                except Exception as e:
                    print(f"[DRY-RUN] build_publish_texts feilet: {e}")
            else:
                write_report(outdir, sid, r, fmt)
                write_history_copy(history_dir, r)

        if getattr(args, "publish_to_strava", False):
            try:
                pieces = build_publish_texts(reports[-1], lang=lang)
                aid, status = StravaClient(lang=lang).publish_to_strava(pieces, dry_run=getattr(args, "dry_run", False))
                print(f"[STRAVA] activity_id={aid} status={status}")
            except Exception as e:
                print(f"[STRAVA] publisering feilet: {e}")

    return 0
