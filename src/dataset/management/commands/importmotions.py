import json; json.encoder.FLOAT_REPR = lambda f: ("%.4f" % f)
import xml.etree.cElementTree as et
import os
import sys
import StringIO
from getpass import getpass
from hashlib import sha1

import c3d
import numpy as np

import Glacier2
import Ice
Ice.loadSlice('-I%s %s' % (Ice.getSliceDir(), os.path.abspath(os.path.join(__file__, '..', 'MotionDatabase.ice'))))
import MotionDatabase

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from dataset.models import MotionFile
from dataset.management.util import *


SUPPORTED_MARKER_NAMES = {
	MotionFile.MARKER_SET_KIT:
		['RPSI', 'LPSI', 'L3', 'STRN', 'T10', 'C7', 'CLAV', 'LSHO', 'LUPA', 'LAEL',
		 'LWTS', 'LWPS', 'LFRA', 'LIFD', 'LHPS', 'LHTS', 'RSHO', 'RUPA', 'RAEL',
		 'RWTS', 'RWPS', 'RFRA', 'RIFD', 'RHTS', 'RHPS', 'RBHD', 'LFHD', 'RFHD', 'LBHD', 'LHIP',
		 'RHIP', 'RASI', 'LASI', 'LKNE', 'LTHI', 'LANK', 'LTIP', 'LTOE', 'LMT1', 'LMT5', 'LHEE',
		 'RKNE', 'RTHI', 'RANK', 'RTIP', 'RTOE', 'RMT1', 'RMT5', 'RHEE'],
	MotionFile.MARKER_SET_CMU:
		['C7', 'CLAV', 'T10', 'STRN', 'RFWT', 'LUPA', 'LFWT', 'LBWT', 'LKNE',
         'RBWT', 'LFRM', 'LWRB', 'LWRA', 'LMT5', 'LTOE', 'RUPA', 'RKNE', 'RWRB', 'RWRA',
         'RMT5', 'RTOE', 'RHEE', 'LHEE', 'RFRM', 'RSHO', 'LSHO', 'RELB', 'LELB', 'RFIN',
         'LFIN', 'LFHD', 'RFHD', 'RBHD', 'LBHD', 'LANK', 'RANK', 'LSHN', 'RSHN', 'LTHI',
         'RTHI'],
}
DATA_PATH = os.path.abspath(os.path.join(__file__, '..', '..', '..', 'static', 'motions'))
ICE_CLIENT_CONFIG_PATH = os.path.abspath(os.path.join(__file__, '..', 'client.cfg'))


def rotation_matrix(roll, pitch, yaw):
	r11 = np.cos(yaw) * np.cos(pitch)
	r12 = np.cos(yaw) * np.sin(pitch) * np.sin(roll) - np.sin(yaw) * np.cos(roll)
	r13 = np.cos(yaw) * np.sin(pitch) * np.cos(roll) + np.sin(yaw) * np.sin(roll)
	r21 = np.sin(yaw) * np.cos(pitch)
	r22 = np.sin(yaw) * np.sin(pitch) * np.sin(roll) + np.cos(yaw) * np.cos(roll)
	r23 = np.sin(yaw) * np.sin(pitch) * np.cos(roll) - np.cos(yaw) * np.sin(roll)
	r31 = -np.sin(pitch)
	r32 = np.cos(pitch) * np.sin(roll)
	r33 = np.cos(pitch) * np.cos(roll)
	matrix = np.array([[r11, r12, r13],
					   [r21, r22, r23],
					   [r31, r32, r33]])
	return matrix


def pose_matrix(pos, rot):
	mat = np.eye(4)
	mat[0:3, 0:3] = rotation_matrix(rot[0], rot[1], rot[2])
	mat[0:3, 3] = pos
	return mat.astype('float32')


def parse_motion(c3d_data, mmm_data, downsample_factor, marker_set):
	# Open files.
	c3d_reader = c3d.Reader(StringIO.StringIO(c3d_data))
	xml_root = et.fromstring(mmm_data)

	# Extract root position at first frame from MMM file.
	xml_pos = xml_root.find('./Motion/MotionFrames/MotionFrame/RootPosition')
	xml_rot = xml_root.find('./Motion/MotionFrames/MotionFrame/RootRotation')
	assert xml_pos is not None
	assert xml_rot is not None
	pose_pos = [float(x) for x in xml_pos.text.split(' ')]
	pose_rot = [float(x) for x in xml_rot.text.split(' ')]

	xml_timesteps = xml_root.findall('./Motion/MotionFrames/MotionFrame/Timestep')
	if len(xml_timesteps) < 2:
		return None, None, None
	step0 = float(xml_timesteps[0].text)
	step1 = float(xml_timesteps[1].text)
	fps = np.round(1. / (step1 - step0))
	if fps / downsample_factor <= 40.:
		# Do not downsample motions that would then be less than 40 FPS
		downsample_factor = 1.
	interval = int((step1 - step0) * 1000. * float(downsample_factor))  # in ms

	# Extract marker names (some markers are named <Prefix>:<MarkerName>) and filter those to only include
	# the ones that we support across all motions.
	marker_names = [marker.rstrip().split(':')[-1] for marker in c3d_reader.point_labels]
	supported_indexes = [idx for idx, name in enumerate(marker_names) if name in SUPPORTED_MARKER_NAMES[marker_set]]
	markers = [marker_names[idx] for idx in supported_indexes]

	# Extract Cartesian coordinates from C3D file and downsample.
	frames = []
	for idx, points, _ in c3d_reader.read_frames():
		xyz_coordinates = points[supported_indexes, 0:3]
		frame = xyz_coordinates.flatten()
		frames.append(frame)
	frames = np.array(frames)[::downsample_factor, :]

	# Normalize all frames, that is rotate and translate as well as scale.
	n_markers = len(markers)
	n_frames = len(frames)
	pose_inv = np.linalg.inv(pose_matrix([pose_pos[0], pose_pos[1], 0.],  # keep z components as-is
										 [0., 0., pose_rot[2]]))  # only rotate around z-axis
	for i in xrange(n_markers):
		start_idx = i * 3
		pos = np.hstack([frames[:, start_idx:start_idx + 3], np.ones((n_frames, 1))])
		frames[:, start_idx:start_idx + 3] = np.dot(pose_inv, pos.T).T[:, 0:3]
	frames /= 100.  # convert from cm to m

	return markers, frames, interval


def get_marker_set_from_motion(motion):
	if motion.associatedInstitution.acronym.lower() == 'cmu':
		return MotionFile.MARKER_SET_CMU
	else:
		return MotionFile.MARKER_SET_KIT


def get_marker_set_identifier(marker_set):
	if marker_set == MotionFile.MARKER_SET_KIT:
		return 'kit'
	elif marker_set == MotionFile.MARKER_SET_CMU:
		return 'cmu'
	else:
		raise ValueError('unknown marker_set "{}"'.format(marker_set))


def import_motion(db, motion, downsample_factor=2):
	# Download the necessary files.
	failed_files = []
	downloaded_files = 0
	all_c3d_files = [f for f in db.listFiles(motion.id) if f.fileType == 'Vicon C3D File']
	all_mmm_files = [f for f in db.listFiles(motion.id) if f.fileType == 'Converted MMM Motion']
	c3d_files, mmm_files = [], []
	for c3d_file in all_c3d_files:
		if c3d_file.visibility != MotionDatabase.VisibilityLevel.Public:
			# Only import public files.
			continue
			
		# Ensure that this file isn't already in the database.
		if MotionFile.objects.filter(motion_db_id=motion.id, motion_db_file_id=c3d_file.id).count() > 0:
			# Already exists, skip.
			continue

		# Find the matching MMM file for the given C3D file.
		mmm_file = None
		for f in all_mmm_files:
			if f.originatedFrom is not None and f.originatedFrom.id == c3d_file.id:
				mmm_file = f
				break
		if mmm_file is None:
			# No matching MMM file found, skip.
			continue

		# Only append files where we have both, the MMM and C3D file.
		mmm_files.append(mmm_file)
		c3d_files.append(c3d_file)
	assert len(c3d_files) == len(mmm_files)

	# Read all files.
	c3d_data, mmm_data, ids, names = [], [], [], []
	for mmm_file, c3d_file in zip(mmm_files, c3d_files):
		ids.append(c3d_file.id)
		names.append(c3d_file.fileName)
		
		mmm_reader = db.getFileReader(mmm_file.id)
		d = read_file(mmm_reader)
		mmm_reader.destroy()
		if d is None:
			return -1
		mmm_data.append(d)
		
		c3d_reader = db.getFileReader(c3d_file.id)
		d = read_file(c3d_reader)
		c3d_reader.destroy()
		if d is None:
			return -1
		c3d_data.append(d)

	imported_files = 0
	marker_set = get_marker_set_from_motion(motion)
	motion_files = []
	for c3d_d, mmm_d, id, name, in zip(c3d_data, mmm_data, ids, names):
		filename = '{}.json'.format(sha1('{}{}'.format(motion.id, id)).hexdigest())
		path = os.path.join(DATA_PATH, filename)
		if os.path.exists(path):
			# The file already exists. Skip motion to avoid messing with another motions file.
			continue

		# Parse.
		markers, frames, interval = parse_motion(c3d_d, mmm_d, downsample_factor, marker_set)
		if markers is None or len(markers) == 0:
			continue
		if frames is None or frames.shape[0] == 0:
			continue
		if interval is None:
			continue

		# Save in database.
		motion_file = MotionFile()
		motion_file.motion_db_id = motion.id
		motion_file.motion_db_file_id = id
		motion_file.filename = filename
		motion_file.marker_set = marker_set
		motion_file.is_hidden = True  # hide until we're done
		motion_file.save()
		
		# Save JSON file.
		data = {}
		data['markers'] = markers
		data['frames'] = frames.tolist()
		data['interval'] = interval
		data['marker_set'] = get_marker_set_identifier(marker_set)
		with open(path, 'w') as f:
			json.dump(data, f)

		# Book-keeping
		motion_files.append(motion_file)
	return motion_files


class Command(BaseCommand):
	help = 'Imports motions from the KIT motion database'

	def add_arguments(self, parser):
		pass

	def handle(self, *args, **options):
		username = raw_input('MotionDB Username: ')
		password = getpass('MotionDB Password: ')
		
		description_filter = raw_input('Description filter (leave blank for all descriptions): ')
		if len(description_filter) == 0:
			description_filter = None
		
		raw_project_ids = raw_input('Project IDs (comma-separated list; leave blank for all projects): ')
		if len(raw_project_ids) == 0:
			project_ids = None
		else:
			project_ids = [int(project_id.strip()) for project_id in raw_project_ids.split(',')]
		
		raw_institution_ids = raw_input('Institution IDs (comma-separated list; leave blank for all institutions): ')
		if len(raw_institution_ids) == 0:
			institution_ids = None
		else:
			institution_ids = [int(institution_id.strip()) for institution_id in raw_institution_ids.split(',')]

		raw_max_subjects = raw_input('Maximum number of subjects (leave blank for no limit): ')
		max_subjects = int(raw_max_subjects) if len(raw_max_subjects) > 0 else sys.maxint
		raw_max_objects = raw_input('Maximum number of objects (leave blank for no limit): ')
		max_objects = int(raw_max_objects) if len(raw_max_objects) > 0 else sys.maxint
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

		approx_motion_count = count_motions(db, project_ids, institution_ids, description_filter)
		self.stdout.write('Fetching approx. {} motions ...'.format(approx_motion_count), ending=' ')
		motions = fetch_motions(db, project_ids, institution_ids, description_filter, max_subjects, max_objects)
		n_motions = len(motions)
		self.stdout.write('done, actually obtained {} motions after applying all filters'.format(n_motions))
		self.stdout.write('')

		self.stdout.write('Importing motions ...')
		count = 0
		for idx, motion in enumerate(motions):
			self.stdout.write('  {}/{}: motion {} ...'.format(idx + 1, n_motions, motion.id), ending=' ')
			motion_files = import_motion(db, motion)
			imported_files = len(motion_files)
			if imported_files > 0:
				count += imported_files
				self.stdout.write('done, imported {} files'.format(imported_files))
			elif imported_files == 0:
				self.stdout.write('skipped')
			else:
				self.stdout.write('failed')
		self.stdout.write('Imported a total of {} files'.format(count))
		self.stdout.write('')

		self.stdout.write('Please note: the new motions haven\'t been made visible yet since you need to manually collect static files first:')
		self.stdout.write('  python manage.py collectstatic')
		self.stdout.write('You can then enable all motions by simply running the following SQL command:')
		self.stdout.write('  UPDATE dataset_motionfile SET is_hidden=0')
