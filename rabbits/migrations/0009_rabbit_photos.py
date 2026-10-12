"""Replace the single Rabbit.photo with RabbitPhoto rows.

Each rabbit's existing photo becomes its main RabbitPhoto, pointing at the
same stored file, so nothing is copied or lost. Going back puts each main
photo's file back on Rabbit.photo.
"""

import django.db.models.deletion
import django.utils.timezone
import rabbits.models
from django.db import migrations, models


def copy_photos_forward(apps, schema_editor):
    Rabbit = apps.get_model("rabbits", "Rabbit")
    RabbitPhoto = apps.get_model("rabbits", "RabbitPhoto")
    for rabbit in Rabbit.objects.exclude(photo=""):
        RabbitPhoto.objects.create(
            rabbit=rabbit, image=rabbit.photo.name, is_main=True, uploaded_at=rabbit.updated_at
        )


def copy_photos_back(apps, schema_editor):
    Rabbit = apps.get_model("rabbits", "Rabbit")
    RabbitPhoto = apps.get_model("rabbits", "RabbitPhoto")
    for photo in RabbitPhoto.objects.filter(is_main=True):
        Rabbit.objects.filter(pk=photo.rabbit_id).update(photo=photo.image.name)


class Migration(migrations.Migration):

    dependencies = [
        ('rabbits', '0008_rabbit_color_is_standard'),
    ]

    operations = [
        migrations.CreateModel(
            name='RabbitPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to=rabbits.models.photo_file_path)),
                ('notes', models.TextField(blank=True, max_length=500)),
                ('is_main', models.BooleanField(default=False)),
                ('uploaded_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('rabbit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='rabbits.rabbit')),
            ],
            options={
                'ordering': ['-is_main', 'uploaded_at', 'pk'],
                'constraints': [models.UniqueConstraint(condition=models.Q(('is_main', True)), fields=('rabbit',), name='one_main_photo_per_rabbit')],
            },
        ),
        migrations.RunPython(copy_photos_forward, copy_photos_back),
        migrations.RemoveField(
            model_name='rabbit',
            name='photo',
        ),
    ]
