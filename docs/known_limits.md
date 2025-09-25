## 📄 `docs/known_limits.md`

```markdown
# Known limits

- **HR-data kreves** for å beregne Pa:Hr og W/beat.
- **PrecisionWatt** er estimert – ikke målt – og avhenger av inputkvalitet og smoothing.
- **Rapporten er ikke egnet** for sprint-analyse eller økter <30 sekunder.
- **sessions_no_power_total** trigges kun ved fullstendig fravær av wattdata.
- **VI** kan være misvisende ved korte eller ujevne økter.
- **Fallback-modus** (`hr_only`) gir begrenset rapport og utelater enkelte felter.