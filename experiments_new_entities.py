import csv
import json
import os
import traceback
from datetime import datetime

from rdflib import Graph, RDFS, Literal, URIRef

from table_to_kg import create_triples
from wiki_downloader import download_article, get_tables, remove_example_rows, split_table_for_new_entities
from wikidata_dbpedia_mapper import get_dbpedia_to_wikidata_mapping

MAX_NUMBER_OF_EXAMPLES = 3


def run_experiments():
    dbpedia_to_wikidata = get_dbpedia_to_wikidata_mapping()

    number_of_examples = 5

    number_of_tables = 0

    total_number_of_target_entities = 0

    file_name_done_tables = "data/evaluation/" + str(number_of_examples) + "_examples/"
    if not os.path.exists(file_name_done_tables):
        os.makedirs(file_name_done_tables)
    file_name_done_tables += "new_entities/"
    if not os.path.exists(file_name_done_tables):
        os.makedirs(file_name_done_tables)
    file_name_done_tables += "log.txt"
    if not os.path.exists(file_name_done_tables):
        with open(file_name_done_tables, 'w'): pass

    done_articles = set()
    done_tables = set()

    if not os.path.exists(file_name_done_tables):
        with open(file_name_done_tables, 'w'): pass

    with open(file_name_done_tables) as file_log:
        reader = csv.reader(file_log, delimiter="\t", quotechar='"')
        for row in reader:
            if row[0] == "Article" and row[3] != "Error":
                done_articles.add(row[1])
            if row[0] == "Table" and row[3] != "Error":
                done_tables.add(row[1] + "_" + row[2])

    print("done_articles:", done_articles)
    print("done_tables:", done_tables)

    file_log = open(file_name_done_tables, 'a+')  # open file in append mode

    with open("data/wikipedia_list_tables.tsv") as fd:
        reader = csv.reader(fd, delimiter="\t", quotechar='"')
        next(reader, None)
        for row in reader:
            wikipedia_page = row[0]
            table_numbers = [int(id) for id in row[1].split(", ")]
            page_id = None
            if len(row) > 2:
                page_id = row[2]
            article_name = wikipedia_page.replace("https://en.wikipedia.org/wiki/", "")

            if article_name in done_articles:
                print("Article name: Already done.")
                continue

            #if article_name != "List_of_churches_in_London":
            #    continue

            print("Article name:", article_name, "-> Table numbers:", table_numbers)

            article_content = download_article(article_name, page_id)
            tables = get_tables(article_content)

            errors_in_article = False

            for table_number in table_numbers:

                print("--- Table number: " + str(table_number) + " ---\n")

                if article_name + "_" + str(table_number) in done_tables:
                    print("Table " + str(table_number) + ": Already done.")
                    continue

                table = tables[table_number]

                config_dict = {"article_name": article_name, "table_number": table_number,
                               "number_of_examples": number_of_examples,
                               "time": datetime.today().strftime('%Y-%m-%d %H:%M:%S')}

                example_table, target_table, example_entities, number_of_target_entities = split_table_for_new_entities(
                    table,
                    number_of_examples,
                    3, 6,
                    10, dbpedia_to_wikidata)

                if not example_table:
                    print("Skip table.")
                    file_log.write("\t".join(["Table", article_name, str(table_number), "Skipped"]) + "\n")
                    file_log.flush()
                    continue

                config_dict["number_of_target_entities"] = number_of_target_entities

                total_number_of_target_entities += number_of_target_entities

                try:
                    create_triples(example_table, target_table, example_entities, article_name,
                                   dbpedia_to_wikidata,
                                   table_number, number_of_examples, config_dict)
                except Exception as e:
                    print("Error with table:", e)
                    errors_in_article = True
                    traceback.print_exc()
                    file_log.write("\t".join(["Table", article_name, str(table_number), "Error"]) + "\n")
                    file_log.flush()
                    continue

                file_log.write("\t".join(["Table", article_name, str(table_number), "Done"]) + "\n")
                file_log.flush()

            if not errors_in_article:
                file_log.write("\t".join(["Article", article_name, "", "Done"]) + "\n")
                file_log.flush()

    print("number_of_tables:", number_of_tables)
    print("total_number_of_target_entities:", total_number_of_target_entities)
    file_log.close()


def get_results():
    number_of_examples = 5

    subjects = set()
    subjects2 = []

    properties = set()
    property_distribution = {}

    number_of_tables = 0
    number_of_triples = 0
    number_of_literals = 0
    number_of_non_literals = 0
    literal_datatypes_distribution = {}

    for file_name in os.listdir("data/evaluation/" + str(number_of_examples) + "_examples/new_entities/outputs/"):
        if file_name.endswith(".ttl"):

            print("- " + file_name)

            g = Graph()

            g.parse("data/evaluation/" + str(number_of_examples) + "_examples/new_entities/outputs/" + file_name)

            for s, p, o in g.triples((None, None, None)):
                print(s,p,o)
                subjects.add(s)
                subjects2.append(s)
                properties.add(p)
                number_of_triples += 1
                if p in property_distribution:
                    property_distribution[p] = property_distribution[p] + 1
                else:
                    property_distribution[p] = 1
                if isinstance(o, URIRef):
                    number_of_non_literals += 1
                elif isinstance(o, Literal):
                    number_of_literals += 1
                    if o.datatype not in literal_datatypes_distribution:
                        literal_datatypes_distribution[o.datatype] = 1
                    else:
                        literal_datatypes_distribution[o.datatype] = literal_datatypes_distribution[o.datatype] + 1
                else:
                    print("???")

            number_of_tables += 1

    number_of_target_entities = 0
    for file_name in os.listdir("data/evaluation/" + str(number_of_examples) + "_examples/new_entities/prompts/"):
        if file_name.endswith(".json"):
            with open("data/evaluation/" + str(number_of_examples) + "_examples/new_entities/prompts/" + file_name) as f:
                json_prompt = json.load(f)
                number_of_target_entities += json_prompt["config"]["number_of_target_entities"]
                print(json_prompt["config"]["number_of_examples"])

    print("\nTables:", number_of_tables)
    print("Target entities:", number_of_target_entities)
    print("Properties:", len(properties))
    print("Subjects:", len(subjects))

    print("Triples:", number_of_triples)
    print("Literal:", number_of_literals)
    print("Non-literals:", number_of_non_literals)

    print("\nProperty Distribution:")
    a1_sorted_keys = sorted(property_distribution, key=property_distribution.get, reverse=True)
    for r in a1_sorted_keys:
        print(r, property_distribution[r])

    print("\nLiteral Datatypes Distribution:")
    a1_sorted_keys = sorted(literal_datatypes_distribution, key=literal_datatypes_distribution.get, reverse=True)
    for r in a1_sorted_keys:
        print(r, literal_datatypes_distribution[r])


if __name__ == "__main__":
    #run_experiments()
    get_results()
