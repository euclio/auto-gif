import os
import re
import time

import praw
import requests
import db_interface
from bs4 import BeautifulSoup
from gensim import corpora, models, similarities
from stemming.porter2 import stem
from markdown import markdown
from datetime import datetime, timedelta
from itertools import chain

r = praw.Reddit(user_agent='Auto-gif: Attempts to respond to comments with relevant '
                'reaction gifs')


def login():
    """Log in to reddit.

    Attempts to use the BOT_USERNAME and BOT_PASSWORD environment variables to
    log in. If either variable doesn't exist, then the function will prompt for
    a username and password."""
    try:
        username = os.environ['BOT_USERNAME']
        password = os.environ['BOT_PASSWORD']
        r.login(username, password)
    except KeyError:
        r.login()


def days_old(story):
    '''Return true if story is at least two days old.'''
    return datetime.now() - datetime.fromtimestamp(story.created) > timedelta(days=2)


def reddit_threads(number):
    """Get a list of threads from the top stories on reddit.

    Each thread is a list of (body, name) pairs.
    """
    login()
    subr = r.get_subreddit('funny')
    all_threads = []
    for story in filter(days_old, subr.get_top_from_all(limit=number)):
        comments = story.comments
        print story
        print len(comments)
        story_threads = [comment_descendants(comment) for comment in comments if type(comment) is praw.objects.Comment]
        all_threads = chain(all_threads, story_threads)
    return all_threads


def reddit_corpus(name, input_threads):
    """Save a corpus of reddit comments."""

    def thread_words(thread):
        text = ''
        for comment in thread:
            # Remove punctuation
            comment = re.sub('[!.:?,;"]', '', comment[0])
            text += comment
        return [stem(word) for word in text.lower().split()]

    threads = [thread_words(thread) for thread in input_threads]
    dictionary = corpora.Dictionary(threads)
    unique_id = [word for word, count in dictionary.dfs.iteritems() if count == 1]
    common_id = []
    with open('common_words.txt') as f:
        for line in f.readlines():
            word = stem(line.rstrip())
            if word in dictionary.token2id:
                common_id.append(dictionary.token2id[word])
    stopword_id = unique_id + common_id
    print 'Number of words thrown out:', len(stopword_id)
    dictionary.filter_tokens(stopword_id)
    dictionary.compactify()
    dictionary.save(name + '.dict')
    corpus = (dictionary.doc2bow(thread) for thread in threads)
    corpora.MmCorpus.serialize(name + '.mm', corpus)


def LDA_model(name, number):
    """Create an LDA model from saved corpus and dictionary."""
    corpus = corpora.MmCorpus(name + '.mm')
    print corpus
    dictionary = corpora.Dictionary.load(name + '.dict')
    print dictionary
    model = models.ldamodel.LdaModel(corpus=corpus, id2word=dictionary, num_topics=number, passes = 10)
    print model
    for topic in model.show_topics(topics=-1):
        print topic
    return model


def comment_descendants(comment):
    """Get the text and id of a comment and its descendants, taking the first
    reply at each level."""
    descendants = [(strip_markdown(comment.body), comment.name)]
    while (len(comment.replies) > 0
           and type(comment.replies[0]) is praw.objects.Comment
           and comment.replies[0].ups - comment.replies[0].downs > 1):
        comment = comment.replies[0]
        descendants.append((strip_markdown(comment.body), comment.name))
    return descendants


def strip_markdown(text):
    """Remove markdown formatting on reddit comments."""
    html = markdown(text)
    return ''.join(BeautifulSoup(html).findAll(text=True))


def scrape():
    """Scrapes gifs and tags from reactiongifs.com and stores them in
    database."""
    for page in range(245, 500):
        print 'Scraping page', page, '...'
        url_prefix = "http://www.reactiongifs.com/page/"
        response = requests.get(url_prefix + str(page))
        content = response.content
        soup = BeautifulSoup(content)
        posts = soup.find_all(class_="post")
        for post in posts:
            post_url = post.find(class_="post-author").input["value"]
            image_url = post.find(class_="middle").find(class_="entry").a["href"]
            title = post.find(class_="middle").find(class_="title").a["title"]
            tags = post.find(class_="post-category").text[6:].split(', ')
            db_interface.store_image(image_url, post_url, title, tags)
        time.sleep(5)           # Make sure reactiongifs.com doesn't hate us :)


if __name__ == '__main__':
    #scrape()
    number = 100
    name = 'top'+ str(number)
    reddit_corpus(name, reddit_threads(number))
    LDA_model(name, 200)
