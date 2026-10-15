# Heritage Show theme choice on User.ui_theme (tokens in assets/themes.css).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_sample_content"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="ui_theme",
            field=models.CharField(
                choices=[
                    ("light", "Light"),
                    ("heritage", "Heritage Show"),
                    ("dark-a", "Evergreen night"),
                    ("dark-b", "Midnight and mint"),
                    ("dark-c", "Deep moss and amber"),
                    ("med-a", "Slate"),
                    ("med-b", "Charcoal sage"),
                    ("med-c", "Graphite and sky"),
                    ("warm-a", "Cream and forest"),
                    ("warm-b", "Oat and terracotta"),
                    ("warm-c", "Linen and olive"),
                    ("cool-a", "Mist and forest"),
                    ("cool-b", "Blue-gray and indigo"),
                    ("cool-c", "Fog and teal"),
                ],
                default="light",
                max_length=8,
            ),
        ),
    ]
