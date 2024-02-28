import os

from rdflib import Graph, RDF, RDFS, Literal, XSD

if __name__ == "__main__":

    subjects = set()
    properties = set()
    property_distribution = {}

    folder_name = "data/evaluation/3_examples/new_entities/outputs/"

    for file in os.listdir(folder_name):
        if file.endswith(".ttl") and "Malaysia_0" in file:

            print("=== " + file + "===")

            g = Graph()

            g.parse(folder_name + file)
            print(len(g))
            g.remove((None, None, Literal("Unknown", datatype=XSD.decimal)))
            print(len(g))

            for s, _, o in g.triples((None, RDFS.label, None)):
                print(s, o)

            for s, p, o in g.triples((None, None, None)):
                subjects.add(s)
                properties.add(p)
                if p in property_distribution:
                    property_distribution[p] = property_distribution[p] + 1
                else:
                    property_distribution[p] = 1

    print("Properties:", len(properties))
    print("Subjects:", len(subjects))

    print("Property Distribution:")
    a1_sorted_keys = sorted(property_distribution, key=property_distribution.get, reverse=True)
    for r in a1_sorted_keys:
        print(r, property_distribution[r])