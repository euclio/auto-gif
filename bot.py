from datetime import datetime, timedelta
from itertools import chain, islice
import os
import re
import time

from bs4 import BeautifulSoup
from gensim import corpora, models
from markdown import markdown
import praw
import requests
from stemming.porter2 import stem

import db_interface

r = praw.Reddit(user_agent='Auto-gif: Attempts to respond to comments with '
                           'relevant reaction gifs')

NUM_COMMENTS = 20


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


def reddit_threads(number):
    """Get a list of old threads from the top stories on reddit.

    Each thread is a list of (body, name) pairs.
    """

    def days_old(story):
        '''Return true if story is at least two days old.'''
        story_created = datetime.fromtimestamp(story.created)
        return datetime.now() - story_created > timedelta(days=2)

    login()
    subr = r.get_subreddit('funny')
    all_threads = []
    top_stories = (story for story in subr.get_top_from_all(limit=None)
                   if days_old(story))
    for story in islice(top_stories, number):
        comments = story.comments
        print story
        print len(comments)
        story_threads = [comment_descendants(comment) for comment in comments
                         if type(comment) is praw.objects.Comment]
        all_threads = chain(all_threads, story_threads)
    return all_threads


def recent_threads(number):
    """Get a list of old threads from the top stories on reddit.

    Each thread is a list of (body, name) pairs.
    """

    def hours_old(story):
        '''Return true if story is under six hours old.'''
        story_created = datetime.fromtimestamp(story.created)
        return datetime.now() - story_created < timedelta(hours=6)

    login()
    subr = r.get_subreddit('funny')
    all_threads = []
    top_stories = (story for story in subr.get_top(limit=None)
                   if hours_old(story))
    for story in islice(top_stories, number):
        comments = story.comments
        print story
        print len(comments)
        story_threads = [comment_descendants(comment) for comment in comments
                         if type(comment) is praw.objects.Comment
                         and comment.ups > 5]
        all_threads = chain(all_threads, story_threads)
    return all_threads


def thread_words(thread):
    """Get the words from a list of comments."""

    text = ''
    for comment in thread:
        # Remove punctuation
        comment = re.sub('[!.:?,;|"]', '', comment[0])
        text += comment
    return [stem(word) for word in text.lower().split()]


def reddit_corpus(name, training_threads):
    """Save a corpus of reddit threads."""

    threads = [thread_words(thread) for thread in training_threads]
    dictionary = corpora.Dictionary(threads)
    unique_id = [word for word, count in dictionary.dfs.iteritems()
                 if count == 1]
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


def classify_new(model, input_threads):
    """Test a set of new reddit threads with an LDA model and find the comment
    with the best match."""

    # Return the total length of the comments in a thread
    def thread_length(thread):
        return reduce(lambda x, y: x + len(y[0]), thread, 0)

    # leave out threads with under 100 characters
    input_threads = [thread for thread in input_threads
                     if thread_length(thread) > 100]

    threads = [thread_words(thread) for thread in input_threads]

    dictionary = model.id2word

    weighted = []
    for processed, raw in zip(threads, input_threads):
        # sort the topics for this thread by weight
        topics = model[dictionary.doc2bow(processed)]
        topics_by_weight = sorted(topics, key=lambda x: -x[1])
        weighted.append((topics_by_weight, raw))

    sorted_weighted = sorted(weighted, key=lambda x: -x[0][0][1])

    comment_topics = []

    for topics_weights, comment in sorted_weighted[:NUM_COMMENTS]:
        best_topic, best_weight = topics_weights[0]
        topics = model.show_topics(topics=-1, formatted=False)[best_topic]
        comment_topics.append((comment, topics))

    return comment_topics


def LDA_model(name, number, passes=10):
    """Create an LDA model from saved corpus and dictionary."""
    corpus = corpora.MmCorpus(name + '.mm')
    print corpus
    dictionary = corpora.Dictionary.load(name + '.dict')
    print dictionary
    model = models.ldamodel.LdaModel(corpus=corpus, id2word=dictionary,
                                     num_topics=number, passes=passes)
    model.save(name + '.lda')
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
            image_url = (post.find(class_="middle")
                             .find(class_="entry")
                             .a["href"])
            title = (post.find(class_="middle")
                         .find(class_="title")
                         .a["title"])
            tags = post.find(class_="post-category").text[6:].split(', ')
            db_interface.store_image(image_url, post_url, title, tags)
        time.sleep(5)           # Make sure reactiongifs.com doesn't hate us :)


def respond_with_gif(comment, topics):
    images = []
    current_topic = None
    for topic in topics:
        images = db_interface.get_images_for_tag(topic)
        current_topic = topic
        if images:
            break
    else:
        print "No suitable images found."
        return
    image = images[0]
    print comment
    print current_topic
    print image
    reply_to_comment(comment, image.image_url)


def respond_with_random_gif(comment):
    image = db_interface.get_random_image()
    print comment
    print image
    reply_to_comment(comment, image.image_url)


def reply_to_comment(comment, image_url):
    r._add_comment(comment[1], '[relevant GIF]({})'.format(image_url))


if __name__ == '__main__':
    #scrape()
    number = 1000
    name = 'top' + str(number)
    #reddit_corpus(name, reddit_threads(number))
    #model = LDA_model(name, 100)
    model = models.ldamodel.LdaModel.load(name + '.lda')
    recent_threads = recent_threads(20)
    threads_and_topics = classify_new(model, recent_threads)
    for idx, thread_and_topics in enumerate(threads_and_topics):
        thread, weights_topics = thread_and_topics
        topics = [topic for weight, topic in weights_topics]
        if idx % 2 == 0:
            print 'Posting relevant gif.'
            respond_with_gif(thread[-1], topics)
        else:
            print 'Posting random gif.'
            respond_with_random_gif(thread[-1])
        time.sleep(660)         # Avoid reddit spam filtering
