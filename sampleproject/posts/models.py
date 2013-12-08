from django.db import models

class Post(models.Model):
    title = models.CharField(max_length=256)
    content = models.TextField(blank=True)
    tags = models.ManyToManyField('Tag', blank=True)

    def __unicode__(self):
        return u'Post: {0}'.format(self.title)


class Comment(models.Model):
    post = models.ForeignKey(Post)
    author = models.CharField(max_length=256)
    content = models.TextField()

    def __unicode__(self):
        return u'Comment on {0} by {1}'.format(self.post, self.author)

class Tag(models.Model):
    name = models.CharField(max_length=50)

    def __unicode__(self):
        return self.name
