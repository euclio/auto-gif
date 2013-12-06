import os
import praw
import requests
import db_interface
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
        post_url = post.find(class_="post-author").input["value"]
        image_url = post.find(class_="middle").find(class_="entry").a["href"]
        title = post.find(class_="middle").find(class_="title").a["title"]
        tags = post.find(class_="post-category").text[6:].split(', ')
        print title
        print post_url
        print image_url
        print tags
        db_interface.store_image(image_url,post_url,title,tags)
        # see if i can retrieve
        print db_interface.get_images_for_tag("wrong")
        
if __name__ == '__main__':
    scrape()

