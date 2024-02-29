from rdflib import Graph, RDFS

from table_to_kg import create_triples
from wiki_downloader import download_article, get_tables, split_table_for_new_entities
from wikidata_dbpedia_mapper import get_dbpedia_to_wikidata_mapping


def extract_triples_for_wikipedia_article(page_name, table_number, number_of_examples, dbpedia_to_wikidata,
                                          ttl_filename):
    article_content = download_article(page_name)
    tables = get_tables(article_content)

    table = tables[table_number]

    example_table, target_table, example_entities, number_of_target_entities = split_table_for_new_entities(
        table, number_of_examples, 3, 6, 10, dbpedia_to_wikidata)

    create_triples(page_name,table_number,example_table, target_table, example_entities,
                   dbpedia_to_wikidata, number_of_examples, ttl_filename)


def explore_graph(file_name):
    g = Graph()
    g.parse(file_name)

    print("Number of triples:", len(g))

    print("--- Triples with rdfs:label ---")
    for s, p, o in g.triples((None, RDFS.label, None)):
        print(s, p, o)


if __name__ == "__main__":
    ttl_filename = "examples/example_churches_in_london.ttl"
    dbpedia_to_wikidata = get_dbpedia_to_wikidata_mapping()
    extract_triples_for_wikipedia_article(page_name="List of churches in London", table_number=0,
                                          number_of_examples=4, dbpedia_to_wikidata=dbpedia_to_wikidata,
                                          ttl_filename=ttl_filename)
    explore_graph(ttl_filename)
