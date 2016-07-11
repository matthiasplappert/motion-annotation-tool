import os
import sys
from getpass import getpass
from hashlib import sha1

import Glacier2
import Ice
Ice.loadSlice('-I%s %s' % (Ice.getSliceDir(), os.path.abspath(os.path.join(__file__, '..', 'MotionDatabase.ice'))))
import MotionDatabase

from django.core.management.base import BaseCommand, CommandError
from dataset.models import MotionFile


DATA_PATH = os.path.abspath(os.path.join(__file__, '..', '..', '..', 'static', 'motions'))
ICE_CLIENT_CONFIG_PATH = os.path.abspath(os.path.join(__file__, '..', 'client.cfg'))


class Command(BaseCommand):
	help = 'Removes motions from the tool that are marked as not public'

	def add_arguments(self, parser):
		pass

	def handle(self, *args, **options):
		username = raw_input('MotionDB Username: ')
		password = getpass('MotionDB Password: ')

		# Configure Ice and Connect to database.
		properties = Ice.createProperties(sys.argv)
		properties.load(ICE_CLIENT_CONFIG_PATH)
		init_data = Ice.InitializationData()
		init_data.properties = properties
		ic = Ice.initialize(init_data)
		router = Glacier2.RouterPrx.checkedCast(ic.getDefaultRouter())
		session = router.createSession(username, password)
		db = MotionDatabase.MotionDatabaseSessionPrx.checkedCast(session)

		self.stdout.write('Fetching all MotionFile objects ...')
		q = MotionFile.objects.all()
		motion_files = q[:]
		self.stdout.write('done, {} objects'.format(len(motion_files)))
		self.stdout.write('')

		self.stdout.write('Checking visibility of {} objects ...')
		nb_deleted_motionfiles = 0
		nb_deleted_annotations = 0
		for idx, mf in enumerate(motion_files):
			self.stdout.write('  {}/{} ...'.format(idx + 1, len(motion_files)), ending=' ')
			self.stdout.flush()
			file = db.getFile(mf.motion_db_file_id)
			if file.visibility == MotionDatabase.VisibilityLevel.Public:
				# The file is visible, nothing to do.
				self.stdout.write('skipping')
				continue

			# Delete the JSON file.
			path = os.path.join(DATA_PATH, mf.filename)
			assert os.path.exists(path)
			os.remove(path)

			# Delete the MotionFile and all its annotations.
			nb_annotations = mf.annotation_set.count()
			nb_annotations, _ = mf.annotation_set.all().delete()
			nb_motionfiles, _ = mf.delete()
			assert nb_motionfiles == 1
			nb_deleted_annotations += nb_annotations
			nb_deleted_motionfiles += 1
			self.stdout.write('deleted file + {} annotation(s)'.format(nb_annotations))
		self.stdout.write('done, deleted {} objects and {} annotations'.format(nb_deleted_motionfiles, nb_deleted_annotations))
