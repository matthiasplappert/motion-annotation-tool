DOWNLOAD_CHUNK_SIZE = 32768
FETCH_LIMIT = 200


def count_motions(db, project_ids=None, institution_ids=None, description_filter=None):
	count = db.countMotions(None, project_ids, institution_ids, None, None, description_filter)
	return count


def fetch_motions(db, project_ids=None, institution_ids=None, description_filter=None, max_subjects=None, max_objects=None):
	offset = 0
	motions = []
	while True:
		ms = db.listMotions(None, project_ids, institution_ids, None, None, description_filter, 'id', FETCH_LIMIT, offset)
		filtered_ms = ms
		if max_subjects is not None:
			filtered_ms = [m for m in filtered_ms if len(m.associatedSubjects) <= max_subjects]
		if max_objects is not None:
			filtered_ms = [m for m in filtered_ms if len(m.associatedObjects) <= max_objects]
		motions.extend(filtered_ms)
		offset += FETCH_LIMIT
		if len(ms) != FETCH_LIMIT:
			break
	return motions


def read_file(reader):
	size = reader.getSize()
	data = ''
	try:
		# We cannot just read the entire file b/c readChunk() seems to have an limit.
		remaining_size = size
		while remaining_size > 0:
			s = min(remaining_size, DOWNLOAD_CHUNK_SIZE)
			data += reader.readChunk(s)
			remaining_size -= s
	except:
		data = None
	return data
