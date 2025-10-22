# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
from fitparse import FitFile

SRC = Path(r'data\imports')
DST = SRC / 'csv'
DST.mkdir(parents=True, exist_ok=True)

def to_csv(fit_path: Path):
    ff = FitFile(str(fit_path))
    rows = []
    for msg in ff.get_messages('record'):
        d = {f.name: f.value for f in msg}
        # Vi trenger timestamp, power, heart_rate
        t  = d.get('timestamp')
        pw = d.get('power')
        hr = d.get('heart_rate')
        if pw is None or hr is None:
            continue
        rows.append({
            't': t.isoformat() if hasattr(t, 'isoformat') else t,
            'watts': int(pw) if isinstance(pw, (int, float)) else None,
            'hr': int(hr) if isinstance(hr, (int, float)) else None,
        })
    if not rows:
        return None

    df = pd.DataFrame(rows).dropna(subset=['watts','hr'])
    df['watts'] = df['watts'].astype(int)
    df['hr']    = df['hr'].astype(int)

    out = DST / (fit_path.stem + '.csv')
    df.to_csv(out, index=False)
    return out

def main():
    made = []
    for p in SRC.glob('*.fit'):
        out = to_csv(p)
        if out:
            print('OK:', out)
            made.append(out)
        else:
            print('SKIP (no usable power/hr):', p)
    if not made:
        print('No CSVs produced — check your FIT files.')

if __name__ == '__main__':
    main()
