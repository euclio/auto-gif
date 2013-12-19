import os
import praw
import requests
import db_interface
from bs4 import BeautifulSoup
from gensim import corpora, models, similarities
from stemming.porter2 import stem
from markdown import markdown

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


def reddit_threads():
    """Get a list of threads from the top stories on reddit.

    Each thread is a list of (body, name) pairs.
    """
    login()
    reactiongifs = r.get_subreddit('reactiongifs')
    threads = []
    for story in reactiongifs.get_top_from_all(limit=5):
        comments = story.comments
        print story
        print len(comments)
        threads += [comment_descendants(comment) for comment in comments
                    if type(comment) is praw.objects.Comment]
    return threads


def reddit_topics():
    """Get a list of topics from reddit comments using LDA."""
    threads = []
    for thread in reddit_threads():
        text = ''
        for comment in thread:
            text += ' ' + comment[0]
        # don't include short threads
        if len(text) > 100:
            threads.append([stem(word) for word in text.lower().split()])
    all_tokens = []
    print 'Number of threads is', len(threads)
    for thread in threads:
        all_tokens += thread
    unique = set(word for word in set(all_tokens) if all_tokens.count(word) == 1)
    common_string = "are on his for it was when there a this be or your of the and to in http gif mrw [deleted] me you i some have that as is"
    common = set([stem(word) for word in common_string.split()])
    documents = [[word for word in thread if word not in unique | common]
               for thread in threads]
    dictionary = corpora.Dictionary(documents)
    dictionary.save('/tmp/top10.dict')
    corpus = [dictionary.doc2bow(document) for document in documents]
    corpora.MmCorpus.serialize('/tmp/top10.mm', corpus)
    model = models.ldamodel.LdaModel(corpus=corpus, id2word=dictionary, num_topics=5)
    print model
    for topic in model.show_topics():
        print topic


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
    page = 1
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


if __name__ == '__main__':
    #scrape()
    reddit_topics()
