# Django Schema Sprout

![Tests Status](./reports/assets/tests_badge.svg)
![Coverage Status](./reports/assets/coverage_badge.svg)
![Flake8 Status](./reports/assets/flake8_badge.svg)

Django Schema Sprout is a django package that helps with generating models, serializers and views dynamically for unmanaged databases.
Currently Django Schema Sprout supports only PostgreSQL (>=11.), Django (>=4.0, <5.0)


## Installation

To install Django Schema Sprout, you can run:

```sh
pip install django-schema-sprout
```

## Usage

### Settings.py
Add `django_schema_sprout` in installed apps in your `settings.py` and add `SchemaSproutDBRouter` to your database routers.  

```py
INSTALLED_APPS = [
    # django_schema_sprout requires rest_framework and drf_yasg to be installed.
    "rest_framework",
    "drf_yasg",
    ...
     "django_schema_sprout"
]
...

DATABASE_ROUTERS = [
    ...,
    "django_schema_sprout.router.SchemaSproutDBRouter",
]
```

### Initializing SchemaSprout

```py
from django_schema_sprout.schema_sprout import SchemaSprout

my_db_sprout = SchemaSprout("name_of_unmanaged_db")
```

`SchemaSprout` is Singleton based on parameters so initializing `SchemaSprout` with same database name will return same instance.

### Creating models

You can either create all models at once using `create_models`.

`create_models` takes one parameter: 
- `readonly` bool (default: `False`), specifying if created REST ViewSets should be readonly or not.

```py
my_db_sprout.create_models(readonly=True)
```

---

To create one model at the time use `create_model`.

`create_model` takes 3 parameter:
- `table_name` - str, name of the table for which you want to create model.
- `table_nspname` - str, schema where the table resides.
- `readonly` bool (default: `False`), specifying if created REST ViewSet should be readonly or not.

```py
my_db_sprout.create_model(
    table_name="my_table"
    table_nspname="my_schema"
    readonly=False
)
```

### Including SchemaSprout ViewSets
In `url.py` file, include urls from `SchemaSprout.router`. Make sure that the models that you need were created before.

```py
from django.contrib import admin
from django.urls import path, re_path, include
...

from django_schema_sprout.schema_sprout import SchemaSprout


urlpatterns = [
    ...,
    path("api/", include(SchemaSprout("name_of_unmanaged_db").router.urls)),
    ...
]
```

### Accessing created models
You can access created models, serializers and views by accessing SchemaSprout attributes:


```py
table_name = "my_table"
schema_name = "my_schema"

obj_key = f"{schema_name}_{table_name}"

my_model = my_db_sprout.models.get(obj_key, None)

my_model_serializer = my_db_sprout.serializers.get(obj_key, None)

my_model_view = my_db_sprout.views.get(obj_key, None)
```


## Contribution

Feel free to contriute or open an issue.

For local development:
-  in your venv install dev dependencies `pip install -e ".[dev]"`
- for testing install test dependencies `pip install -e ".[test]"`

Running tests requires to have installed Postgres.

## License
This project is licensed under the Apache License 2.0 

## Contact

For questions feel free to contact me: grumpy.miner.dev@gmail.com
