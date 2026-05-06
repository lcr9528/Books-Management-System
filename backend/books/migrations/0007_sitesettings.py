from django.db import migrations, models


def seed_sitesettings(apps, schema_editor):
    SiteSettings = apps.get_model("books", "SiteSettings")
    SiteSettings.objects.get_or_create(
        pk=1,
        defaults={"require_borrow_to_read_chapters": False},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0006_bookreviewcommentlike"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                ("id", models.IntegerField(default=1, primary_key=True, serialize=False)),
                (
                    "require_borrow_to_read_chapters",
                    models.BooleanField(
                        default=False,
                        help_text="开启后，未登录或未有本书在借记录的用户无法通过 API 获取章节正文。",
                        verbose_name="阅读章节需先借阅（在借中）",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "站点设置",
                "verbose_name_plural": "站点设置",
            },
        ),
        migrations.RunPython(seed_sitesettings, migrations.RunPython.noop),
    ]
