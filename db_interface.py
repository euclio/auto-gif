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
    image_tags = db.select("* from ImageTag where tag = $query_tag",
                           {"query_tag": tag})
    results = []
    for image_tag in image_tags:
        images = db.select("* from Image where id = $image_id",
                           {"image_id": image_tag.id})
        if len(images) > 0:
            results.append(images[0])
    return results

db.generate_mapping(create_tables=True)
