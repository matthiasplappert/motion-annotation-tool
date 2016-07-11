import random
import time
import numpy as np

from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Avg
from django.contrib import messages, auth
from django.utils import timezone
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import IntegrityError, transaction
from django.conf import settings

from ipware.ip import get_ip

from .models import MotionFile, Annotation, Dataset, Download


MOTIVATIONAL_MESSAGES = ['We have saved your annotation. Thank you for helping, and keep going!',
						 'Thank you so much for helping out. You are awesome!',
						 'Today was a good day since you helped science! Keep going!',
						 'You annotate motions like there\'s no tomorrow! Thank you so much.',
						 'Who would\'ve thought that annotating motions can be this much fun, right? Thank you so much and keep going!']


LEVELS = [
	(0., 9, 'Novice', 'info'),
	(10, 49, 'Research Assistant', 'success'),
	(50, 299, 'Junior Scientist', 'warning'),
	(300, 999, 'Senior Scientist', 'danger'),
	(1000, 2999, 'Professor', 'danger'),
	(3000, 1000000, 'Donald Knuth', 'danger'),
]


def level_for_number_of_annotations(nb_annotations):
	for (lower, upper, name, klass) in LEVELS:
		if lower <= nb_annotations <= upper:
			return (lower, upper, name, klass)
	return None


def index(request):
	if not request.user.is_authenticated():
		return render(request, 'dataset/welcome.html', {})

	context = {}
	if 'motion_file_id' in request.POST:
		motion_file = get_object_or_404(MotionFile, pk=request.POST['motion_file_id'])
		description = request.POST['description'].strip()
		start_time = float(request.POST['start_time'])
		duration = int(time.time() - start_time)
		annotation = Annotation(user=request.user, motion_file=motion_file, description=description, duration=duration)
		annotation.accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE')
		annotation.ip_address = get_ip(request)
		if annotation.is_valid():
			# Update motion file and save annotation.
			motion_file.mean_perplexity = 0.  # reset mean perplexity until it is re-computed
			with transaction.atomic():
				motion_file.save()
				annotation.save()
			messages.success(request, random.choice(MOTIVATIONAL_MESSAGES))
			return redirect('dataset:index')
		
		# Annotation is invalid, prepare context.
		problem_url = '&#109;&#097;&#105;&#108;&#116;&#111;:&#109;&#097;&#116;&#116;&#104;&#105;&#097;&#115;&#046;&#112;&#108;&#097;&#112;&#112;&#101;&#114;&#116;&#064;&#115;&#116;&#117;&#100;&#101;&#110;&#116;&#046;&#107;&#105;&#116;&#046;&#101;&#100;&#117;?subject=Problem%20with%20motion%20{}'.format(motion_file.id)
		skip_url = '{}?skip={}'.format(reverse('dataset:index'), motion_file.id)
		messages.error(request, 'We think that your description of this motion is not a single, complete sentence in English. Please try again. You can also <a href="{}" class="alert-link">report a problem</a> or <a href="{}" class="alert-link">skip this motion</a>.'.format(problem_url, skip_url))
		context['motion_file'] = motion_file
		context['description'] = description
		context['invalid'] = True
		context['start_time'] = start_time
	else:
		# Get skip ID.
		try:
			skip_id = max(-1, int(request.GET['skip']))
		except:
			skip_id = -1

		# Mark as broken, if applicable.
		try:
			broken_id = int(request.GET['broken'])
			broken_motion_file = MotionFile.objects.get(id=broken_id)
			broken_motion_file.is_broken_reported = True
			broken_motion_file.save()
		except:
			pass

		# Get all annotations that haven't been annotated yet.
		q = MotionFile.objects.exclude(annotation__user=request.user)  # get all MotionFiles that haven't been annotated by the user
		q = q.annotate(annotation_count=Count('annotation__id'))  # annotate each motion file with the number of annotations
		q = q.filter(is_hidden=False, is_broken_reported=False, is_broken_confirmed=False, annotation_count=0)
		values = q.values('id')
		ids = [v['id'] for v in values if v['id'] != skip_id]

		if len(ids) > 0:
			# There are still un-annotated motions, select uniformly from them.
			selected_id = np.random.choice(ids)
		else:
			# All motions have been annotated, use perplexity-based sampling.
			q = MotionFile.objects.exclude(annotation__user=request.user)  # get all MotionFiles that haven't been annotated by the user
			q = q.filter(is_hidden=False, is_broken_reported=False, is_broken_confirmed=False)
			values = q.values('id', 'mean_perplexity')
			ids = [v['id'] for v in values if v['id'] != skip_id]
			perplexities = np.array([v['mean_perplexity'] for v in values if v['id'] != skip_id])
			assert len(ids) == len(perplexities)

			if len(ids) == 0:
				# Nothing more to annotate.
				return render(request, 'dataset/all_done.html', {})

			# Select randomly.
			probabilities = perplexities / np.sum(perplexities)
			assert np.allclose(np.sum(probabilities), 1.)
			selected_id = np.random.choice(ids, p=probabilities)
		assert selected_id != skip_id
		motion_file = MotionFile.objects.get(id=selected_id)

		motion_file.annotation_count = motion_file.annotation_set.count()
		context['overall_mean_perplexity'] = MotionFile.objects.all().aggregate(Avg('mean_perplexity'))['mean_perplexity__avg']
		context['motion_file'] = motion_file
		context['invalid'] = False
		context['start_time'] = time.time()

	# Fetch stats.
	users = User.objects.annotate(annotation_count=Count('annotation__id')).order_by('-annotation_count').all()
	all_user_ids = [user.id for user in users]
	all_annotation_counts = [user.annotation_count for user in users]
	ranked_user_idx = all_user_ids.index(request.user.id)
	user_count_annotations = all_annotation_counts[ranked_user_idx]
	total_count_motions = MotionFile.objects.filter(is_hidden=False).count()
	percentage_complete = float(user_count_annotations) / float(total_count_motions)
	lower_threshold, upper_threshold, name, klass = level_for_number_of_annotations(user_count_annotations)

	context['level_class'] = klass
	context['level_progress'] = int(round(float(user_count_annotations - lower_threshold) / float(upper_threshold - lower_threshold + 1) * 100.))
	context['level_name'] = name
	context['user_count_annotations'] = user_count_annotations
	context['total_count_motions'] = total_count_motions
	context['user_rank'] = ranked_user_idx + 1
	context['total_count_users'] = len(users)

	# Render result.
	context['motion_file_url'] = static('motions/' + context['motion_file'].filename)
	return render(request, 'dataset/annotate.html', context)


def stats(request):
	if not request.user.is_authenticated():
		return redirect('dataset:sign-in')

	# Fetch stats.
	users = User.objects.annotate(annotation_count=Count('annotation__id')).order_by('-annotation_count').all()
	max_annotation_count = users[0].annotation_count
	total_motions = MotionFile.objects.filter(is_hidden=False, is_broken_reported=False, is_broken_confirmed=False).count()
	total_annotations = Annotation.objects.filter(motion_file__is_hidden=False, motion_file__is_broken_reported=False, motion_file__is_broken_confirmed=False).count()
	total_users = len(users)
	distinct_annotations = Annotation.objects.filter(motion_file__is_hidden=False, motion_file__is_broken_reported=False, motion_file__is_broken_confirmed=False).values('motion_file_id').distinct().count()
	
	for idx, user in enumerate(users):
		percentage_complete = float(user.annotation_count) / float(total_motions)
		_, _, name, klass = level_for_number_of_annotations(user.annotation_count)
		user.level_class = klass
		user.level_name = name
		user.rank = idx + 1
		user.progress = float(user.annotation_count) / float(max_annotation_count) * 100.
		user.total_progress = int(round(percentage_complete * 100.))

	context = {
		'users': users,
		'total_motions': total_motions,
		'total_annotations': total_annotations,
		'total_users': total_users,
		'distinct_annotations': distinct_annotations,
		'percentage_complete': int(round(float(distinct_annotations) / float(total_motions) * 100.)),
		'annotations_per_motion': float(total_annotations) / float(total_motions),
	}
	return render(request, 'dataset/stats.html', context)


def logout(request):
	auth.logout(request)
	return redirect('dataset:index')

def register(request):
	if request.user.is_authenticated():
		return redirect('dataset:index')

	email = ''
	username = ''
	if 'email' in request.POST:
		username = request.POST['username']
		email = request.POST['email']
		password = request.POST['password']
		password_repeat = request.POST['password-repeat']

		# Validate.
		try:
			validate_email(email)
			is_valid_email = True
		except ValidationError:
			is_valid_email = False
		is_valid_username = len(username) > 0
		is_valid_password = (len(password) > 5)
		is_valid_repeat_password = (password == password_repeat)

		if not is_valid_username:
			messages.error(request, 'The username you entered appears to be invalid. Please try again.')
		elif not is_valid_email:
			messages.error(request, 'The email address you entered appears to be invalid. Please try again.')
		elif not is_valid_password:
			messages.error(request, 'Your password is too short. Please use a password that contains at least 6 characters.')
		elif not is_valid_repeat_password:
			messages.error(request, 'The passwords you entered do not match. Please try again.')
		else:
			try:
				user = User.objects.create_user(username=username,
										 		email=email,
										 		password=password)
				success = True
			except IntegrityError:
				success = False
				url = reverse('dataset:sign-in')
				message = 'Your username or email address was already used to register an account. Please <a href="{}" class="alert-link">sign in</a> or use a different email address.'.format(url)
				messages.error(request, message, )
			if success:
				login(request, authenticate(username=username, password=password))
				messages.success(request, 'You have successfully created an account. We\'ve already logged you in so that you can start annotating motions right away!')
				return redirect('dataset:index')
	context = {'email': email, 'username': username}
	return render(request, 'dataset/register.html', context)


def dataset(request):
	# Get the datasets
	datasets = Dataset.objects.order_by('-creation_date').all()
	context = {
		'datasets': datasets,
	}
	return render(request, 'dataset/dataset.html', context)


def download_dataset(request, dataset_id):
	dataset = get_object_or_404(Dataset, pk=dataset_id)
	
	# Record the download.
	download = Download()
	download.dataset = dataset
	download.accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE')
	download.ip_address = get_ip(request)
	download.save()

	return redirect('/static/downloads/{}'.format(dataset.filename))
