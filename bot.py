import os
import praw

r = praw.Reddit('Auto-gif: Attempts to respond to comments with relevant '
                'reaction gifs')


def login():
    try:
        username = os.environ['BOT_USERNAME']
        password = os.environ['BOT_PASSWORD']
        r.login(username, password)
    except KeyError:
        r.login()

if __name__ == '__main__':
    login()

    reactiongifs = r.get_subreddit('reactiongifs')
    top = reactiongifs.get_top(limit=1).next()
    comments = top.comments
    print top
    print comments[0]
