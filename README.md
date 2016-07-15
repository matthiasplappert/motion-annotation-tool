# Motion Annotation Tool

- [https://motion-annotation.humanoids.kit.edu](https://motion-annotation.humanoids.kit.edu)
- Paper: [https://arxiv.org/abs/1607.03827](The KIT Motion-Language Dataset)

## Installation

Start by installing all Python dependencies:
```bash
pip install -r requirements.txt
```
Next, install [SRILM](http://www.speech.sri.com/projects/srilm/download.html). You'll have to adapt
the path to SRILM in `src/proj/settings.py`. You might also have to adapt other parts of the configuration
depending on your needs. You should also make sure that your configuration is secure. Please consult the
[Django documentation](https://docs.djangoproject.com/en/1.9/topics/security/) for this!

Finally, you can set up the database:
```bash
cd src/
python manage.py migrate
python manage.py createsuperuser
```

At this point everything is ready. However, you'll probably need some motion data:
```bash
python manage.py importmotions
```
This step requires a free account for the [KIT Whole-Body Human Motion Database](https://motion-database.humanoids.kit.edu/).
You can select different filters. At this point, only a single subject can be visualized so you should at least set the maximum number of subjects to `1`. This step is going to take a while. After all motions have been imported, you might have to collect
the static files and switch them to visible:
```bash
python manage.py collectstatic
python manage.py dbshell
UPDATE dataset_motionfile SET is_hidden=0;
```
Lastly, you can try if everything works by running a local server:
```bash
python manage.py runserver
```
Just visit [http://localhost:8000](http://localhost:8000). If everything worked, you should be able to log in
using your previously created account.
