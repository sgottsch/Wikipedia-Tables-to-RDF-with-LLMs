# Wikipedia-Tables-to-RDF-with-LLMs (Examples)

## Wikidata Query

[This Wikidata example query](example_wikidata_sparql_query.txt) is used to get relevant triples about the entity "[St Margaret's Church, Barking](https://www.wikidata.org/wiki/Q17526496)".

You can see the results of this query on the Wikidata SPARQL endpoint [here](https://w.wiki/9Kfp).

## Example Graph

See [here](example_churches_in_london.ttl) for an example RDF Turtle file automatically generated for the table "Barking and Dagenham" in the Wikipedia page ["List of churches in London"](https://en.wikipedia.org/w/index.php?title=List_of_churches_in_London&oldid=1203013560).

## Example Experiments

The [`data/evaluation`](../data/evaluation) folder contains results of two types of experiments:
- Evaluation: The sub folders `existing_entities` contain results generated for known target entities for different numbers of examples.
   - You can see an example comparison of known triples and generated triples [here](../data/evaluation/5_examples/existing_entities/evaluation/List_of_Ganesha_temples_1.txt). The prompt to generate these triples is [here](/data/evaluation/5_examples/existing_entities/prompts/List_of_Ganesha_temples_1.txt).
- New entities: The sub folder [`data/evaluation/5_examples/new_entities`](../data/evaluation/5_examples/new_entities) contains results of running our method to detect new entities for 5 examples.

## Table Dataset

See [here](../data/wikipedia_list_tables.tsv) for the list of Wikipedia pages and their tables used in our experiments.
