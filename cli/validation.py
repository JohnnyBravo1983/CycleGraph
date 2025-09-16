def validate_rdf(shape_path="shapes/session_shape.ttl", data_path="data/sample.ttl"):
    try:
        from pyshacl import validate
        from rdflib import Graph
    except ImportError:
        return False, "pyshacl/rdflib er ikke installert. Kjør: pip install pyshacl rdflib"

    sg = Graph().parse(shape_path, format="turtle")
    dg = Graph().parse(data_path, format="turtle")
    conforms, _vgraph, vtext = validate(
        dg,
        shacl_graph=sg,
        inference="rdfs",
        abort_on_first=False,
    )
    return bool(conforms), str(vtext)
