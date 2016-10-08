import os
import sys
from getpass import getpass
from tempfile import mkdtemp
import json
import zipfile
import time
import shutil

import Glacier2
import Ice
Ice.loadSlice('-I%s %s' % (Ice.getSliceDir(), os.path.abspath(os.path.join(__file__, '..', 'MotionDatabase.ice'))))
import MotionDatabase

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from dataset.models import MotionFile, Annotation, Dataset
from dataset.management.util import *


DATA_PATH = os.path.abspath(os.path.join(__file__, '..', '..', '..', 'static', 'downloads'))
ICE_CLIENT_CONFIG_PATH = os.path.abspath(os.path.join(__file__, '..', 'client.cfg'))


def zipdir(basedir, archivename, callback_before=None, callback_after=None):
	assert os.path.isdir(basedir)
	with zipfile.ZipFile(archivename, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
		for root, dirs, files in os.walk(basedir):
			for fn in files:
				absfn = os.path.join(root, fn)
				zfn = absfn[len(basedir) + len(os.sep):]
				if callback_before is not None:
					callback_before(zfn)
				z.write(absfn, zfn)
				if callback_after is not None:
					callback_after(zfn)


class Command(BaseCommand):
	help = 'Exports a version of the current dataset.'

	def add_arguments(self, parser):
		pass

	def handle(self, *args, **options):
		username = raw_input('MotionDB Username: ')
		password = getpass('MotionDB Password: ')
		self.stdout.write('')
		
		# Configure Ice and Connect to database.
		properties = Ice.createProperties(sys.argv)
		properties.load(ICE_CLIENT_CONFIG_PATH)
		init_data = Ice.InitializationData()
		init_data.properties = properties
		ic = Ice.initialize(init_data)
		router = Glacier2.RouterPrx.checkedCast(ic.getDefaultRouter())
		session = router.createSession(username, password)
		db = MotionDatabase.MotionDatabaseSessionPrx.checkedCast(session)

		# Collect all matching C3D and MMM files.
		self.stdout.write('Collecting data from motion database ...')
		q = MotionFile.objects.filter(is_hidden=False, is_broken_reported=False, is_broken_confirmed=False)
		motion_ids = list(set([m.motion_db_id for m in q.all()]))
		all_c3d_files = []
		all_mmm_files = []
		all_annotations = []
		all_motion_ids = []
		all_database_entries = []
		for idx, motion_id in enumerate(motion_ids):
			self.stdout.write(' {}/{} ...'.format(idx + 1, len(motion_ids)), ending= ' ')
			self.stdout.flush()
			files = db.listFiles(motion_id)
			c3d_files = [f for f in files if f.fileType == 'Vicon C3D File']
			mmm_files = [f for f in files if f.fileType == 'Converted MMM Motion']
			
			for c3d_file in c3d_files:
				# Ensure that only visible data is exported.
				assert c3d_file.visibility == MotionDatabase.VisibilityLevel.Public

				# Fetch motion file from database.
				try:
					motion_file = MotionFile.objects.get(motion_db_file_id=c3d_file.id)
				except MotionFile.DoesNotExist:
					continue
				assert motion_file.motion_db_id == motion_id

				# Skip broken motions.
				if motion_file.is_broken_reported or motion_file.is_broken_confirmed:
					continue

				# Find the matching MMM file for the given C3D file.
				mmm_file = None
				for f in mmm_files:
					if f.originatedFrom.id == c3d_file.id:
						mmm_file = f
						break
				assert mmm_file is not None

				# Get all annotations. We include data even if it isn't annotated yet.
				annotations = Annotation.objects.filter(motion_file=motion_file).all()

				all_c3d_files.append(c3d_file)
				all_mmm_files.append(mmm_file)
				all_annotations.append(annotations)
				all_motion_ids.append(motion_id)
				all_database_entries.append(motion_file)
			self.stdout.write('done')
		n_motions = len(all_c3d_files)
		assert n_motions == len(all_mmm_files)
		assert n_motions == len(all_annotations)
		assert n_motions == len(all_motion_ids)
		assert n_motions == len(all_database_entries)
		self.stdout.write('done, obtained {} motions and their annotations'.format(n_motions))
		self.stdout.write('')

		# Create temporary directory.
		tmp_path = mkdtemp()
		self.stdout.write('Downloading data to "{}" ...'.format(tmp_path))
		motion_entry_cache = {}
		nb_annotations = 0
		nb_motions = 0
		for idx, (database_entry, c3d_file, mmm_file, annotations, motion_id) in enumerate(zip(all_database_entries, all_c3d_files, all_mmm_files, all_annotations, all_motion_ids)):
			self.stdout.write('  {}/{}: ...'.format(idx + 1, n_motions), ending=' ')
			self.stdout.flush()
			filename_prefix = '{0:05d}'.format(database_entry.id)
			filename_mmm = filename_prefix + '_mmm.xml'
			filename_c3d = filename_prefix + '_raw.c3d'
			filename_meta = filename_prefix + '_meta.json'
			filename_annotation = filename_prefix + '_annotations.json'

			# Download MMM.
			r = db.getFileReader(mmm_file.id)
			d = read_file(r)
			r.destroy()
			if d is None:
				return -1
			with open(os.path.join(tmp_path, filename_mmm), 'wb') as f:
				f.write(d)

			# Download C3D.
			r = db.getFileReader(c3d_file.id)
			d = read_file(r)
			r.destroy()
			if d is None:
				return -1
			with open(os.path.join(tmp_path, filename_c3d), 'wb') as f:
				f.write(d)

			# Retrieve motion information.
			if c3d_file.attachedToId in motion_entry_cache:
				motion_entry = motion_entry_cache[c3d_file.attachedToId]
			else:
				motion_entry = db.getMotion(c3d_file.attachedToId)
				motion_entry_cache[c3d_file.attachedToId] = motion_entry

			# Save annotations and extract their IDs for metadata.
			with open(os.path.join(tmp_path, filename_annotation), 'w') as f:
				json.dump([a.description for a in annotations], f)
			mat_annotation_ids = [a.id for a in annotations]
				
			# Save metadata.
			annotation_perplexities = [a.perplexity for a in annotations]
			assert len(annotation_perplexities) == len(annotations)
			with open(os.path.join(tmp_path, filename_meta), 'w') as f:
				data = {
					'motion_annotation_tool': {
						'id': database_entry.id,
						'annotation_ids': mat_annotation_ids,
					},
					'source': {
						'institution': {
							'name': motion_entry.associatedInstitution.name,
							'identifier': motion_entry.associatedInstitution.acronym.lower(),
						},
						'database': {
							'identifier': 'kit',
							'motion_id': motion_id,
							'motion_file_id': c3d_file.id,
						},
					},
					'nb_annotations': len(annotations),
					'annotation_perplexities': annotation_perplexities,
				}
				if motion_entry.associatedInstitution.acronym.lower() == 'cmu':
					# Reference actual CMU database first and provide KIT database as the mirror.
					data['source']['mirror_database'] = data['source']['database']
					motion_id, file_id = [int(x) for x in os.path.splitext(c3d_file.fileName)[0].split('_')]
					data['source']['database'] = {
						'identifier': 'cmu',
						'motion_id': motion_id,
						'motion_file_id': file_id,
					}
				json.dump(data, f)

				# Book-keeping.
				nb_annotations += len(annotations)
				nb_motions += 1
			self.stdout.write('done')
		self.stdout.write('done')
		self.stdout.write('')

		# Create ZIP archive.
		filename = time.strftime('%Y-%m-%d') + '.zip'
		self.stdout.write('Exporting ZIP archive "{}" ...'.format(filename), ending=' ')
		self.stdout.flush()
		def callback_before(file):
			self.stdout.write('  processing file "{}" ...'.format(file), ending = ' ')
			self.stdout.flush()
		def callback_after(file):
			self.stdout.write('done')
		zipdir(tmp_path, os.path.join(DATA_PATH, filename), callback_before=callback_before, callback_after=callback_after)
		self.stdout.write('done')
		self.stdout.write('')

		# Create dataset entry in DB.
		dataset = Dataset()
		dataset.nb_annotations = nb_annotations
		dataset.nb_motions = nb_motions
		dataset.filename = filename
		dataset.filesize = os.path.getsize(os.path.join(DATA_PATH, filename))
		dataset.save()

		# Clean up tmp directory.
		self.stdout.write('Cleaning up temp directory "{}" ...'.format(tmp_path), ending=' ')
		self.stdout.flush()
		shutil.rmtree(tmp_path)
		self.stdout.write('done')
		self.stdout.write('')

		self.stdout.write('All done, remember to collect the static files so that people can download the dataset!')
