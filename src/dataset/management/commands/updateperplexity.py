import os
import sys
import string
from tempfile import mkdtemp
import shutil
import unicodedata
import subprocess
import time

import numpy as np

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from dataset.models import MotionFile, Annotation


class Command(BaseCommand):
	help = 'Updates the all entries with the perplexity of the annotations that have been gathered so far.'

	def add_arguments(self, parser):
		parser.add_argument('--disable-throttle', action='store_true')

	def handle(self, *args, **options):
		# Collect all annotations and normalize the descriptions.
		self.stdout.write('Fetching annotations ...')
		annotations = Annotation.objects.all()
		descriptions = [a.description.lower() for a in annotations]
		remove_punct_map = dict.fromkeys(map(ord, string.punctuation))
		descriptions = [d.translate(remove_punct_map) for d in descriptions]
		for idx, description in enumerate(descriptions):
			descriptions[idx] = ' '.join([d.strip() for d in description.split()])
		descriptions = [unicodedata.normalize('NFKD', d).encode('ascii', 'ignore') for d in descriptions]
		assert len(descriptions) == len(annotations)

		# Create a temporary working folder.
		tmp_path = mkdtemp()

		# Combine all descriptions into a single file and keep the order so that we can map between
		# annotation ID and description.
		all_descriptions = '\n'.join(descriptions)
		text_path = os.path.join(tmp_path, 'text.txt')
		with open(text_path, 'w') as f:
			f.write(all_descriptions)
		self.stdout.write('done')
		self.stdout.write('')

		# Compute language model and perplexity under the model.
		self.stdout.write('Computing language model ...')
		model_path = os.path.join(tmp_path, 'model.txt')
		result = subprocess.call([os.path.join(settings.SRILM_BIN_PATH, 'ngram-count'), '-text', text_path, '-lm', model_path])
		if result != 0:
			raise RuntimeError('could not compute language model')
		process = subprocess.Popen([os.path.join(settings.SRILM_BIN_PATH, 'ngram'), '-lm', model_path, '-ppl', text_path, '-debug', '1'], stdout=subprocess.PIPE)
		out, err = process.communicate()

		# Parse output.
		lines = [line.strip() for line in out.split('\n')]
		line_idx = 0
		perplexity_by_annotation_id = {}
		for annotation, description in zip(annotations, descriptions):
			assert description == lines[line_idx]
			stats = lines[line_idx + 2]
			before, sep, after = stats.rpartition('=')
			assert before.endswith('ppl1')
			assert sep == '='
			annotation.perplexity = float(after)
			annotation.save()
			line_idx += 4
			if not options['disable_throttle']:
				time.sleep(.01)  # throttle updates so that users can still annotate (since we're using sqlite)
		self.stdout.write('done')
		self.stdout.write('')

		# Compute perplexity per motion by averaging.
		self.stdout.write('Updating database ...')
		motion_files = MotionFile.objects.all()
		for motion_file in motion_files:
			annotation_perplexities = motion_file.annotation_set.values('perplexity')
			if len(annotation_perplexities) == 0:
				mean_perplexity = int(10000)  # no annotation at all, use large value
			else:
				perplexities = np.array([x['perplexity'] for x in annotation_perplexities])
				mean_perplexity = np.mean(perplexities)
			motion_file.mean_perplexity = mean_perplexity
			motion_file.save()
			if not options['disable_throttle']:
				time.sleep(.01)  # throttle updates so that users can still annotate (since we're using sqlite)
		self.stdout.write('done')

		#print '\n'.join([u'"{}", {}'.format(mf.annotation_set.first().description, mf.mean_perplexity) for mf in sorted(motion_files, key=lambda mf: mf.mean_perplexity)])
		
		# Clean up.
		shutil.rmtree(tmp_path)
