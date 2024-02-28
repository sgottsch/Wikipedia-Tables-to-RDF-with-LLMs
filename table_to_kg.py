import json
import os
import re
from datetime import datetime

import rdflib
from rdflib import Graph, RDFS, URIRef, Literal, XSD
from rdflib.plugins.parsers.notation3 import BadSyntax

from wikidata_connector import get_triples, get_wikidata_id
import openai

import urllib.parse

PRINT_INFO = False


def replace_dbpedia_with_wikidata(line, dbpedia_to_wikidata):
    if "<https://en.wikipedia.org/wiki/" in line:
        x = re.search(r'(<https://en.wikipedia.org/wiki/(.*?)>)', line)
        whole_link = x.group(1)
        name = urllib.parse.unquote(x.group(2))
        if name in dbpedia_to_wikidata:
            line = line.replace(whole_link, "wd:" + dbpedia_to_wikidata[name])
            line = line + " # " + name
        else:
            print("Missing Wikidata ID for", name)
            line = line.replace(whole_link, "wd:Delete")
            line = line + " # Delete"
    return line


def create_entity_graphs_prompt(links, all_property_labels, all_object_labels, all_prefix_lines):
    entity_graphs_prompt = ""

    for entity_no, entity in enumerate(links):
        print("Build graph for " + entity["link"])
        wikidata_id = get_wikidata_id(entity["link"], "en")

        if not wikidata_id:
            print("Error, missing Wikidata ID in input:", entity["link"])

        result_graph, property_labels, object_labels, prefix_lines = get_triples(entity["link"], entity["anchor_text"],
                                                                                 wikidata_id, "en")

        for key, value in property_labels.items():
            all_property_labels[key] = value
        for key, value in object_labels.items():
            all_object_labels[key] = value
        for prefix_line in prefix_lines:
            all_prefix_lines.add(prefix_line)
        # entity_graphs_prompt += "# Entity " + str(entity_no + 1) + "\n" + result_graph + "\n\n"
        entity_graphs_prompt += "\n" + result_graph + "\n"

    return entity_graphs_prompt


def create_triples(example_table, target_tables, example_entities, page_name, dbpedia_to_wikidata,
                   table_number, number_of_example_entities, config_dict,
                   evaluate_existing_entities=False, target_entities=None):
    output_folder = "data/evaluation/" + str(number_of_example_entities) + "_examples/"

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    if evaluate_existing_entities:
        output_folder += "existing_entities/"
    else:
        output_folder += "new_entities/"

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    if not os.path.exists(output_folder + "outputs"):
        os.makedirs(output_folder + "outputs")
    if not os.path.exists(output_folder + "prompts"):
        os.makedirs(output_folder + "prompts")
    if evaluate_existing_entities:
        if not os.path.exists(output_folder + "evaluation"):
            os.makedirs(output_folder + "evaluation")

    print("=== " + page_name + " ===")

    output_dict = {"config": config_dict}

    output_dict["table_with_only_examples"] = example_table
    output_dict["tables_without_examples"] = target_tables
    output_dict["links"] = example_entities
    if target_entities:
        output_dict["links_other"] = target_entities

    print("tables_without_examples", len(target_tables))

    triples_examples = []

    all_prefix_lines = set()
    # add some required prefixes in case they are missed by the LLM
    all_prefix_lines.add("@prefix wdt: <http://www.wikidata.org/prop/direct/> .")
    all_prefix_lines.add("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
    all_prefix_lines.add("@prefix wd: <http://www.wikidata.org/entity/> .")
    all_prefix_lines.add("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .")

    if number_of_example_entities > 0:
        all_property_labels = {}
        all_object_labels = {}
        entity_graphs_prompt = create_entity_graphs_prompt(example_entities, all_property_labels, all_object_labels,
                                                           all_prefix_lines)

        all_property_labels_strings = []
        for key, value in all_property_labels.items():
            all_property_labels_strings.append(key + " -> " + value)
        all_property_labels_string = "\n".join(all_property_labels_strings)

        all_object_labels_strings = []
        for key, value in all_object_labels.items():
            all_object_labels_strings.append(key + " -> " + value)
        all_object_labels_string = "\n".join(all_object_labels_strings)

        all_prefix_lines_strings = "\n".join(all_prefix_lines)

        output_dict["all_object_labels"] = all_object_labels
        output_dict["all_property_labels"] = all_property_labels

    output_dict["prompts"] = []
    other_lines = []

    for table_without_examples in target_tables:

        prompt_dict = {}
        output_dict["prompts"].append(prompt_dict)
        prompt_dict["table_without_examples"] = table_without_examples

        # if number_of_examples == 0:
        #    llm_prompt = ('''Your task is to create RDF triples in the Turtle format for entities described in a table from the Wikipedia page \"{0}\" in the Wikitext format. Only use information which is directly stated in the table. Return all triples for all entities that you can find, I do not want a partial representation. Do not return placeholders, only complete objects.
        #    \n---\nThis is the table for which you should extract RDF triples:\n\n{1}
        #    \n ---'''.format(article_name.replace("_", " "),
        #                     table_without_examples.strip()))
        # else:
        llm_prompt = '''Your task is to create RDF triples in the Turtle format for entities described in a table in the Wikitext format, given an example table from the Wikipedia page \"{0}\" and triples extracted from that example table. Only use information which is directly stated in the table. Return all triples for all entities that you can find, I do not want a partial representation. Do not return placeholders, only complete objects. If you provide a URL, the URL must be stated in the table.
---\nThis is the example table:\n\n{1}
---\nFor this example table, the following triples are created:\n\n{2}
---\nThese are the labels of the properties:\n\n{3}.
---\nThese are the labels of the objects:\n\n{4}.
---\nThis is the table for which you should extract RDF triples:\n\n{5}
---'''.format(page_name.replace("_", " "), example_table.strip(),
              all_prefix_lines_strings.strip() + "\n\n" + entity_graphs_prompt.strip(),
              all_property_labels_string.strip(), all_object_labels_string.strip(),
              table_without_examples.strip())

        with open(output_folder + "prompts/" + page_name + "_" + str(table_number) + ".txt", "w",
                  encoding="utf8") as file_prompt_txt:
            file_prompt_txt.write(llm_prompt)

        prompt_dict["prompt"] = llm_prompt

        # print(llm_prompt)

        print("Execute prompt... (" + datetime.today().strftime('%Y-%m-%d %H:%M:%S') + ")")
        completion = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            temperature=0,
            messages=[
                {"role": "system",
                 "content": "You are a helpful assistant designed to output valid Turtle Syntax for RDF. If you use xsd:integer or xsd:demical, the object must be a number."},
                {"role": "user", "content": llm_prompt}
            ]
        )

        result = completion.choices[0].message.content
        print(" ... Done. (" + datetime.today().strftime('%Y-%m-%d %H:%M:%S') + ")")

        prompt_dict["result"] = result

        for line in result.split("\n"):
            line = line.strip()
            if line.startswith("@prefix "):
                all_prefix_lines.add(line)
            else:
                if len(line) == 0 or "wd:" in line or "rdfs:" in line or "wdt:" in line or "xsd:" in line:

                    # ignore lines with unknown values
                    if "\"unknown\"" in line.lower():
                        if PRINT_INFO:
                            print("IGNORE", line)
                        if line.strip().endswith("."):
                            other_lines[len(other_lines) - 1] = other_lines[len(other_lines) - 1][:-1] + "."
                    else:
                        other_lines.append(line)
                elif not line.startswith("#"):
                    if PRINT_INFO:
                        print("Ignore:", line)

    ttl_filename = output_folder + "outputs/" + page_name + "_" + str(table_number) + ".ttl"

    with open(ttl_filename, "w", encoding="utf8") as f:
        for prefix_line in all_prefix_lines:
            f.write(prefix_line + "\n")
        for other_line_number, other_line in enumerate(other_lines):
            other_line = other_line.strip()
            if other_line.endswith(",") and len(other_lines) > other_line_number + 1 and other_lines[
                other_line_number + 1].startswith("wdt:"):
                print("Fix comma/semicolon error in " + other_line)
                other_line = other_line[:-1] + ";"
            if other_line.count("\"") > 2:
                print("Fix quotation error in " + other_line)
                # Convert  rdfs:label ""Left-Wing" Communism: An Infantile Disorder"@en ; into  rdfs:label "'Left-Wing' Communism: An Infantile Disorder"@en ;
                first_occurrence = other_line.find("\"")
                last_occurrence = other_line.rfind("\"")
                # Replace all occurrences of "x" except for the first and last
                other_line = other_line[:first_occurrence + 1] + other_line[
                                                                 first_occurrence + 1:last_occurrence].replace(
                    "\"", "'") + other_line[last_occurrence:]
            if "<" in other_line and not ("<http" in other_line or "<www" in other_line):
                print("Skip line with erroneous URLs: ", other_line)
                # Replace ";" with "." in previous line
                if other_line.endswith(".") and other_lines[other_line_number - 1].endswith(";"):
                    other_lines[other_line_number - 1] = other_lines[other_line_number - 1][:-1] + ";"
                continue
            if "example.org" in other_line:
                # replace space with underscore in subject identifier
                start_index = other_line.find("<https://example.org/resource/") + len("<https://example.org/resource/")
                end_index = other_line.find(">", start_index)
                substring_to_replace = other_line[start_index:end_index]
                replaced_substring = substring_to_replace.replace(" ", "_")
                other_line = other_line[:start_index] + replaced_substring + other_line[end_index:]
            other_line = replace_dbpedia_with_wikidata(other_line, dbpedia_to_wikidata)

            f.write(other_line + "\n")

    # load the TTL file once via RDFLib, delete triples with missing Wikidata IDs and safe again
    g = Graph()
    try:
        g.parse(ttl_filename)
    except BadSyntax:
        print("Bad syntax.")

    print("Triples:", len(g))
    g.remove((None, None, URIRef("http://www.wikidata.org/entity/Delete")))
    # g.remove((None, None, Literal("Unknown", datatype=XSD.decimal)))
    # g.remove((None, None, Literal("unknown", datatype=XSD.decimal)))
    # g.remove((None, None, Literal("Unknown", datatype=XSD.integer)))
    # g.remove((None, None, Literal("unknown", datatype=XSD.integer)))
    print("Triples after cleaning:", len(g))
    g.serialize(destination=ttl_filename)
    predicted_triples = g.serialize(format='nt')

    if PRINT_INFO:
        print("PREDICTED")
        print(predicted_triples)

    with open(output_folder + "prompts/" + page_name + "_" + str(table_number) + ".json", "w") as fp:
        json.dump(output_dict, fp)

    if evaluate_existing_entities:
        # Evaluation

        with open(output_folder + "evaluation/" + page_name + "_" + str(table_number) + ".txt",
                  "w", encoding="utf8") as file_evaluation:

            entity_graphs_prompt_other = "\n".join(all_prefix_lines) + "\n" + create_entity_graphs_prompt(target_entities,
                                                                                                          all_property_labels,
                                                                                                          all_object_labels,
                                                                                                          all_prefix_lines)
            g_ground = Graph()
            entity_graphs_prompt_other_wd_links = ""
            for line in entity_graphs_prompt_other.split("\n"):
                if line.count("\"") > 2:
                    print("Fix quotation error in " + other_line)
                    # Convert  rdfs:label ""Left-Wing" Communism: An Infantile Disorder"@en ; into  rdfs:label "'Left-Wing' Communism: An Infantile Disorder"@en ;
                    first_occurrence = line.find("\"")
                    last_occurrence = line.rfind("\"")
                    # Replace all occurrences of "x" except for the first and last
                    line = line[:first_occurrence + 1] + line[
                                                         first_occurrence + 1:last_occurrence].replace(
                        "\"", "'") + line[last_occurrence:]

                entity_graphs_prompt_other_wd_links += replace_dbpedia_with_wikidata(line, dbpedia_to_wikidata) + "\n"

            if PRINT_INFO:
                print("GROUND2")
                print(entity_graphs_prompt_other_wd_links)

            g_ground.parse(data=entity_graphs_prompt_other_wd_links)
            g_ground.remove((None, None, URIRef("http://www.wikidata.org/entity/Delete")))
            ground_triples = g_ground.serialize(format='nt')

            if PRINT_INFO:
                print("GROUND")
                print(ground_triples)

            all_triple_strings_predicted = set(predicted_triples.split("\n"))
            all_triple_strings_predicted.remove("")
            all_triple_strings_ground = set(ground_triples.split("\n"))
            all_triple_strings_ground.remove("")

            common_triples = all_triple_strings_predicted.intersection(all_triple_strings_ground)
            only_predicted = all_triple_strings_predicted.difference(all_triple_strings_ground)
            only_ground = all_triple_strings_ground.difference(all_triple_strings_predicted)

            if PRINT_INFO:
                print("In both")
            file_evaluation.write("In both" + "\n")
            for triple in common_triples:
                if PRINT_INFO:
                    print(triple)
                file_evaluation.write(triple + "\n")

            if PRINT_INFO:
                print("In ground only")
            file_evaluation.write("In ground only" + "\n")
            for triple in only_ground:
                if PRINT_INFO:
                    print(triple)
                file_evaluation.write(triple + "\n")

            if PRINT_INFO:
                print("In predicted only")
            file_evaluation.write("In predicted only" + "\n")
            for triple in only_predicted:
                if PRINT_INFO:
                    print(triple)
                file_evaluation.write(triple + "\n")

            precision = 1
            if len(all_triple_strings_predicted) > 0:
                precision = len(common_triples) / (len(all_triple_strings_predicted))

            recall = 0
            if len(all_triple_strings_ground) > 0:
                recall = len(common_triples) / (len(all_triple_strings_ground))

            f1 = 0
            if precision + recall > 0:
                f1 = (2 * precision * recall) / (precision + recall)

            eval_dict = {"config": config_dict, "in_both": len(common_triples),
                         "in_ground": len(all_triple_strings_ground), "in_predicted": len(all_triple_strings_predicted),
                         "in_ground_only": len(only_ground), "in_predicted_only": len(only_predicted),
                         "recall": recall,
                         "precision": precision,
                         "f1": f1}

            with open(output_folder + "evaluation/" + page_name + "_" + str(table_number) + ".json",
                      "w") as file_evaluation_json:
                json.dump(eval_dict, file_evaluation_json)

            print("Recall:", recall)
            print("Precision:", precision)
            print("F1:", f1)


'''
if __name__ == "__main__":
    article_name = "List_of_churches_in_London"
    article_content = download_article(article_name)
    table = get_tables(article_content)[0]

    dbpedia_to_wikidata = get_dbpedia_to_wikidata_mapping()

    create_triples(table, article_name, dbpedia_to_wikidata, 0)
'''
