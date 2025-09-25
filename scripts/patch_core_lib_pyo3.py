# scripts/patch_core_lib_pyo3.py
import io, os, re, sys

LIB = "core/src/lib.rs"

BIND_FN = r'''
#[cfg(feature = "python")]
#[pyo3::prelude::pyfunction]
fn compute_power_with_wind_json(
    samples_json: &str,
    profile_json: &str,
    weather_json: &str,
) -> pyo3::PyResult<String> {
    use pyo3::exceptions::PyValueError;
    use serde_json::json;

    let samples: Vec<crate::models::Sample> = serde_json::from_str(samples_json)
        .map_err(|e| PyValueError::new_err(format!("samples parse error: {e}")))?;
    let profile: crate::models::Profile = serde_json::from_str(profile_json)
        .map_err(|e| PyValueError::new_err(format!("profile parse error: {e}")))?;
    let weather: crate::models::Weather = serde_json::from_str(weather_json)
        .map_err(|e| PyValueError::new_err(format!("weather parse error: {e}")))?;

    let out = crate::physics::compute_power_with_wind(&samples, &profile, &weather);
    let s = serde_json::to_string(&json!({
        "watts": out.power,
        "wind_rel": out.wind_rel,
        "v_rel": out.v_rel,
    }))
    .map_err(|e| PyValueError::new_err(format!("serialize error: {e}")))?;
    Ok(s)
}
'''.strip()+"\n"

ADD_FN_IN_PYMODULE = 'm.add_function(pyo3::wrap_pyfunction!(compute_power_with_wind_json, m)?)?;'

def main():
    if not os.path.isfile(LIB):
        print(f"[ERR] Fant ikke {LIB}", file=sys.stderr)
        sys.exit(1)

    with io.open(LIB, "r", encoding="utf-8") as f:
        src = f.read()

    changed = False

    # 1) Legg inn pyfunction hvis mangler
    if "fn compute_power_with_wind_json(" not in src:
        # prøv å finne et sted i Python-seksjonen å legge funksjonen
        m = re.search(r'(?s)#\[cfg\(feature\s*=\s*"python"\)\].*?pymodule', src)
        insert_pos = m.start() if m else len(src)
        src = src[:insert_pos] + "\n\n" + BIND_FN + "\n" + src[insert_pos:]
        changed = True
        print("[OK] La til PyO3-funksjonen compute_power_with_wind_json")

    # 2) Registrer i pymodule
    pymod_re = re.compile(r'(?s)#\[cfg\(feature\s*=\s*"python"\)\]\s*#[^\n]*pymodule[^{]+\{(.*?)\}', re.M)
    mo = pymod_re.search(src)
    if mo:
        body = mo.group(1)
        if "compute_power_with_wind_json" not in body:
            new_body = body
            # sørg for wrap_pyfunction (bruk fullt kvalifisert macro)
            new_body = new_body.replace("{", "{", 1)
            new_body = new_body + "\n    " + ADD_FN_IN_PYMODULE + "\n"
            # bygg ny src
            start, end = mo.span(1)
            src = src[:start] + new_body + src[end:]
            changed = True
            print("[OK] Registrerte compute_power_with_wind_json i #[pymodule]")
    else:
        print("[WARN] Fant ikke #[pymodule]-blokk; antas allerede korrekt hvis modul genereres annet sted.")

    if changed:
        with io.open(LIB, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"[DONE] Patch oppdatert: {LIB}")
    else:
        print("[SKIP] Ingen endringer nødvendig")

if __name__ == "__main__":
    main()