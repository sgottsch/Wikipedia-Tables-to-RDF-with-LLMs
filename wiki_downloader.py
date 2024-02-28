import re
import urllib.request, urllib.error
import time

from mediawiki import MediaWiki


def download_article(article_name, page_id=None):
    wikipedia = MediaWiki(lang="en", user_agent='pyMediaWiki, WikiTableToKGViaLLM (gottschalk@L3S.de)')

    if page_id:
        p = wikipedia.page(pageid=page_id)
    else:
        p = wikipedia.page(article_name)

    return p.wikitext


def get_tables(input_string):
    input_string = input_string.replace("sortable ", "")
    input_string = input_string.replace(" sortable", "")
    pattern = r'\{\| ?class="?wikitable(.*?)\|\}'
    matches = re.findall(pattern, input_string, re.DOTALL)

    tables = []
    for re_match in matches:
        tables.append("{| class=\"wikitable " + re_match.strip() + " |}")

    return tables


def wikipedia_page_exists(article_name, dbpedia_to_wikidata):
    if article_name.replace(" ", "_") in dbpedia_to_wikidata:
        return True

    number_of_retries = 0

    while True:
        # our index has no redirects, so we call Wikipedia
        try:
            url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(article_name.replace(" ", "_"))
            urllib.request.urlopen(url).getcode()
            return True
        except urllib.error.HTTPError:
            return False
        except urllib.error.URLError as err:
            if number_of_retries <= 5:
                print("Error:", err)
                print(" Retry in 10 seconds.")
                number_of_retries += 1
                time.sleep(10)
                continue
            else:
                raise err


def remove_example_rows(table, max_number_of_examples, max_number_of_rows_without_links, evaluate_existing_entities,
                        dbpedia_to_wikidata):
    table_with_only_examples = []
    tables_without_examples = []

    links = []
    other_links = []

    number_of_examples = 0

    link_pattern = re.compile(r'\[\[.*?\]\]')

    # split table in start and list of rows
    current_row = []

    start_lines = []
    rows = []
    started_rows = False
    current_row_is_header = False
    header_was_seen = False

    for line in table.split("\n"):
        if not started_rows and not line.startswith("|-"):
            start_lines.append(line)
        else:
            if line.startswith("|-"):
                if current_row_is_header:
                    for row in current_row:
                        start_lines.append(row)
                    header_was_seen = True
                else:
                    rows.append(current_row)
                current_row_is_header = False
                started_rows = True
                current_row = []
            if line.startswith("!") and not header_was_seen:
                current_row_is_header = True
            current_row.append(line)

    if current_row:
        rows.append(current_row)
    table_with_only_examples += start_lines

    number_of_rows_without_examples = 0
    table_without_examples = []
    table_without_examples += start_lines
    number_of_rows_in_current_table_without_examples = 0

    for row in rows:

        added_new_row_without_example = False

        if not row or len(row) < 2:
            continue

        row_link = row[1]
        row_link = row_link.replace("!scope=\"row\"", "").strip()

        if row_link.count("|") > 1:
            # check if there is style information to be removed
            parts = row_link.split("|")
            if "width=\"" in parts[1] or "align=\"" in parts[1] or "style=\"" in parts[1]:
                del parts[1]
                row_link = "|".join(parts)

        row_link = row_link.strip()
        if row_link.startswith("| [[") or row_link.startswith("|[[") or row_link.startswith(
                "| ''[[") or row_link.startswith("|''[["):
            link = re.findall(link_pattern, row_link)[0].replace("[[", "").replace("]]", "").strip()
            if "|" in link:
                parts = link.split("|")
                link = parts[0].strip()
                link_anchor = parts[1].strip()
            else:
                link_anchor = link

            if "#" not in link:
                if number_of_examples < max_number_of_examples and wikipedia_page_exists(link,
                                                                                         dbpedia_to_wikidata):  # ignore links like Upper_Clapton#The_Abode_of_Love
                    table_with_only_examples += [line for line in row]
                    links.append({"link": link.replace(" ", "_"), "anchor_text": link_anchor})
                    number_of_examples += 1
                elif evaluate_existing_entities and number_of_examples >= max_number_of_examples and wikipedia_page_exists(
                        link, dbpedia_to_wikidata):
                    table_without_examples += [line for line in row]
                    number_of_rows_without_examples += 1
                    number_of_rows_in_current_table_without_examples += 1
                    other_links.append({"link": link.replace(" ", "_"), "anchor_text": link_anchor})
                    added_new_row_without_example = True
        elif not evaluate_existing_entities:
            table_without_examples += [line for line in row]
            number_of_rows_without_examples += 1
            number_of_rows_in_current_table_without_examples += 1
            added_new_row_without_example = True

        if added_new_row_without_example and number_of_rows_without_examples % max_number_of_rows_without_links == 0:
            if table_without_examples:
                table_without_examples_str = "\n".join(table_without_examples).strip()
                if not table_without_examples_str.endswith("|}"):
                    table_without_examples_str += " |}"
                tables_without_examples.append(table_without_examples_str)

            table_without_examples = []
            table_without_examples += start_lines
            number_of_rows_in_current_table_without_examples = 0

    table_with_only_examples_str = "\n".join(table_with_only_examples).strip()

    if not table_with_only_examples_str.endswith("|}"):
        table_with_only_examples_str += " |}"

    if number_of_rows_in_current_table_without_examples > 0:
        table_without_examples_str = "\n".join(table_without_examples).strip()
        if not table_without_examples_str.endswith("|}"):
            table_without_examples_str += " |}"
        tables_without_examples.append(table_without_examples_str)

    return table_with_only_examples_str, tables_without_examples, links, other_links


def create_table(start_lines, content_rows):
    table_lines = []
    table_lines += start_lines
    for content_row in content_rows:
        for content_line in content_row:
            table_lines.append(content_line)

    table = "\n".join(table_lines).strip()
    if not table.endswith("|}"):
        table += " |}"

    return table


def split_table_for_new_entities(table, number_of_examples, min_number_of_examples_required, number_of_tables_per_batch,
                                 max_number_of_batches,
                                 dbpedia_to_wikidata):
    start_lines, rows_with_linked_examples, rows_without_examples, example_entities = split_table(table,
                                                                                       dbpedia_to_wikidata)

    if len(rows_with_linked_examples) < min_number_of_examples_required:
        print("Not enough rows with examples.", len(rows_with_linked_examples))
        return None, None, None, None

    example_table = create_table(start_lines, rows_with_linked_examples[:number_of_examples])
    example_entities = example_entities[:number_of_examples]
    target_table = []
    create_table(start_lines, rows_with_linked_examples[:number_of_examples])

    for i in range(0, len(rows_without_examples), number_of_tables_per_batch):
        target_table.append(
            create_table(start_lines, rows_without_examples[i:i + number_of_tables_per_batch]))
        if len(target_table) >= max_number_of_batches:
            print("Reached limit. Only use the first " + str(
                max_number_of_batches * number_of_tables_per_batch) + " rows for entity creation.")
            break

    number_of_target_entities = min(len(rows_without_examples), max_number_of_batches * number_of_tables_per_batch)

    return example_table, target_table, example_entities, number_of_target_entities


def split_table_for_existing_entities(table, number_of_examples, max_number_of_examples,
                                      min_number_of_rows_without_examples_required, number_of_tables_per_batch,
                                      max_number_of_batches,
                                      dbpedia_to_wikidata):
    start_lines, rows_with_linked_examples, _, links = split_table(table, dbpedia_to_wikidata)

    # minimum table size: max_number_of_examples + min_number_of_rows_without_examples_required
    if len(rows_with_linked_examples) < max_number_of_examples + min_number_of_rows_without_examples_required:
        print("Not enough rows with examples.", len(rows_with_linked_examples))
        return None, None, None, None, None

    example_table = create_table(start_lines, rows_with_linked_examples[:number_of_examples])
    example_entities = links[:number_of_examples]

    target_entities = links[number_of_examples:]

    if len(target_entities) > max_number_of_batches * number_of_tables_per_batch:
        print("Reached limit. Only use the first " + str(
            max_number_of_batches * number_of_tables_per_batch) + " rows for entity creation.")
        target_entities = target_entities[:max_number_of_batches * number_of_tables_per_batch]

    tables_without_examples = []
    for i in range(max_number_of_examples, len(rows_with_linked_examples), number_of_tables_per_batch):
        tables_without_examples.append(
            create_table(start_lines, rows_with_linked_examples[i:i + number_of_tables_per_batch]))
        if len(tables_without_examples) >= max_number_of_batches:
            break
        # links_other.append(links[i:i + number_of_tables_per_batch])

    number_of_target_entities = min(len(target_entities), max_number_of_batches * number_of_tables_per_batch)

    return example_table, tables_without_examples, example_entities, target_entities, number_of_target_entities


def row_link_is_not_forbidden(row_link, forbidden_links):
    # ignore links to Wiktionary etc
    for forbidden_link in forbidden_links:
        if forbidden_link in row_link:
            return False
    return True


def split_table(table, dbpedia_to_wikidata):

    # Create three types of tables:
    # - with "max_number_of_examples" linked examples
    # - with other linked examples (group of tables to reduce prompt size)
    # - without examples (group of tables to reduce prompt size)

    forbidden_links = set()

    wiki_lang_codes = ["en", "es", "fr", "de", "it", "ja", "ko", "zh", "ru", "ar", "pt", "hi", "nl", "sv", "fi", "tr",
                       "id", "pl", "he", "uk"]
    # see https://en.wikipedia.org/wiki/Help:Interwiki_linking
    for wiki_category in ["simple", "wikt", "wikiquote", "q", "s", "wikisource", "b", "wikibooks", "wikinews", "n",
                          "wikidata", "d", "mediawikiwiki", "mw", "commons", "c"] + wiki_lang_codes:
        forbidden_links.add("[[" + wiki_category + ":")
        forbidden_links.add("[[:" + wiki_category + ":") # rare case

    links = []

    rows_with_linked_examples = []
    rows_without_examples = []

    number_of_examples = 0

    link_pattern = re.compile(r'\[\[.*?\]\]')

    # split table in start and list of rows
    current_row = []

    start_lines = []
    rows = []
    started_rows = False
    current_row_is_header = False
    header_was_seen = False

    for line in table.split("\n"):
        if not started_rows and not line.startswith("|-"):
            start_lines.append(line)
        else:
            if line.startswith("|-"):
                if current_row_is_header:
                    for row in current_row:
                        start_lines.append(row)
                    header_was_seen = True
                else:
                    rows.append(current_row)
                current_row_is_header = False
                started_rows = True
                current_row = []
            if line.startswith("!") and not header_was_seen:
                current_row_is_header = True
            current_row.append(line)

    if current_row:
        rows.append(current_row)

    for row in rows:

        if not row or len(row) < 2:
            continue

        row_link = row[1]
        row_link = row_link.replace("!scope=\"row\"", "").strip()

        if row_link.count("|") > 1:
            # check if there is style information to be removed
            parts = row_link.split("|")
            if "width=\"" in parts[1] or "align=\"" in parts[1] or "style=\"" in parts[1]:
                del parts[1]
                row_link = "|".join(parts)

        row_link = row_link.strip()
        if row_link.startswith("| [[") or row_link.startswith("|[[") or row_link.startswith(
                "| ''[[") or row_link.startswith("|''[["):

            link = re.findall(link_pattern, row_link)[0].replace("[[", "").replace("]]", "").strip()
            if "|" in link:
                parts = link.split("|")
                link = parts[0].strip()
                link_anchor = parts[1].strip()
            else:
                link_anchor = link

            if "#" not in link and row_link_is_not_forbidden(row_link, forbidden_links):
                if wikipedia_page_exists(link,
                                         dbpedia_to_wikidata):  # ignore links like Upper_Clapton#The_Abode_of_Love
                    rows_with_linked_examples.append([line for line in row])
                    links.append({"link": link.replace(" ", "_"), "anchor_text": link_anchor})
                    number_of_examples += 1
                else:
                    rows_without_examples.append([line for line in row])
        else:
            rows_without_examples.append([line for line in row])

    return start_lines, rows_with_linked_examples, rows_without_examples, links


def extract_triples(link):
    pass


'''
if __name__ == "__main__":

    # Example usage:
    article_name = "List_of_churches_in_London"
    article_content = download_article(article_name)
    tables = get_tables(article_content)

    for table in tables:
        # print("T:",table)
        table_with_only_examples, table_without_examples, links = remove_example_rows(table, MAX_NUMBER_OF_EXAMPLES)
        # print(table_without_examples)
        # print(table_with_only_examples)
        print(links)
        # break

        for link in links:
            triples = extract_triples(link)
'''
