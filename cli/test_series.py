from cyclegraph_core import calculate_efficiency_series

# Eksempeldata – kan byttes ut med reelle treningsmålinger
watts = [200, 220, 210, 230]
pulses = [150, 152, 148, 151]

avg_eff, session_status, per_point_eff, per_point_status = calculate_efficiency_series(watts, pulses)

print(f"Snitteffektivitet: {avg_eff:.2f} watt/puls")
print(f"Øktstatus: {session_status}\n")

print("Per datapunkt:")
for i, (eff, status) in enumerate(zip(per_point_eff, per_point_status), start=1):
    print(f"  Punkt {i}: {eff:.2f} watt/puls – {status}")