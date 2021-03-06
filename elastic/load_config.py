import json
import sys
from pyelasticsearch import ElasticSearch
from datetime import datetime
from pprint import pprint
from add_documents import add_document


def load_config(config_file, es_index='config', es_doc_type='domains', es_host=None):
    es = None
    if es_host is None:
        es = ElasticSearch('http://localhost:9200/')
    else:
        es = ElasticSearch(es_host)

    with open(config_file) as data_file:
        data = json.load(data_file)

    entries = data['entries']
    updated_entries = []
    for entry in entries:
        if entry.get('timestamp') is None:
            entry['timestamp'] = datetime.utcnow()
        updated_entries.append(entry)

    print updated_entries

    add_document(updated_entries, es_index, es_doc_type, es)

if __name__ == "__main__":

    if len(sys.argv)>1:
        config_file = sys.argv[1]
    else:
        config_file = 'ddt_index_config_entries.json'

    if len(sys.argv)>2:    
        es_index = sys.argv[2]
    else:
        es_index = 'config'

    if len(sys.argv)>3:    
        es_doc_type = sys.argv[3]
    else:
        es_doc_type = 'domains'

    if len(sys.argv)>4:    
        es_host = sys.argv[4]
    else:
        es_host = ('http://localhost:9200/')
    
    load_config(config_file, es_index, es_doc_type, es_host)
