import csv
import json
import os
import traceback
from datetime import datetime

from table_to_kg import create_triples
from wiki_downloader import download_article, get_tables, remove_example_rows, split_table_for_new_entities, \
    split_table_for_existing_entities
from wikidata_dbpedia_mapper import get_dbpedia_to_wikidata_mapping

MAX_NUMBER_OF_EXAMPLES = 3


def run_experiments():
    dbpedia_to_wikidata = get_dbpedia_to_wikidata_mapping()

    max_number_of_examples = 8
    min_number_of_rows_without_examples_required = 2
    max_number_of_batches = 10

    for number_of_examples in [8,7,6,5,4,3,2,1]:  # [1, 2, 3, 4, 5, 6, 7, 8]:#[1 , 2, 3, 4, 5]:

        print("=== Number of examples: " + str(number_of_examples) + "===\n")

        file_name_done_tables = "data/evaluation/" + str(number_of_examples) + "_examples/"
        if not os.path.exists(file_name_done_tables):
            os.makedirs(file_name_done_tables)
        file_name_done_tables += "existing_entities/"
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

        total_number_of_target_entities = 0
        total_number_of_tables = 0

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
                    print("Skip article: " + article_name + " - Already done.")
                    continue

                # if article_name != "List_of_museums_in_Central_Texas":
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

                    # if table_number != 2: # and table_number != 4 and table_number != 5:
                    #    continue

                    table = tables[table_number]

                    config_dict = {"article_name": article_name, "table_number": table_number,
                                   "number_of_examples": number_of_examples,
                                   "max_number_of_examples": max_number_of_examples,
                                   "min_number_of_rows_without_examples_required": min_number_of_rows_without_examples_required,
                                   "time": datetime.today().strftime('%Y-%m-%d %H:%M:%S')}

                    example_table, target_table, example_entities, target_entities, number_of_target_entities = split_table_for_existing_entities(
                        table, number_of_examples, max_number_of_examples, min_number_of_rows_without_examples_required,
                        6, max_number_of_batches, dbpedia_to_wikidata)

                    if not example_table:
                        print("Skip table.")
                        file_log.write("\t".join(["Table", article_name, str(table_number), "Skipped",
                                                  datetime.today().strftime('%Y-%m-%d %H:%M:%S')]) + "\n")
                        file_log.flush()
                        continue

                    config_dict["number_of_target_entities"] = number_of_target_entities
                    total_number_of_target_entities += number_of_target_entities
                    total_number_of_tables += 1

                    try:
                        create_triples(example_table, target_table, example_entities, article_name,
                                       dbpedia_to_wikidata, table_number, number_of_examples, config_dict,
                                       evaluate_existing_entities=True, target_entities=target_entities)
                    except Exception as e:
                        print("Error with table:", e)
                        errors_in_article = True
                        traceback.print_exc()
                        file_log.write("\t".join(["Table", article_name, str(table_number), "Error",
                                                  datetime.today().strftime('%Y-%m-%d %H:%M:%S')]) + "\n")
                        file_log.flush()
                        continue

                    file_log.write("\t".join(["Table", article_name, str(table_number), "Done",
                                              datetime.today().strftime('%Y-%m-%d %H:%M:%S')]) + "\n")
                    file_log.flush()

                if not errors_in_article:
                    file_log.write("\t".join(
                        ["Article", article_name, "", "Done", datetime.today().strftime('%Y-%m-%d %H:%M:%S')]) + "\n")
                file_log.flush()

        print("total_number_of_target_entities:", total_number_of_target_entities)
        print("total_number_of_tables:", total_number_of_tables)

        file_log.close()


def get_results():
    outputs_micro = []
    outputs_macro = []

    for number_of_examples in [1, 2, 3, 4, 5, 6, 7, 8]:

        print("\n=== Number of examples:" + str(number_of_examples) + " ===\n")

        number_of_tables = 0
        in_both = 0
        in_ground_only = 0
        in_ground = 0
        in_predicted_only = 0
        in_predicted = 0
        precision_sum = 0
        recall_sum = 0
        f1_sum = 0

        for file_name in os.listdir(
                "data/evaluation/" + str(number_of_examples) + "_examples/existing_entities/evaluation/"):
            if file_name.endswith(".json"):
                with open("data/evaluation/" + str(
                        number_of_examples) + "_examples/existing_entities/evaluation/" + file_name) as json_file:
                    json_res = json.load(json_file)
                    in_both += json_res["in_both"]
                    in_ground_only += json_res["in_ground_only"]
                    in_ground += json_res["in_ground"]
                    in_predicted_only += json_res["in_predicted_only"]
                    in_predicted += json_res["in_predicted"]
                    precision_sum += json_res["precision"]
                    recall_sum += json_res["recall"]
                    f1_sum += json_res["f1"]
                    number_of_tables += 1

        print("Micro")
        micro_precision = in_both / in_predicted
        micro_recall = in_both / in_ground
        micro_f1 = (2 * micro_precision * micro_recall) / (micro_precision + micro_recall)
        print("Recall:", micro_recall)
        print("Precision:", micro_precision)
        print("F1:", micro_f1)

        outputs_micro.append(
            str(number_of_examples) + "\t" + str(micro_precision) + "\t" + str(micro_recall) + "\t" + str(
                micro_f1) + "\t" + str(in_predicted))

        print("Macro")
        macro_precision = precision_sum / number_of_tables
        macro_recall = recall_sum / number_of_tables
        macro_f1 = f1_sum / number_of_tables
        print("Recall:", macro_recall)
        print("Precision:", macro_precision)
        print("F1:", macro_f1)

        outputs_macro.append(
            str(number_of_examples) + "\t" + str(macro_precision) + "\t" + str(macro_recall) + "\t" + str(
                macro_f1) + "\t" + str(in_predicted))

        print("Number of tables:", number_of_tables)
        print("Number of triples:", in_predicted)

    print("\n".join(outputs_micro))
    print("\n".join(outputs_macro))


if __name__ == "__main__":
    run_experiments()
    #get_results()
