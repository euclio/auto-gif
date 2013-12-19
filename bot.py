import os
import praw
import requests
import db_interface
from bs4 import BeautifulSoup
from gensim import corpora, models, similarities

r = praw.Reddit(user_agent='Auto-gif: Attempts to respond to comments with relevant '
                'reaction gifs')


def login():
    try:
        username = os.environ['BOT_USERNAME']
        password = os.environ['BOT_PASSWORD']
        r.login(username, password)
    except KeyError:
        r.login()


# Get a list of threads from the top stories on reddit.
# Each thread is a list of (body, name) pairs.
def reddit_threads():
    login()
    reactiongifs = r.get_subreddit('reactiongifs')
    threads = []
    for story in reactiongifs.get_top_from_all(limit=5):
        comments = story.comments
        print story
        print len(comments)
        threads += [comment_descendants(comment) for comment in comments
                    if type(comment) is praw.objects.Comment]
    print 'Number of threads is ' + str(len(threads))
    return threads


# Get a list of topics from reddit comments using LDA
def reddit_topics():
    threads = []
    for thread in reddit_threads():
        text = ''
        for comment in thread:
            text += ' ' + comment[0]
        threads.append([word for word in text.lower().split()])
    all_tokens = []
    for thread in threads:
        all_tokens += thread
    unique = set(word for word in set(all_tokens) if all_tokens.count(word) == 1)
    common = set(['for', 'a', 'of', 'the', 'and', 'to', 'in', 'http', 'gif',
                  'mrw'])
    threads = [[word for word in thread if word not in unique | common]
               for thread in threads]
    dictionary = corpora.Dictionary(threads)
    dictionary.save('/tmp/top10.dict')
    corpus = [dictionary.doc2bow(thread) for thread in threads]
    corpora.MmCorpus.serialize('/tmp/top10.mm', corpus)
    model = models.ldamodel.LdaModel(corpus=corpus, id2word=dictionary, num_topics=10)
    print model
    model.print_topics(50)



# Get the text and id of a comment and its descendants, taking the first
# reply at each level.
def comment_descendants(comment):
    descendants = [comment.body, comment.name]
    while (len(comment.replies) > 0
           and type(comment.replies[0]) is praw.objects.Comment
           and comment.replies[0].ups - comment.replies[0].downs > 1):
        comment = comment.replies[0]
        descendants.append((comment.body, comment.name))
    return descendants


def scrape():
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
