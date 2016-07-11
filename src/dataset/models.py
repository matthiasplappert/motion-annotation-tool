from __future__ import unicode_literals
from random import randint

from django.db import models
from django.contrib.auth.models import User

from enchant import Dict
from enchant.tokenize import get_tokenizer


DICTIONARY = Dict('en_US')
TOKENIZER = get_tokenizer('en_US')


def default_randomness():
	return randint(0, 10000)


class MotionFile(models.Model):
	MARKER_SET_KIT = 0  # do not change values, since they are stored in the DB!
	MARKER_SET_CMU = 1
	
	class Meta:
		unique_together = ('motion_db_id', 'motion_db_file_id')
	
	motion_db_id = models.PositiveIntegerField()
	motion_db_file_id = models.PositiveIntegerField()
	filename = models.CharField(max_length=255, unique=True)
	mean_perplexity = models.FloatField(default=0.)
	is_broken_confirmed = models.BooleanField(default=False)
	is_broken_reported = models.BooleanField(default=False)
	marker_set = models.PositiveIntegerField(default=MARKER_SET_KIT)
	creation_date = models.DateTimeField(auto_now_add=True)
	update_date = models.DateTimeField(auto_now=True)
	is_hidden = models.BooleanField(default=False)

	def __str__(self):
		return self.filename


class Annotation(models.Model):
	class Meta:
		unique_together = ('user', 'motion_file')
	user = models.ForeignKey(User, on_delete=models.PROTECT)
	creation_date = models.DateTimeField(auto_now_add=True)
	motion_file = models.ForeignKey(MotionFile, on_delete=models.PROTECT)
	description = models.TextField()
	duration = models.PositiveIntegerField(default=0)
	ip_address = models.CharField(max_length=255, null=True, blank=True)
	accept_language = models.CharField(max_length=50, null=True, blank=True)
	perplexity = models.FloatField(default=0.)

	def __str__(self):
		return self.description

	def is_valid(self):
		words = [w[0] for w in TOKENIZER(self.description.lower())]
		n_words = len(words)
		if n_words == 0:
			# Return early to avoid problems with DIV by zero and such.
			return False
		
		unique_words = set(words)
		n_unique_words = len(unique_words)
		correct_unique_words = [w for w in unique_words if DICTIONARY.check(w)]
		n_correct_unique_words_words = len(correct_unique_words)
		correct_ratio = (float(n_correct_unique_words_words) / float(n_unique_words))
		n_punctuation_marks = self.description.count('.') + self.description.count('!') + self.description.count('?')

		is_valid = n_unique_words >= 3  # ... which contains at least three words
		is_valid &= correct_ratio >= 0.7  # ... of which at least 70% are spelled correctly
		is_valid &= n_punctuation_marks <= 2  # ... and the sentence only contains 2 or less punctuation marks

		return is_valid


class Dataset(models.Model):
	creation_date = models.DateTimeField(auto_now_add=True)
	filename = models.CharField(max_length=255, unique=True)
	filesize = models.PositiveIntegerField(default=0)
	nb_motions = models.PositiveIntegerField(default=0)
	nb_annotations = models.PositiveIntegerField(default=0)
	
	def __str__(self):
		return self.filename


class Download(models.Model):
	dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT)
	creation_date = models.DateTimeField(auto_now_add=True)
	ip_address = models.CharField(max_length=255, null=True, blank=True)
	accept_language = models.CharField(max_length=50, null=True, blank=True)
