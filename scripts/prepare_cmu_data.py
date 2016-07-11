import argparse
import os
import glob
import re
import csv

from termcolor import colored
import numpy as np
import c3d
import requests


REQUIRED_MARKERS = set(['C7', 'CLAV', 'RBAC', 'T10', 'STRN', 'RFWT', 'LUPA', 'LFWT', 'LBWT', 'LKNE',
                        'RBWT', 'LFRM', 'LWRB', 'LWRA', 'LMT5', 'LTOE', 'RUPA', 'RKNE', 'RWRB', 'RWRA',
                        'RMT5', 'RTOE', 'RHEE', 'LHEE', 'RFRM', 'RSHO', 'LSHO', 'RELB', 'LELB', 'RFIN',
                        'LFIN', 'LFHD', 'RFHD', 'RBHD', 'LBHD', 'LANK', 'RANK', 'LSHN', 'RSHN', 'LTHI',
                        'RTHI'])


# Source: http://stackoverflow.com/questions/11686720/is-there-a-numpy-builtin-to-reject-outliers-from-a-list
def reject_outliers(data, m=2):
    return data[abs(data - np.mean(data)) < m * np.std(data)]


def parse_index_file(text):
    lines = [l.strip() for l in text.split('\n')]
    if len(lines) < 4:
        return None
    if not lines[1].startswith('Subject #'):
        return None

    prog = re.compile(r'Subject #(?P<subject_id>\d+) \((?P<description>[^)]+)\)')
    result = prog.match(lines[1])
    if not result:
        return None

    subject_id = int(result.group('subject_id'))
    description = result.group('description').strip()
    motions = []
    for l in lines[3:]:
        if not l:
            continue
        parts = [p.strip() for p in l.split('\t')]
        if len(parts) < 2:
            return None
        current_subject_id, motion_id = [int(x) for x in parts[0].split('_')]
        if subject_id != current_subject_id:
            return None
        if motion_id in motions:
            return None
        data = {
            'motion_id': motion_id,
            'description': parts[-1],
        }
        motions.append(data)
    data = {
        'subject_id': subject_id,
        'description': description,
        'motions': motions,
    }
    return data


def main(args):
    files = []
    subject_ids = []
    print('processing C3D files in "{}" ...'.format(args.input))
    file_candidates = glob.glob(os.path.join(args.input, '*', '*.c3d'))
    c3d_metadata = {}
    subject_heights = {}
    for idx, path in enumerate(file_candidates):
        relative_path = path.replace(args.input, '')[1:]
        print('  {}/{}: processing "{}" ...'.format(idx + 1, len(file_candidates), relative_path)),
        with open(path, 'rb') as f:
            try:
                r = c3d.Reader(f)
            except ValueError:
                print(colored('skipped, could not read C3D file', 'red'))
                continue

            # Extract marker and subject names.
            marker_names = []
            subject_names = []
            for marker in r.point_labels:
                split = marker.rstrip().split(':')
                marker_name = split[-1]
                if len(split) > 1:
                    subject_name = split[0]
                else:
                    if split[0][0] == '*':
                        # Weird fragments, probably from Vicon.
                        subject_name = None
                    else:
                        # Probably just a regular marker.
                        subject_name = 'subject'
                marker_names.append(marker_name)
                subject_names.append(subject_name)
            unique_subject_names = set([name for name in subject_names if name])  # ignore None
            nb_subjects = len(unique_subject_names)

            if nb_subjects == 0 or (args.max_subjects is not None and args.max_subjects < nb_subjects):
                print(colored('skipped, invalid subjects: {}'.format(unique_subject_names), 'red'))
                continue

            missing_markers = REQUIRED_MARKERS.difference(set(marker_names))
            
            # Estimate height.
            frames = list(r.read_frames())
            first_frames = frames[:args.nb_height_samples]
            last_frames = frames[-args.nb_height_samples:]
            raw_markers = [marker.rstrip().split(':')[-1] for marker in r.point_labels]
            lfhd_idx = raw_markers.index('LFHD')
            rfhd_idx = raw_markers.index('RFHD')
            start_height = 0.
            for i, points, analog in first_frames:
                start_height += (points[lfhd_idx, 2] + points[rfhd_idx, 2]) / 2.
            start_height /= float(len(first_frames))
            end_height = 0.
            for i, points, analog in last_frames:
                end_height += (points[lfhd_idx, 2] + points[rfhd_idx, 2]) / 2.
            end_height /= float(len(last_frames))
            start_height += 100.  # the markers are approx. 10cm below the top of the head
            end_height += 100.
            if np.abs(start_height - end_height) < args.delta_threshold:
                # Start and end height are approximately the same, use mean over both.
                height = (start_height + end_height) / 2.
            else:
                # They differ, select the height that is closest to the average human height.
                start_delta = np.abs(args.average_height - start_height)
                end_delta = np.abs(args.average_height - end_height)
                if start_delta < end_delta:
                    height = start_height
                else:
                    height = end_height
            
            # Get subject number from filename (<subject_id>_<file_id>.c3d).
            split = os.path.basename(path).split('_')
            if len(split) != 2:
                print(colored('skipping, unknown filename format', 'red'))
                continue
            subject_id = int(split[0])
            motion_id = int(split[1].split('.')[0])
            
            # Book-keeping.
            if subject_id not in subject_heights:
                subject_heights[subject_id] = []
            subject_heights[subject_id].append(height)
            subject_ids.append(subject_id)
            if subject_id not in c3d_metadata:
                c3d_metadata[subject_id] = {}
            metadata = {
                'path': relative_path,
                'frame_rate': r.header.frame_rate,
                'missing_markers': missing_markers,
            }
            c3d_metadata[subject_id][motion_id] = metadata
            files.append(path)
            
            print(colored('done', 'green'))
    print('done, {} files qualify for further processing'.format(len(files)))
    print('')
    assert len(subject_ids) == len(files)

    # Now fetch additional metadata for each subject.
    subject_data = []
    motion_data = []
    print('fetching metadata ...')
    for idx, subject_id in enumerate(subject_heights):
        print('  {}/{}: fetching data for subject {} ...'.format(idx + 1, len(subject_heights), subject_id)),
        url = 'http://mocap.cs.cmu.edu/search.php?subjectnumber={}&motion=%%%&maincat=%&subcat=%&subtext=yes'.format(subject_id)
        r = requests.get(url)
        if r.status_code != 200:
            print(colored('skipped, could not retrieve metadata', 'red'))
            continue
        index_data = parse_index_file(r.text)
        if index_data is None:
            print(colored('skipped, invalid metadata format', 'red'))
            continue
        if index_data['subject_id'] != subject_id:
            print(colored('skipped, subject id is mismatch', 'red'))
            continue

        # Condense height into a single estimate.
        heights = subject_heights[subject_id]
        if len(heights) <= 1:
            filtered_heights = np.array(heights)
        else:
            filtered_heights = reject_outliers(np.array(heights))
        height = np.mean(filtered_heights)

        # Append data for CSV export.
        data = {
            'subject_id': subject_id,
            'height': int(np.round(height)),
            'description': index_data['description'],
        }
        subject_data.append(data)
        for motion in index_data['motions']:
            motion_id = motion['motion_id']
            if motion_id not in c3d_metadata[subject_id]:
                # This motion was filtered out previously.
                continue

            # TODO: get file path
            c3d_data = c3d_metadata[subject_id][motion_id]
            data = {
                'subject_id': subject_id,
                'motion_id': motion_id,
                'path': c3d_data['path'],
                'frame_rate': c3d_data['frame_rate'],
                'description': motion['description'],
                'missing_markers': ', '.join(c3d_data['missing_markers']),
            }
            motion_data.append(data)
        
        print(colored('done', 'green'))
    print('done')
    print('')

    print('saving results to "{}" ...'.format(args.input))
    with open(os.path.join(args.input, 'motions.csv'), 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['subject_id', 'motion_id', 'description', 'path', 'frame_rate', 'missing_markers'])
        writer.writeheader()
        writer.writerows(motion_data)
    with open(os.path.join(args.input, 'subjects.csv'), 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['subject_id', 'description', 'height'])
        writer.writeheader()
        writer.writerows(subject_data)
    print('done, {} subjects and {} motions'.format(len(subject_data), len(motion_data)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('input', type=str)
    parser.add_argument('--max-subjects', type=int, default=None)
    parser.add_argument('--average-height', type=float, default=1700.)  # in mm
    parser.add_argument('--delta-threshold', type=float, default=100.)  # in mm
    parser.add_argument('--nb-height-samples', type=int, default=10)
    parser.add_argument('--height-range', type=int, nargs=2, default=[1400., 2000.])  # in mm

    main(parser.parse_args())
