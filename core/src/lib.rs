use pyo3::prelude::*;

#[pyfunction]
fn calculate_efficiency_series(watts: Vec<f64>, pulses: Vec<f64>) 
    -> PyResult<(f64, String, Vec<f64>, Vec<String>)> 
{
    if watts.is_empty() || pulses.is_empty() || watts.len() != pulses.len() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Watt og puls-lister må ha samme lengde og ikke være tomme.",
        ));
    }

    // Beregn snittverdier
    let avg_watt: f64 = watts.iter().sum::<f64>() / watts.len() as f64;
    let avg_pulse: f64 = pulses.iter().sum::<f64>() / pulses.len() as f64;
    let avg_eff = if avg_pulse == 0.0 { 0.0 } else { avg_watt / avg_pulse };

    // Status for hele økten
    let session_status = if avg_eff < 1.0 {
        "Lav effekt – vurder å øke tråkkfrekvens eller intensitet.".to_string()
    } else if avg_pulse > 170.0 {
        "Høy puls – vurder lengre restitusjon.".to_string()
    } else {
        "OK – treningen ser balansert ut.".to_string()
    };

    // Per-datapunkt effektivitet + status
    let mut per_point_eff = Vec::new();
    let mut per_point_status = Vec::new();

    for (w, p) in watts.iter().zip(pulses.iter()) {
        let eff = if *p == 0.0 { 0.0 } else { w / p };
        per_point_eff.push(eff);

        let status = if eff < 1.0 {
            "Lav effekt".to_string()
        } else if *p > 170.0 {
            "Høy puls".to_string()
        } else {
            "OK".to_string()
        };
        per_point_status.push(status);
    }

    Ok((avg_eff, session_status, per_point_eff, per_point_status))
}

#[pymodule]
fn cyclegraph_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_efficiency_series, m)?)?;
    Ok(())
}
