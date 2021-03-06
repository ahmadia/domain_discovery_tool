import math
import time
import os
from sklearn.decomposition import PCA
from random import random, randint
from pprint import pprint
from subprocess import call
from subprocess import Popen
from subprocess import PIPE
from os import chdir, listdir, environ
from os.path import isfile, join, exists
import shutil
import sys
from datetime import datetime

from seeds_generator.download import download, decode
from seeds_generator.concat_nltk import get_bag_of_words

from pyelasticsearch import ElasticSearch
from elasticsearch import Elasticsearch
from elastic.get_config import get_available_domains
from elastic.search_documents import get_context, term_search, search, range
from elastic.add_documents import add_document, update_document
from elastic.get_mtermvectors import getTermStatistics
from elastic.get_documents import get_most_recent_documents, get_documents, get_all_ids
from ranking import tfidf, rank, extract_terms



class CrawlerModel:
  def __init__(self):
    self.es = None
    self._activeCrawlerIndex = None
    self._filter = None
    self._pagesCap = int(10E2)

    # TODO(Yamuna): delete when not returning random data anymore.
    self._randomTerms = {
      'Word': ['Word', randint(1, 100), randint(1, 100), ['Positive']],
      'Disease': ['Disease', randint(1, 100), randint(1, 100), ['Negative']],
      'Control': ['Control', randint(1, 100), randint(1, 100), []],
      'Symptoms': ['Symptoms', randint(1, 100), randint(1, 100), ['Positive']],
      'Epidemy': ['Epidemy', 100, 100, []],
    }



  # Returns a list of available crawlers in the format:
  # [
  #   {'id': crawlerId, 'name': crawlerName, 'creation': epochInSecondsOfFirstDownloadedURL},
  #   {'id': crawlerId, 'name': crawlerName, 'creation': epochInSecondsOfFirstDownloadedURL},
  #   ...
  # ]
  def getAvailableCrawlers(self):
    # TODO(Yamuna): Fix to point to correct elastic search.
    # Initializes elastic search.
    self.es = ElasticSearch( \
    os.environ['ELASTICSEARCH_SERVER'] if 'ELASTICSEARCH_SERVER' in os.environ else 'http://localhost:9200')

    domains = get_available_domains(self.es)
    return \
    [{'id': d['index'], 'name': d['domain_name'], 'creation': d['timestamp']} for d in domains]



  # Returns a list of available seed crawlers in the format:
  # [
  #   {'id': crawlerId, 'name': crawlerName, 'creation': epochInSecondsOfFirstDownloadedURL},
  #   {'id': crawlerId, 'name': crawlerName, 'creation': epochInSecondsOfFirstDownloadedURL},
  #   ...
  # ]
  def getAvailableSeedCrawlers(self):
    # Initializes elastic search.
    self.es = ElasticSearch( \
    os.environ['ELASTICSEARCH_SERVER'] if 'ELASTICSEARCH_SERVER' in os.environ else 'http://localhost:9200')

    domains = get_available_domains(self.es)
    return \
    [{'id': d['index'], 'name': d['domain_name'], 'creation': d['timestamp']} for d in domains]


  # Changes the active crawler to be monitored.
  def setActiveCrawler(self, crawlerId):
    print 'SET ACTIVE CRAWLER'
    self._activeCrawlerIndex = crawlerId
    self._filter = None

  # Returns number of pages downloaded between ts1 and ts2 for active crawler.
  # ts1 and ts2 are Unix epochs (seconds after 1970).
  # If opt_applyFilter is True, the summary returned corresponds to the applied pages filter defined
  # previously in @applyFilter. Otherwise the returned summary corresponds to the entire dataset
  # between ts1 and ts2.
  # Returns dictionary in the format:
  # {
  #   'Positive': {'Explored': numExploredPages, 'Exploited': numExploitedPages},
  #   'Negative': {'Explored': numExploredPages, 'Exploited': numExploitedPages},
  # }
  def getPagesSummaryCrawler(self, opt_ts1 = None, opt_ts2 = None, opt_applyFilter = False):
    # If ts1 not specified, sets it to -Infinity.
    if opt_ts1 is None:
      now = time.localtime(0)
      opt_ts1 = int(time.mktime(now))
    else:
      opt_ts1 = int(opt_ts1)

    # If ts2 not specified, sets it to now.
    if opt_ts2 is None:
      now = time.localtime()
      opt_ts2 = int(time.mktime(now))
    else:
      opt_ts2 = int(opt_ts2)

    # TODO(Yamuna): Query Elastic Search (schema self._activeCrawlerId) for number of downloaded pages
    # between given Unix epochs.
    # TODO(Yamuna): apply filter if it is None. Otherwise, match_all.
    print '\n\n *** init', opt_ts1

    inc = opt_ts2 - opt_ts1

    print '\n\n *** delta', inc

    explored = int(opt_ts1 / 10E6 + inc)
    exploited = int(opt_ts1 / 10E8 + inc / 2)
    boosted = int(opt_ts1 / 10E8 + inc / 2)
    return { \
      'Positive': {'Explored': explored, 'Exploited': exploited, 'Boosted': boosted},
      'Negative': {'Explored': explored / 5, 'Exploited': exploited / 5, 'Boosted':  boosted / 5},
    }



  # Returns number of pages downloaded between ts1 and ts2 for active crawler.
  # ts1 and ts2 are Unix epochs (seconds after 1970).
  # If opt_applyFilter is True, the summary returned corresponds to the applied pages filter defined
  # previously in @applyFilter. Otherwise the returned summary corresponds to the entire dataset
  # between ts1 and ts2.
  # Returns dictionary in the format:
  # {
  #   'Relevant': numRelevantPages,
  #   'Irrelevant': numIrrelevantPages,
  #   'Neutral': numNeutralPages,
  # }
  def getPagesSummarySeedCrawler(self, opt_ts1 = None, opt_ts2 = None, opt_applyFilter = False):

    # If ts1 not specified, sets it to -Infinity.
    if opt_ts1 is None:
      now = time.localtime(0)
      opt_ts1 = float(time.mktime(now))
    else:
      opt_ts1 = float(opt_ts1)

    # If ts2 not specified, sets it to now.
    if opt_ts2 is None:
      now = time.localtime()
      opt_ts2 = float(time.mktime(now))
    else:
      opt_ts2 = float(opt_ts2)
    
    if opt_applyFilter:
    # TODO(Yamuna): apply filter if it is None. Otherwise, match_all.
      results = \
      range('retrieved',opt_ts1, opt_ts2, ['url','tag'], True, self._activeCrawlerIndex, es=self.es)
    else:
      results = \
      range('retrieved',opt_ts1, opt_ts2, ['url','tag'], True, self._activeCrawlerIndex, es=self.es)

    relevant = 0
    irrelevant = 0
    neutral = 0

    # TODO(Yamuna): Double check the return values for crawler
    for res in results:
        try:
          tags = res['tag']
          if 'Relevant' in res['tag']:
            relevant = relevant + 1
          elif 'Irrelevant' in res['tag']:
            irrelevant = irrelevant + 1
          else:
            # Page has tags, but not Relevant or Irrelevant.
            neutral = neutral + 1
        except KeyError:
          # Page does not have tags.
          neutral = neutral + 1

    return { \
      'Relevant': relevant,
      'Irrelevant': irrelevant,
      'Neutral': neutral
    }



  # Returns number of terms present in positive and negative pages.
  # Returns array in the format:
  # [
  #   [term, frequencyInPositivePages, frequencyInNegativePages, tags],
  #   [term, frequencyInPositivePages, frequencyInNegativePages, tags],
  #   ...
  # ]
  def getTermsSummaryCrawler(self, opt_maxNumberOfTerms = 50):
    # TODO(Yamuna): Query Elastic Search (schema self._activeCrawlerId) for terms ranked by highest
    # tf-idf, and return top opt_maxNumberOfTerms, with tf_idf for term occurring in positive and
    # negative pages.
    #return 9 * [e[:3] for e in self._randomTerms.values()]
    return 9 * self._randomTerms.values()



  # Returns number of terms present in relevant and irrelevant pages.
  # Returns array in the format:
  # [
  #   [term, frequencyInRelevantPages, frequencyInIrrelevantPages, tags],
  #   [term, frequencyInRelevantPages, frequencyInIrrelevantPages, tags],
  #   ...
  # ]
  def getTermsSummarySeedCrawler(self, opt_maxNumberOfTerms = 50):

    terms = []

    pos_urls = term_search('tag', ['Relevant'], self._activeCrawlerIndex, 'page', self.es)
    pos_urls_found = True
    if len(pos_urls) == 0:
      pos_urls = get_all_ids(self._activeCrawlerIndex, 'page', self.es)
      pos_urls_found = False

    if len(pos_urls) > 1:

      tfidf_h = tfidf.tfidf(pos_urls)
      extract_terms_h = extract_terms.extract_terms(tfidf_h)
      top_terms = extract_terms_h.getTopTerms(opt_maxNumberOfTerms)

      tags = get_documents(top_terms, 'term', ['tag'], self._activeCrawlerIndex, 'terms', self.es)

      pos_freq = {}
      if pos_urls_found:
        ttfs = tfidf_h.getTtf()
        pos_freq = { key: 0 if ttfs.get(key) is None else ttfs.get(key) for key in top_terms }      
      else:
        pos_freq = { key: 0 for key in top_terms }      

      neg_urls = term_search('tag', ['Irrelevant'], self._activeCrawlerIndex, 'page', self.es)
      neg_freq = {}
      if len(neg_urls) > 1:
        tfidf_h = tfidf.tfidf(neg_urls)
        ttfs = tfidf_h.getTtf()
        neg_freq = { key: 0 if ttfs.get(key) is None else ttfs.get(key) for key in top_terms }      
      else:
        neg_freq = { key: 0 for key in top_terms }      

      for term in top_terms:
        entry = [term, pos_freq[term], neg_freq[term], []]
        if not tags.get(term) is None:
          entry[3] = tags[term]['tag'].split(';')
        terms.append(entry)

    return terms

  # Sets limit to pages returned by @getPages.
  def setPagesCountCap(self, pagesCap):
    self._pagesCap = int(pagesCap)

  # Returns most recent downloaded pages.
  # Returns dictionary in the format:
  # {
  #   'last_downloaded_url_epoch': 1432310403 (in seconds)
  #   'pages': [
  #             [url1, x, y, tags, retrieved],     (tags are a list, potentially empty)
  #             [url2, x, y, tags, retrieved],
  #             [url3, x, y, tags, retrieved],
  #   ]
  # }
  def getPages(self):

    hits = get_most_recent_documents(self._pagesCap, ["url", "x", "y", "tag", "retrieved"], 
                                     self._filter, self._activeCrawlerIndex, 'page', \
                                     self.es)

    docs = []
    for i, hit in enumerate(hits):
      doc = ["", 0, 0, [], 0]
      if not hit.get('url') is None:
        doc[0] = hit['url'][0]
      if not hit.get('x') is None:
        doc[1] = hit['x'][0]
      if not hit.get('y') is None:
        doc[2] = hit['y'][0]
      if not hit.get('tag') is None:
        doc[3] = hit['tag'][0].split(';')
      if not hit.get('retrieved') is None:
        doc[4] = hit['retrieved'][0]
      docs.append(doc)

    # Gets last downloaded url epoch from top result (most recent one).
    last_downloaded_url_epoch = 0
    if len(docs) > 0:
      last_downloaded_url_epoch = docs[0][4]

      # Prepares results: computes projection.
      # TODO(Yamuna): Update x, y for pages after projection is done.
      projectionData = self.projectPages(docs)

      # TODO(Yamuna): Fill x and y returned by projection.
      #crawlermodeladapter.runpcasklearn(pos_data, pc_count)

      last_download_epoch = CrawlerModel.convert_to_epoch(datetime.strptime(last_downloaded_url_epoch, '%Y-%m-%dT%H:%M:%S.%f'))
      return {\
              'last_downloaded_url_epoch': last_download_epoch,
              'pages': [page[:4] for page in docs]
            }
    else:
      return {}

  # Boosts set of pages: crawler exploits outlinks for the given set of pages in active crawler.
  def boostPages(self, pages):
    # TODO(Yamuna): Issue boostPages on running crawler defined by active crawlerId.
    i = 0
    print 3 * '\n', 'boosted pages', str(pages), 3 * '\n'



  # Fetches snippets for a given term.
  def getTermSnippets(self, term):
    tags = get_documents(term, 'term', ['tag'], self._activeCrawlerIndex, 'terms', self.es)
    tag = []
    if tags:
      tag = tags[term]['tag'].split(';')

    return {'term': term, 'tags': tag, 'context': get_context([term], self._activeCrawlerIndex, 'page', self.es)}

  # Adds tag to pages (if applyTagFlag is True) or removes tag from pages (if applyTagFlag is
  # False).
  def setPagesTag(self, pages, tag, applyTagFlag):

    results = get_documents(pages, 'url', ['tag'], self._activeCrawlerIndex, 'page', self.es)

    entries = []
    if applyTagFlag:
      print '\n\napplied tag ' + tag + ' to pages' + str(pages) + '\n\n'
      for page in pages:
        entry = {}

        if len(results) > 0:
          if results.get(page) is None:
            entry['url'] = page
            entry['tag'] = tag
          elif tag not in results.get(page)['tag']:
            entry['url'] = page
            entry['tag'] = results.get(page)['tag'] + ';' + tag
        else:
          entry['url'] = page
          entry['tag'] = tag

        if entry:
          entries.append(entry)
    else:
      print '\n\nremoved tag ' + tag + ' from pages' + str(pages) + '\n\n'
      for page in pages:
        entry = {}
        if len(results) > 0 and not results.get(page) is None:
          if tag in results.get(page)['tag']:
            entry['url'] = page
            tags = results.get(page)['tag'].split(';')
            tags.remove(tag)
            entry['tag'] = ';'.join(tags)
        if entry:
          entries.append(entry)

    update_document(entries, 'url', self._activeCrawlerIndex, 'page', self.es)


  # Adds tag to terms (if applyTagFlag is True) or removes tag from terms (if applyTagFlag is
  # False).
  def setTermsTag(self, terms, tag, applyTagFlag):
    # TODO(Yamuna): Apply tag to page and update in elastic search. Suggestion: concatenate tags
    # with semi colon, removing repetitions.

    results = get_documents(terms, 'term', ['tag'], self._activeCrawlerIndex, 'terms', self.es)
    
    add_entries = []
    update_entries = []

    if applyTagFlag:
      for term in terms:
        new_tag = None
        if len(results) > 0:
          if not results.get(term) is None:
            old_tag = results[term]['tag']
            if tag not in old_tag:
              new_tag = old_tag + ";" + tag
              entry = {
                "term" : term,
                "tag" : new_tag
              }
              update_entries.append(entry)
          else:
            new_tag = tag
            entry = {
              "term" : term,
              "tag" : new_tag
            }
            add_entries.append(entry)
        else:
          new_tag = tag
          entry = {
            "term" : term,
            "tag" : new_tag
          }
          add_entries.append(entry)
    else:
      for term in terms:
        new_tag = None
        if len(results) > 0:
          if not results.get(term) is None:
            old_tag = results[term]['tag']
            if tag in old_tag:
              tags = old_tag.split(';')
              tags = tags.remove(tag)
              new_tag = ';'.join(tags)
              entry = {
                "term" : term,
                "tag" : new_tag
              }
              update_entries.append(entry)

    if add_entries:
      add_document(add_entries, self._activeCrawlerIndex, 'terms', self.es)
    
    if update_entries:
      update_document(update_entries, 'term', self._activeCrawlerIndex, 'terms', self.es)

  # Submits a web query for a list of terms, e.g. 'ebola disease'
  def queryWeb(self, terms, max_url_count = 100):
    # TODO(Yamuna): Issue query on the web: results are stored in elastic search, nothing returned
    # here.
    
    chdir(environ['DDT_HOME']+'/seeds_generator')
    
    with open('conf/queries.txt','w') as f:
      f.write(terms)

    comm = "java -cp target/seeds_generator-1.0-SNAPSHOT-jar-with-dependencies.jar BingSearch -t " + str(max_url_count)
    p=Popen(comm, shell=True, stdout=PIPE)
    output, errors = p.communicate()
    print output
    print errors
    
    download("results.txt", self._activeCrawlerIndex, "page", os.environ['ELASTICSEARCH_SERVER'] if 'ELASTICSEARCH_SERVER' in os.environ else 'http://localhost:9200')



  # Applies a filter to crawler results, e.g. 'ebola disease'
  def applyFilter(self, terms):
    # The filter is just cached, and should be used in getPages (always) and getPagesSummary
    # (when the optional flag is set to True). Check those methods signatures.
    if terms:
      self._filter = terms


  # Projects pages.
  def projectPages(self, pages):
    return self.pcaProjectPages(pages)
    
  # Projects pages with PCA.
  def pcaProjectPages(self, pages):
    
    # TODO(Yamuna): compute tfidf for pages, compute projection, fill x, y.
    urls = [page[0] for page in pages]
    [_, _, data] = self.term_tfidf(urls)
    
    pca_count = 2
    pcadata = CrawlerModel.runPCASKLearn(data, pca_count)

    for i, page in enumerate(pages):
      if i >= len(pcadata[1]):
        break;
      page[1] = pcadata[1][i][0]
      page[2] = pcadata[1][i][1]

    return pages
    
  def term_tfidf(self, urls):
    es_server = Elasticsearch( \
    os.environ['ELASTICSEARCH_SERVER'] if 'ELASTICSEARCH_SERVER' in os.environ else 'http://localhost:9200')

    [data, _ , _ , corpus] = getTermStatistics(urls, self._activeCrawlerIndex, 'page', es_server)
    return [urls, corpus, data.toarray()]

  @staticmethod
  def runPCASKLearn(X, pc_count = None):
    pca = PCA(n_components=pc_count)
    pca.fit(X)
    return [pca.explained_variance_ratio_.tolist(), pca.transform(X).tolist()]

  @staticmethod
  def convert_to_epoch(dt):
    epoch = datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.total_seconds()

