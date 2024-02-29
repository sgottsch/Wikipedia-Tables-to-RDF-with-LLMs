import csv



def create_mapping():
    # 1. Download https://databus.dbpedia.org/dbpedia/wikidata/sameas-all-wikis
    # 2. grep '<http://dbpedia.org/resource/' sameas-all-wikis.ttl > sameas-en-wiki.ttl
    with open("data/sameas-all-enwiki.tsv", "w") as f:
        with open("data/sameas-en-wiki.ttl", errors="ignore") as file_ttl:
            for line in file_ttl:
                parts = line.split(" ")
                wikidata_id = parts[0].replace("<http://wikidata.dbpedia.org/resource/", "").replace(">", "")
                dbpedia_id = parts[2].replace("<http://dbpedia.org/resource/", "").replace(">", "")

                f.write(dbpedia_id + "\t" + wikidata_id + "\n")


def get_dbpedia_to_wikidata_mapping():
    print("Load DBpedia to Wikidata mapping.")
    dbpedia_to_wikidata = {}
    with open("data/sameas-all-enwiki.tsv") as fd:
        reader = csv.reader(fd, delimiter="\t", quotechar='"')
        for row in reader:
            dbpedia_to_wikidata[row[0]] = row[1]
    print(" -> Load DBpedia to Wikidata mapping: Done.")
    return dbpedia_to_wikidata

if __name__ == "__main__":
    create_mapping()
