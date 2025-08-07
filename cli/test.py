from cyclegraph_core import calculate_efficiency

watt = 250
pulse = 160
eff = calculate_efficiency(watt, pulse)
print(f"Effektivitet: {eff:.2f} watt/puls")