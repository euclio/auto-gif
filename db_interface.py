from pony.orm import Database, Required, Set, commit, db_session

db = Database('sqlite', 'database.sqlite', create_db=True)


class Image(db.Entity):
    image_url = Required(unicode)
    post_url = Required(unicode)
    title = Required(unicode)
    tags = Set("ImageTag")


class ImageTag(db.Entity):
    tag = Required(unicode)
    image = Required(Image)


@db_session
def store_image(image_url, post_url, title, tags):
    image = Image(image_url=image_url, post_url=post_url,
                  title=title)
    for tag in tags:
        ImageTag(tag=tag, image=image)
    commit()


@db_session
def get_images_for_tag(tag):
    result = db.select("* from ImageTag where tag = $query_tag",
                       {"query_tag": tag})
    return result

db.generate_mapping(create_tables=True)
