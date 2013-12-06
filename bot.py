import os
import praw
import requests
import sys
import codecs
from bs4 import BeautifulSoup

r = praw.Reddit('Auto-gif: Attempts to respond to comments with relevant '
                'reaction gifs')


def login():
    try:
        username = os.environ['BOT_USERNAME']
        password = os.environ['BOT_PASSWORD']
        r.login(username, password)
    except KeyError:
        r.login()


def reddit_test():
    login()
    reactiongifs = r.get_subreddit('reactiongifs')
    top = reactiongifs.get_top(limit=1).next()
    comments = top.comments
    print top
    print comments[0]


def scrape():
    page = 1
    url_prefix = "http://www.reactiongifs.com/page/"
    response = requests.get(url_prefix + str(page))
    content = response.content
    soup = BeautifulSoup(content)
    posts = soup.find_all(class_="post")
    for post in posts:
        date = post.find(class_="post-date")
        print date

if __name__ == '__main__':
    scrape()
