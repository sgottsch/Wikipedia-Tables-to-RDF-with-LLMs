import json
import time
import urllib
from urllib.error import URLError, HTTPError

from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("https://query.wikidata.org/sparql")

prefixes = {"wd:": "http://www.wikidata.org/entity/", "rdfs:": "http://www.w3.org/2000/01/rdf-schema#",
            "schema:": "http://schema.org/",
            "wdt:": "http://www.wikidata.org/prop/direct/", "skos:": "http://www.w3.org/2004/02/skos/core#",
            "xsd:": "http://www.w3.org/2001/XMLSchema#"}
for language in ["en", "de", "fr"]:  # TODO: can be easily extended to all languages
    prefixes[language + "wiki:"] = "https://" + language + ".wikipedia.org/wiki/"


def get_wikidata_id_by_sparql(dbpedia_id: str, language="en"):
    sparql.setQuery("""
    SELECT DISTINCT ?wikidata_id WHERE {
      ?article schema:about ?wikidata_id .
      ?article	schema:isPartOf	<https://@lang@.wikipedia.org/> .
      ?article  schema:name "@article_name@"@@lang@ .
    } LIMIT 1
    """.replace("@lang@", language).replace("@article_name@", dbpedia_id.replace("_", " ")))
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    print(results)

    try:
        wikidata_id = results["results"]["bindings"][0]["wikidata_id"]["value"].replace(
            "http://www.wikidata.org/entity/", "")
    except IndexError:
        return None

    return wikidata_id


def get_wikidata_id(dbpedia_id: str, language="en"):
    # see https://en.wikipedia.org/wiki/Wikipedia:Finding_a_Wikidata_ID
    url = "https://" + language + ".wikipedia.org/w/api.php?action=query&prop=pageprops&titles=" + urllib.parse.quote(
        dbpedia_id) + "&format=json&redirects=1"

    number_of_retries = 0

    while True:
        try:
            with urllib.request.urlopen(url) as url_res:
                data = json.load(url_res)
                try:
                    for page_id in data["query"]["pages"]:
                        wikidata_id = data["query"]["pages"][page_id]["pageprops"]["wikibase_item"]
                    return wikidata_id
                except KeyError:
                    return None
        except URLError as err:
            if number_of_retries <= 5:
                print("Error:", err)
                print(" Retry in 10 seconds.")
                time.sleep(10)
                number_of_retries += 1
                continue
            else:
                raise err


def convert_to_prefixed(value):
    for ns, prefix in prefixes.items():
        if value.startswith(prefix):
            return value.replace(prefix, ns)
    return value


def get_triples(dbpedia_id, anchor_text, wikidata_id, language):

    # other potential properties: skos:altLabel

    sparql.setQuery("""
SELECT DISTINCT ?p ?propertyLabel ?o ?oArticle ?oLabel WHERE {
wd:""" + wikidata_id + """ ?p ?o .
  
  FILTER(STRSTARTS(STR(?p), STR(wdt:)) || ?p in (rdfs:label)) .
  FILTER(!isLiteral(?o) || isNumeric(?o) || lang(?o) = "en" || datatype(?o) = xsd:dateTime || datatype(?o) = xsd:date || datatype(?o) = xsd:time) .
  
OPTIONAL {
      ?oArticle schema:about ?o .
      ?oArticle	schema:isPartOf	<https://""" + language + """.wikipedia.org/> .
} 
  
  OPTIONAL {
?property wikibase:directClaim ?p  .
}
SERVICE wikibase:label { bd:serviceParam wikibase:language \"""" + language + """\". }
}
    """)
    # print(sparql.queryString)
    sparql.setReturnFormat(JSON)

    number_of_retries = 0

    while True:
        try:
            results = sparql.query().convert()
            break
        except HTTPError as err:
            if number_of_retries <= 5:
                print("Error:", err)
                print(" Retry in 10 seconds.")
                time.sleep(10)
                number_of_retries += 1
                continue
            else:
                raise err

    triples = []
    property_labels = {}
    object_labels = {}

    # s = language + "wiki:" + dbpedia_id.replace(" ","_")
    # avoid some URL-specific characters

    s = "<https://example.org/resource/" + anchor_text.replace(" ", "_").replace("\"", "").replace("|", "-").replace("<","_").replace(">","_") + ">"

    try:
        for res in results["results"]["bindings"]:

            p = convert_to_prefixed(res["p"]["value"])

            o_type = res["o"]["type"]

            o = res["o"]["value"]
            if o_type == "uri":
                if o.startswith("http://www.wikidata.org/entity/"):
                    if "oArticle" in res:
                        # o = convert_to_prefixed(res["oArticle"]["value"])
                        o = "<" + res["oArticle"]["value"] + ">"
                    else:
                        o = o.replace("http://www.wikidata.org/entity/", "wd:")
                        if "oLabel" in res:
                            object_labels[o] = res["oLabel"]["value"]
                else:
                    o = "<" + o + ">"
            elif o_type == "literal":
                o = "\"" + res["o"]["value"] + "\""
                if "xml:lang" in res["o"]:
                    o += "@" + res["o"]["xml:lang"]
                elif "datatype" in res["o"]:
                    datatype = res["o"]["datatype"]
                    if datatype.startswith("http://www.w3.org/2001/XMLSchema#"):
                        o += "^^xsd:" + res["o"]["datatype"].replace("http://www.w3.org/2001/XMLSchema#", "")
                    else:
                        o += "^^<" + res["o"]["datatype"] + ">"

            triple = " ".join([s, p, o]) + " ."
            triples.append(triple)

            if "propertyLabel" in res:
                property_labels[p] = res["propertyLabel"]["value"]
    except IndexError:
        return None

    # shorten query by skipping repeating subject
    result_graph = "\n".join(
        [triples[0].replace(" .", " ;")] + [triple.replace(s, "").replace(" .", " ;") for triple in triples[1:-1]] + [
            triples[-1].replace(s, "")])

    prefix_lines = []

    for ns, prefix in prefixes.items():
        if ns in result_graph:
            prefix_lines.append("@prefix " + ns + " <" + prefix + "> .")

    result_graph = result_graph

    return result_graph, property_labels, object_labels, prefix_lines


if __name__ == "__main__":
    wikidata_id = get_wikidata_id("Berlinale", "en")
    result_graph, property_labels, object_labels, prefix_lines = get_triples(wikidata_id, "en")
    print(result_graph)
    print(property_labels)
    print(object_labels)
#    print(get_wikidata_id("Berlinale", "en"))
#    print(get_wikidata_id("Berlinale", "de"))
